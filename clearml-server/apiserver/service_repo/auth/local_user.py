from datetime import datetime, timedelta

import bcrypt

from apiserver.apierrors import errors
from apiserver.bll.iam import audit, enabled, normalize_username, verify_password
from apiserver.config_repo import config
from apiserver.database.model.auth import User


# A valid hash makes unknown-user and wrong-password paths perform the same
# expensive comparison without creating a secret or account at startup.
_DUMMY_HASH = b"$2b$12$C6UzMDM.H6dfI/f/IKcEe.ou8Z8uo1qZdJzO7l7gJb7xVjQWcVYfK"


class LocalDatabaseProvider:
    @classmethod
    def enabled(cls):
        return enabled()

    @classmethod
    def authenticate(cls, username: str, password: str, call) -> User:
        normalized = normalize_username(username)
        user = User.objects(username=normalized).first()
        now = datetime.utcnow()

        if not user:
            bcrypt.checkpw(password.encode("utf-8")[:72], _DUMMY_HASH)
            audit(
                "LOGIN_FAILURE",
                company=config.get("apiserver.default_company"),
                target_type="user",
                actor_username=normalized,
                call=call,
                metadata={"reason": "invalid_credentials"},
            )
            raise errors.unauthorized.InvalidCredentials(
                "invalid username or password"
            )

        invalid_state = user.status != "active" or (
            user.locked_until and user.locked_until > now
        )
        password_valid = verify_password(password, user.password_hash)
        if invalid_state or not password_valid:
            if not password_valid:
                max_attempts = int(
                    config.get("apiserver.auth.iam.lockout.max_attempts", 5)
                )
                duration = int(
                    config.get("apiserver.auth.iam.lockout.duration_minutes", 15)
                )
                user = User.objects(id=user.id).modify(
                    inc__failed_login_count=1, set__updated=now, new=True
                )
                if user.failed_login_count >= max_attempts:
                    user.update(
                        set__locked_until=now + timedelta(minutes=duration),
                        set__failed_login_count=0,
                    )
                    audit(
                        "ACCOUNT_LOCKED",
                        user.company,
                        "user",
                        user.id,
                        actor=user,
                        call=call,
                    )
            audit(
                "LOGIN_FAILURE",
                user.company,
                "user",
                user.id,
                actor=user,
                call=call,
                metadata={"reason": "invalid_credentials"},
            )
            raise errors.unauthorized.InvalidCredentials(
                "invalid username or password"
            )

        User.objects(id=user.id).update_one(
            set__validated=now,
            set__last_login_ip=call.real_ip,
            set__failed_login_count=0,
            set__locked_until=None,
            set__updated=now,
        )
        user.validated = now
        user.last_login_ip = call.real_ip
        audit("LOGIN_SUCCESS", user.company, "user", user.id, actor=user, call=call)
        return user
