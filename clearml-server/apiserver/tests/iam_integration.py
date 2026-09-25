"""Opt-in IAM smoke test against a running server.

Set CLEARML_IAM_TEST_URL, CLEARML_IAM_TEST_ADMIN and
CLEARML_IAM_TEST_ADMIN_PASSWORD. The test creates a uniquely named user, verifies
USER authorization denial, disables it, checks login denial, and verifies audit.
"""
import base64
import os
import secrets
import unittest

import requests


class IAMIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["CLEARML_IAM_TEST_URL"].rstrip("/")
        cls.admin = os.environ["CLEARML_IAM_TEST_ADMIN"]
        cls.password = os.environ["CLEARML_IAM_TEST_ADMIN_PASSWORD"]
        cls.session = requests.Session()
        cls._login(cls.session, cls.admin, cls.password)

    @classmethod
    def _login(cls, session, username, password, expected=200):
        basic = base64.b64encode(f"{username}:{password}".encode()).decode()
        response = session.post(
            f"{cls.url}/auth.login", headers={"Authorization": f"Basic {basic}"}
        )
        if response.status_code != expected:
            raise AssertionError(response.text)
        return response

    def call(self, session, action, data=None, expected=200):
        response = session.post(f"{self.url}/iam.{action}", json=data or {})
        self.assertEqual(expected, response.status_code, response.text)
        return response.json().get("data", {})

    def test_admin_user_disable_and_audit_flow(self):
        suffix = secrets.token_hex(4)
        username = f"iamtest-{suffix}"
        password = "Temporary-Test-123!"
        created = self.call(self.session, "create_user", {
            "username": username, "password": password, "role": "user",
            "must_change_password": False,
        })["user"]
        user_session = requests.Session()
        self._login(user_session, username, password)
        self.call(user_session, "create_user", {
            "username": f"denied-{suffix}", "password": password,
        }, expected=403)
        self.call(self.session, "disable_user", {"user_id": created["id"]})
        self._login(requests.Session(), username, password, expected=401)
        events = self.call(self.session, "list_audit", {"target_id": created["id"]})
        self.assertTrue(any(e["action"] == "USER_DISABLED" for e in events["events"]))

    def test_signup_creates_user_without_admin_grant(self):
        suffix = secrets.token_hex(4)
        username = f"signup-{suffix}"
        password = "Signup-Test-123!"
        created = self.call(requests.Session(), "signup", {
            "username": username,
            "email": f"{username}@example.com",
            "display_name": "Signup User",
            "password": password,
        })["user"]
        self.assertEqual("user", created["role"])

        user_session = requests.Session()
        self._login(user_session, username, password)
        self.call(user_session, "update_user", {
            "user_id": created["id"], "role": "admin",
        }, expected=403)


if __name__ == "__main__":
    unittest.main()
