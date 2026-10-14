import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import mongomock
import requests
from cryptography.fernet import Fernet
from mongoengine import connect, disconnect

from apiserver.apierrors import APIError
from apiserver.bll import datastudio
from apiserver.database import Database
from apiserver.database.model.datastudio import DataStudioConnection


TOKEN = "ds_pat_" + "a" * 40


class DataStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        disconnect(alias=Database.auth)
        connect("datastudio-unit-tests", alias=Database.auth, mongo_client_class=mongomock.MongoClient)

    @classmethod
    def tearDownClass(cls):
        disconnect(alias=Database.auth)

    def setUp(self):
        DataStudioConnection.drop_collection()
        self.environment = patch.dict(os.environ, {
            "DATASTUDIO_API_URL": "http://studio:8000/api/v1",
            "DATASTUDIO_WEB_URL": "http://studio.example:3000",
            "DATASTUDIO_TOKEN_KEY": Fernet.generate_key().decode(),
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def connect(self, company="company", user="alice", token=TOKEN):
        with patch.object(datastudio, "request", side_effect=[{"username": "studio-alice"}, {"items": []}]):
            return datastudio.connect(company, user, "studio-alice", token)

    def test_credentials_are_encrypted_and_absent_from_status(self):
        result = self.connect()
        self.assertTrue(result["connected"])
        saved = datastudio.connection("company", "alice")
        self.assertNotIn(TOKEN, json.dumps(saved.to_mongo().to_dict(), default=str))
        self.assertEqual(datastudio.cipher().decrypt(saved.encrypted_token.encode()).decode(), TOKEN)
        self.assertNotIn("token", json.dumps(result))
        self.assertEqual(DataStudioConnection.objects.count(), 1)
        self.connect(token="ds_pat_" + "b" * 40)
        self.assertEqual(DataStudioConnection.objects.count(), 1)

    def test_connection_is_scoped_to_both_user_and_company(self):
        self.connect()
        for company, user in [("company", "bob"), ("other-company", "alice")]:
            self.assertFalse(datastudio.status(company, user)["connected"])
            with patch.object(datastudio, "request") as upstream, self.assertRaises(APIError):
                datastudio.datasets(company, user)
            upstream.assert_not_called()
            datastudio.disconnect(company, user)
        self.assertTrue(datastudio.status("company", "alice")["connected"])

    def test_username_mismatch_preserves_previous_connection(self):
        self.connect()
        before = datastudio.connection("company", "alice").encrypted_token
        with patch.object(datastudio, "request", return_value={"username": "someone-else"}), self.assertRaises(APIError):
            datastudio.connect("company", "alice", "studio-alice", "ds_pat_" + "b" * 40)
        self.assertEqual(before, datastudio.connection("company", "alice").encrypted_token)

    def test_disconnect_removes_only_the_current_users_credential(self):
        self.connect()
        self.connect(user="bob")
        result = datastudio.disconnect("company", "alice")
        self.assertFalse(result["connected"])
        self.assertIsNone(datastudio.connection("company", "alice"))
        self.assertIsNotNone(datastudio.connection("company", "bob"))

    def test_malformed_credentials_never_echo_input(self):
        for value in [None, [], "private-secret", "ds_pat_" + "secret" * 100]:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(APIError) as caught:
                datastudio.connect("company", "alice", "studio-alice", value)
            self.assertNotIn("private-secret", str(caught.exception))
            self.assertNotIn("secretsecret", str(caught.exception))
        data = {"username": "studio-alice", "token": TOKEN, "user": "bob"}
        with self.assertRaises(APIError) as caught:
            datastudio.parse_credentials(data)
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertNotIn("token", data)

    def test_dataset_refresh_and_revisions_omit_unexpected_upstream_fields(self):
        self.connect()
        dataset = {"id": "repo", "namespace": "studio-alice", "slug": "vehicles", "token": TOKEN,
                   "latest_revision": {"revision_id": "abc123", "token": TOKEN}}
        with patch.object(datastudio, "request", side_effect=[{"username": "studio-alice"}, {"items": [dataset]}]):
            result = datastudio.datasets("company", "alice")
        self.assertEqual(result["items"][0]["slug"], "vehicles")
        self.assertNotIn(TOKEN, json.dumps(result))
        with patch.object(datastudio, "request", side_effect=[{"username": "studio-alice"}, [{"revision_id": "abc123", "token": TOKEN}]]):
            result = datastudio.revisions("company", "alice", "studio-alice", "vehicles")
        self.assertEqual(result["revisions"][0]["revision_id"], "abc123")
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_changed_server_does_not_receive_existing_token(self):
        self.connect()
        with patch.dict(os.environ, {"DATASTUDIO_API_URL": "http://different-server/api/v1"}):
            self.assertFalse(datastudio.status("company", "alice")["connected"])
            with patch.object(datastudio, "request") as upstream, self.assertRaises(APIError):
                datastudio.datasets("company", "alice")
            upstream.assert_not_called()

    def test_bad_key_does_not_expose_ciphertext(self):
        self.connect()
        ciphertext = datastudio.connection("company", "alice").encrypted_token
        with patch.dict(os.environ, {"DATASTUDIO_TOKEN_KEY": Fernet.generate_key().decode()}), self.assertRaises(APIError) as caught:
            datastudio.datasets("company", "alice")
        self.assertNotIn(ciphertext, str(caught.exception))

    def test_path_traversal_is_rejected_before_upstream_request(self):
        with patch.object(datastudio, "request") as upstream:
            for namespace, dataset in [("../auth", "vehicles"), ("alice", "../tokens"), ("alice", "vehicles?token=secret")]:
                with self.assertRaises(APIError):
                    datastudio.revisions("company", "alice", namespace, dataset)
            upstream.assert_not_called()

    def test_outbound_request_disables_redirects_and_environment_credentials(self):
        client = MagicMock()
        response = client.get.return_value
        response.status_code = 200
        response.json.return_value = {"username": "studio-alice"}
        with patch.object(datastudio.requests, "Session") as session:
            session.return_value.__enter__.return_value = client
            datastudio.request(TOKEN, "/auth/me")
        self.assertFalse(client.trust_env)
        self.assertFalse(client.get.call_args.kwargs["allow_redirects"])
        self.assertEqual(client.get.call_args.kwargs["headers"]["Authorization"], "Bearer " + TOKEN)

    def test_upstream_failures_do_not_leak_token_or_response(self):
        for failure in [requests.Timeout(TOKEN), requests.ConnectionError(TOKEN), ValueError(TOKEN)]:
            client = MagicMock()
            client.get.side_effect = failure
            with patch.object(datastudio.requests, "Session") as session:
                session.return_value.__enter__.return_value = client
                with self.assertRaises(APIError) as caught:
                    datastudio.request(TOKEN, "/auth/me")
                self.assertNotIn(TOKEN, str(caught.exception))
        for code in (301, 401, 403, 404, 500):
            client = MagicMock()
            client.get.return_value.status_code = code
            client.get.return_value.text = TOKEN
            with patch.object(datastudio.requests, "Session") as session:
                session.return_value.__enter__.return_value = client
                with self.assertRaises(APIError) as caught:
                    datastudio.request(TOKEN, "/auth/me")
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_persistent_key_is_private_and_safe_for_concurrent_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "token.key"
            with patch.dict(os.environ, {"DATASTUDIO_TOKEN_KEY": "", "DATASTUDIO_TOKEN_KEY_FILE": str(key_file)}):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    ciphertexts = list(pool.map(lambda _: datastudio.cipher().encrypt(TOKEN.encode()), range(8)))
                for ciphertext in ciphertexts:
                    self.assertEqual(datastudio.cipher().decrypt(ciphertext).decode(), TOKEN)
            self.assertEqual(key_file.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
