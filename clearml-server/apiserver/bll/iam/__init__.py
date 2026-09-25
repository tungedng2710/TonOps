import re
import secrets
import string
from datetime import datetime
from typing import Optional

import bcrypt
from mongoengine.errors import NotUniqueError

from apiserver import database
from apiserver.apierrors import errors
from apiserver.config.info import get_version
from apiserver.config_repo import config
from apiserver.database.model.auth import Role, User as AuthUser
from apiserver.database.model.iam import IAMAuditEvent
from apiserver.database.model.user import User as BackendUser


USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


def enabled() -> bool:
    return config.get("apiserver.auth.iam.enabled", False)


def self_signup_enabled() -> bool:
    return enabled() and config.get(
        "apiserver.auth.iam.self_signup.enabled", True
    )


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not USERNAME_RE.fullmatch(normalized):
        raise errors.bad_request.ValidationError(
            "username must be 3-64 lowercase letters, numbers, dots, dashes or underscores",
            field="username",
        )
    return normalized


def validate_password(password: str) -> None:
    policy = config.get("apiserver.auth.iam.password_policy", {})
    min_length = int(policy.get("min_length", 12))
    max_length = int(policy.get("max_length", 128))
    if not isinstance(password, str) or not min_length <= len(password) <= max_length:
        raise errors.bad_request.ValidationError(
            f"password length must be between {min_length} and {max_length}",
            field="password",
        )
    # bcrypt rejects input over 72 bytes. Keep the configured character limit,
    # while also making the hashing limit explicit for non-ASCII passwords.
    if len(password.encode("utf-8")) > 72:
        raise errors.bad_request.ValidationError(
            "password must be at most 72 UTF-8 bytes", field="password"
        )
    requirements = (
        ("require_uppercase", r"[A-Z]", "an uppercase letter"),
        ("require_lowercase", r"[a-z]", "a lowercase letter"),
        ("require_number", r"[0-9]", "a number"),
        ("require_special", r"[^A-Za-z0-9]", "a special character"),
    )
    for option, pattern, description in requirements:
        if policy.get(option, False) and not re.search(pattern, password):
            raise errors.bad_request.ValidationError(
                f"password must contain {description}", field="password"
            )


def hash_password(password: str) -> str:
    validate_password(password)
    rounds = int(config.get("apiserver.auth.iam.password_policy.bcrypt_rounds", 12))
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds)).decode(
        "ascii"
    )


def generate_temporary_password() -> str:
    min_length = int(
        config.get("apiserver.auth.iam.password_policy.min_length", 12)
    )
    # The fixed prefix satisfies every optional character-class rule. Keep the
    # generated value inside bcrypt's 72-byte limit.
    length = min(72, max(16, min_length))
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-"
    return "Aa1!" + "".join(secrets.choice(alphabet) for _ in range(length - 4))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("ascii")
        )
    except (TypeError, ValueError):
        return False


def audit(
    action: str,
    company: str,
    target_type: str,
    target_id: str = None,
    actor: Optional[AuthUser] = None,
    call=None,
    metadata: dict = None,
    actor_username: str = None,
) -> None:
    if not config.get("apiserver.auth.iam.audit.enabled", True):
        return
    safe_metadata = {
        key: value
        for key, value in (metadata or {}).items()
        if key.lower() not in {"password", "password_hash", "token", "secret", "api_key"}
    }
    IAMAuditEvent(
        id=database.utils.id(),
        company=company,
        timestamp=datetime.utcnow(),
        actor_user_id=actor.id if actor else None,
        actor_username=(actor.username if actor else actor_username),
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=safe_metadata,
        source_ip=call.real_ip if call else None,
        user_agent=(call.headers.get("User-Agent") if call else None),
    ).save()


def serialize_user(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.name,
        "role": user.role,
        "status": user.status or "active",
        "must_change_password": bool(user.must_change_password),
        "created_at": user.created,
        "updated_at": user.updated,
        "created_by": user.created_by,
        "last_login_at": user.validated,
        "last_login_ip": user.last_login_ip,
        "password_changed_at": user.password_changed_at,
        "failed_login_count": user.failed_login_count or 0,
        "locked_until": user.locked_until,
        "auth_version": user.auth_version or 1,
    }


def create_user(
    *,
    company: str,
    username: str,
    password: str,
    display_name: str = None,
    email: str = None,
    role: str = Role.user,
    must_change_password: bool = True,
    created_by: str = None,
) -> AuthUser:
    username = validate_username(username)
    if role not in (Role.admin, Role.user):
        raise errors.bad_request.ValidationError("role must be admin or user", field="role")
    password_hash = hash_password(password)
    now = datetime.utcnow()
    user = AuthUser(
        id=database.utils.id(),
        username=username,
        password_hash=password_hash,
        name=(display_name or username).strip(),
        email=email or None,
        company=company,
        role=role,
        status="active",
        must_change_password=bool(must_change_password),
        created=now,
        updated=now,
        password_changed_at=now,
        created_by=created_by,
        auth_version=1,
    )
    try:
        user.save()
    except NotUniqueError:
        raise errors.bad_request.FieldsValueError(
            "username or email already exists", field="username"
        )
    given_name, _, family_name = user.name.partition(" ")
    try:
        BackendUser(
            id=user.id,
            company=company,
            name=user.name,
            given_name=given_name,
            family_name=family_name or given_name,
            created=now,
            created_in_version=get_version(),
        ).save()
    except Exception:
        user.delete()
        raise
    return user


def set_password(user: AuthUser, password: str, must_change: bool) -> None:
    new_hash = hash_password(password)
    history_size = int(
        config.get("apiserver.auth.iam.password_policy.history", 0)
    )
    old_hashes = [user.password_hash] + list(user.password_history or [])
    if any(verify_password(password, old_hash) for old_hash in old_hashes if old_hash):
        raise errors.bad_request.ValidationError(
            "new password was used recently", field="password"
        )
    user.password_history = [h for h in old_hashes if h][:history_size]
    user.password_hash = new_hash
    user.password_changed_at = datetime.utcnow()
    user.updated = datetime.utcnow()
    user.must_change_password = must_change
    user.auth_version = (user.auth_version or 1) + 1
    user.failed_login_count = 0
    user.locked_until = None
    user.save()
