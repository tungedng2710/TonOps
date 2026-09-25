import unittest
from datetime import datetime, timedelta
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
from apiserver.database.model.iam import IAMAuditEvent, IAMGroup, IAMGroupMember
from apiserver.service_repo.auth.local_user import LocalDatabaseProvider
from apiserver.service_repo.auth import Identity, Token


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
