import unittest
from datetime import datetime, timedelta
import os
from types import SimpleNamespace
from unittest.mock import patch

import mongomock
from mongoengine import connect, disconnect
from mongoengine.errors import NotUniqueError

from apiserver.apierrors import APIError
from apiserver.bll.iam import (
    audit,
    create_user,
    hash_password,
    normalize_username,
    serialize_user,
    set_password,
    validate_password,
    verify_password,
)
from apiserver.database import Database
from apiserver.database.model.auth import Role, User
from apiserver.database.model.project import Project
from apiserver.database.model.model import Model
from apiserver.database.model.user import User as BackendUser
from apiserver.database.model.iam import IAMAuditEvent, IAMGroup, IAMGroupMember
from apiserver.service_repo.auth.local_user import LocalDatabaseProvider
from apiserver.service_repo.auth import Identity, Token
from apiserver.services.storage import sign_rustfs_url


def config_get(key, default=None):
    values = {
        "apiserver.auth.iam.enabled": True,
        "apiserver.auth.iam.self_signup.enabled": True,
        "apiserver.auth.iam.audit.enabled": True,
        "apiserver.auth.iam.password_policy": {"min_length": 12, "max_length": 128},
        "apiserver.auth.iam.password_policy.bcrypt_rounds": 4,
        "apiserver.auth.iam.password_policy.history": 2,
        "apiserver.auth.iam.lockout.max_attempts": 5,
        "apiserver.auth.iam.lockout.duration_minutes": 15,
        "apiserver.default_company": "company",
    }
    return values.get(key, default)


class LocalIAMTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for alias in (Database.auth, Database.backend):
            disconnect(alias=alias)
            connect(
                f"iam-test-{alias}",
                alias=alias,
                mongo_client_class=mongomock.MongoClient,
            )

    def setUp(self):
        User.drop_collection()
        BackendUser.drop_collection()
        Project.drop_collection()
        Model.drop_collection()
        IAMGroup.drop_collection()
        IAMGroupMember.drop_collection()
        IAMAuditEvent.drop_collection()
        self.config_patch = patch("apiserver.bll.iam.config.get", side_effect=config_get)
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()

    def test_password_policy_hash_and_safe_serialization(self):
        with self.assertRaises(APIError):
            validate_password("short")
        password_hash = hash_password("Correct-Horse-1")
        self.assertTrue(verify_password("Correct-Horse-1", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))
        user = create_user(
            company="company",
            username=" Alice ",
            password="Correct-Horse-1",
            role=Role.user,
        )
        self.assertEqual("alice", normalize_username(" Alice "))
        result = serialize_user(user)
        self.assertNotIn("password_hash", result)
        self.assertNotIn("password_history", result)

    def test_auth_version_round_trips_in_jwt(self):
        encoded = Token.create_encoded_token(
            identity=Identity(user="user", company="company", role=Role.user),
            auth_version=7,
        )
        self.assertEqual(7, Token.from_encoded_token(encoded).auth_version)

    def test_unique_username_and_password_reset_invalidates_tokens(self):
        user = create_user(
            company="company", username="alice", password="Correct-Horse-1"
        )
        with self.assertRaises(APIError):
            create_user(
                company="company", username="ALICE", password="Another-Horse-2"
            )
        old_hash = user.password_hash
        set_password(user, "Another-Horse-2", must_change=True)
        self.assertEqual(2, user.auth_version)
        self.assertTrue(user.must_change_password)
        self.assertIn(old_hash, user.password_history)

    def test_valid_invalid_disabled_locked_and_unknown_login(self):
        user = create_user(
            company="company", username="alice", password="Correct-Horse-1"
        )
        call = SimpleNamespace(real_ip="127.0.0.1", headers={"User-Agent": "test"})
        with patch("apiserver.service_repo.auth.local_user.config.get", side_effect=config_get):
            authenticated = LocalDatabaseProvider.authenticate(
                "ALICE", "Correct-Horse-1", call
            )
            self.assertEqual(user.id, authenticated.id)
            with self.assertRaises(APIError):
                LocalDatabaseProvider.authenticate("alice", "wrong-password", call)
            with self.assertRaises(APIError):
                LocalDatabaseProvider.authenticate("unknown", "wrong-password", call)

            user.reload()
            user.status = "disabled"
            user.save()
            with self.assertRaises(APIError):
                LocalDatabaseProvider.authenticate("alice", "Correct-Horse-1", call)
            user.status = "active"
            user.locked_until = datetime.utcnow() + timedelta(minutes=5)
            user.save()
            with self.assertRaises(APIError):
                LocalDatabaseProvider.authenticate("alice", "Correct-Horse-1", call)

    def test_group_membership_is_unique_and_group_delete_does_not_delete_user(self):
        user = create_user(
            company="company", username="alice", password="Correct-Horse-1"
        )
        group = IAMGroup(
            id="group", company="company", name="cv-team", description="CV",
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(), created_by=user.id,
        ).save()
        membership = dict(
            company="company", group_id=group.id, user_id=user.id,
            created_at=datetime.utcnow(), created_by=user.id,
        )
        IAMGroupMember(id="one", **membership).save()
        with self.assertRaises(NotUniqueError):
            IAMGroupMember(id="two", **membership).save()
        IAMGroupMember.objects(group_id=group.id).delete()
        group.delete()
        self.assertIsNotNone(User.objects(id=user.id).first())

    def test_audit_is_append_only_and_redacts_sensitive_metadata(self):
        user = create_user(
            company="company", username="admin", password="Correct-Horse-1", role=Role.admin
        )
        audit(
            "PASSWORD_RESET", "company", "user", user.id, actor=user,
            metadata={"password": "never-store", "field": "safe"},
        )
        event = IAMAuditEvent.objects.get()
        self.assertNotIn("password", event.metadata)
        self.assertEqual("safe", event.metadata["field"])

    def test_cannot_remove_last_active_admin(self):
        from apiserver.services.iam import _protect_last_admin

        admin = create_user(
            company="company", username="admin", password="Correct-Horse-1", role=Role.admin
        )
        with self.assertRaises(APIError):
            _protect_last_admin(admin, status="disabled")
        create_user(
            company="company", username="admin2", password="Correct-Horse-2", role=Role.admin
        )
        _protect_last_admin(admin, status="disabled")

    def test_admin_endpoints_reject_normal_user_role(self):
        # Importing registers service endpoints from their public schemas.
        import apiserver.services.iam  # noqa: F401
        from apiserver.service_repo import ServiceRepo
        from apiserver.utilities.partial_version import PartialVersion

        create_endpoint = ServiceRepo._get_endpoint(
            "iam.create_user", PartialVersion("2.36")
        )
        update_endpoint = ServiceRepo._get_endpoint(
            "iam.update_user", PartialVersion("2.36")
        )
        change_endpoint = ServiceRepo._get_endpoint(
            "iam.change_password", PartialVersion("2.36")
        )
        signup_endpoint = ServiceRepo._get_endpoint(
            "iam.signup", PartialVersion("2.36")
        )
        self.assertTrue(create_endpoint.allows(Role.admin))
        self.assertFalse(create_endpoint.allows(Role.user))
        self.assertTrue(update_endpoint.allows(Role.admin))
        self.assertFalse(update_endpoint.allows(Role.user))
        self.assertTrue(change_endpoint.allows(Role.user))
        self.assertFalse(signup_endpoint.authorize)

    def test_public_profile_filters_private_projects_and_credentials(self):
        from apiserver.services.iam import get_profile, search_profiles

        owner = create_user(company="company", username="admin", password="Correct-Horse-1", role=Role.admin)
        viewer = create_user(company="company", username="viewer", password="Correct-Horse-2")
        now = datetime.utcnow()
        Project(id="public", company="company", user=owner.id, name="Public", basename="Public", visibility="public", created=now).save()
        Project(id="private", company="company", user=owner.id, name="Private", basename="Private", visibility="private", created=now).save()
        call = SimpleNamespace(data={"user_id": owner.id}, identity=SimpleNamespace(user=viewer.id))
        result = get_profile(call, "company", None)
        self.assertEqual(["public"], [project["id"] for project in result["projects"]])
        self.assertEqual(Role.admin, result["user"]["role"])
        self.assertNotIn("email", result["user"])
        self.assertNotIn("credentials", result["user"])
        call.identity.user = owner.id
        self.assertEqual(2, len(get_profile(call, "company", None)["projects"]))
        directory = search_profiles(SimpleNamespace(data={"search": "admin"}), "company", None)
        self.assertEqual([owner.id], [user["id"] for user in directory["users"]])

    def test_profile_lookup_by_username_preserves_visibility_and_company_scope(self):
        from apiserver.services.iam import get_profile

        owner = create_user(company="company", username="alex.smith", password="Correct-Horse-1")
        viewer = create_user(company="company", username="viewer", password="Correct-Horse-2")
        create_user(company="other", username="external", password="Correct-Horse-3")
        now = datetime.utcnow()
        for visibility in ("public", "private"):
            Project(id=visibility, company="company", user=owner.id, name=visibility, basename=visibility,
                    visibility=visibility, created=now).save()
        call = SimpleNamespace(data={"username": " ALEX.SMITH "}, identity=SimpleNamespace(user=viewer.id))
        result = get_profile(call, "company", None)
        self.assertEqual(owner.id, result["user"]["id"])
        self.assertEqual("alex.smith", result["user"]["username"])
        self.assertEqual(["public"], [project["id"] for project in result["projects"]])
        call.identity.user = owner.id
        self.assertEqual(2, len(get_profile(call, "company", None)["projects"]))
        for username in ("external", "missing"):
            call.data = {"username": username}
            with self.assertRaises(APIError):
                get_profile(call, "company", None)
        owner.update(status="disabled")
        call.data = {"username": owner.username}
        with self.assertRaises(APIError):
            get_profile(call, "company", None)

    def test_profile_search_never_returns_a_directory_and_only_matches_active_members(self):
        from apiserver.services.iam import search_profiles

        viewer = create_user(company="company", username="viewer", password="Correct-Horse-1")
        match = create_user(company="company", username="alex.one", password="Correct-Horse-2")
        disabled = create_user(company="company", username="alex.disabled", password="Correct-Horse-3")
        disabled.update(status="disabled")
        create_user(company="other", username="alex.external", password="Correct-Horse-4")
        call = SimpleNamespace(data={}, identity=SimpleNamespace(user=viewer.id, role=Role.user))
        for search in (None, "", "  ", "a", " a "):
            call.data = {} if search is None else {"search": search}
            result = search_profiles(call, "company", None)
            self.assertEqual([], result["users"])
            self.assertEqual(0, result["total"])
        call.data = {"search": " ALEX ", "page_size": 1}
        result = search_profiles(call, "company", None)
        self.assertEqual(1, result["total"])
        self.assertEqual([match.id], [person["id"] for person in result["users"]])
        self.assertNotIn("email", result["users"][0])
        self.assertNotIn("password_hash", result["users"][0])
        call.data["page"] = 1
        self.assertEqual([], search_profiles(call, "company", None)["users"])

    def test_profile_request_accepts_exactly_one_lookup_key(self):
        import jsonschema
        from apiserver.service_repo import ServiceRepo
        from apiserver.utilities.partial_version import PartialVersion

        endpoint = ServiceRepo._get_endpoint("iam.get_profile", PartialVersion("2.36"))
        schema = endpoint.request_schema_validator.schema
        for data in ({"username": "alex.smith"}, {"user_id": "legacy-id"}):
            jsonschema.validate(data, schema)
        for data in ({}, {"username": ""}, {"username": "alex", "user_id": "id"}):
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(data, schema)

    def test_rustfs_download_requires_access_to_registered_model(self):
        owner = create_user(company="company", username="owner", password="Correct-Horse-1")
        viewer = create_user(company="company", username="viewer", password="Correct-Horse-2")
        project = Project(id="project", company="company", user=owner.id, name="Private", basename="Private", visibility="private", created=datetime.utcnow()).save()
        uri = "s3://storage.example:7868/tonops-artifacts/migrated/models/model/weights.pt"
        Model(id="model", company="company", user=owner.id, project=project.id, name="weights", uri=uri, ready=False, created=datetime.utcnow()).save()
        call = SimpleNamespace(data={"url": uri}, identity=SimpleNamespace(user=viewer.id, role=Role.user))
        environment = {
            "RUSTFS_PUBLIC_HOST": "storage.example", "RUSTFS_API_PORT": "7868",
            "RUSTFS_BUCKET": "tonops-artifacts", "RUSTFS_ACCESS_KEY": "TESTACCESSKEY",
            "RUSTFS_SECRET_KEY": "test-secret",
        }
        with patch.dict(os.environ, environment):
            with self.assertRaises(APIError):
                sign_rustfs_url(call, "company", None)
            project.update(visibility="public")
            signed = sign_rustfs_url(call, "company", None)["signed"]
            self.assertIn("X-Amz-Signature=", signed)
            self.assertTrue(signed.startswith("http://storage.example:7868/tonops-artifacts/"))
            call.data["url"] = "s3://storage.example:7868/tonops-artifacts/other.pt"
            with self.assertRaises(APIError):
                sign_rustfs_url(call, "company", None)

    def test_self_signup_always_creates_a_normal_user(self):
        from apiserver.services.iam import signup

        call = SimpleNamespace(
            data={
                "username": "new-user",
                "email": "new-user@example.com",
                "display_name": "New User",
                "password": "Correct-Horse-1",
            },
            real_ip="127.0.0.1",
            headers={"User-Agent": "test"},
        )
        result = signup(call, None, None)
        self.assertEqual(Role.user, result["user"]["role"])
        user = User.objects(username="new-user").get()
        self.assertEqual(Role.user, user.role)
        self.assertFalse(user.must_change_password)
        self.assertEqual("self_signup", user.created_by)


if __name__ == "__main__":
    unittest.main()
