import base64
import os
from pathlib import Path

import bcrypt

from apiserver.bll.iam import audit, create_user, enabled, generate_temporary_password
from apiserver.database.model.auth import Role, User
from apiserver.service_repo.auth.fixed_user import FixedUser


def _read_bootstrap_password():
    password = os.getenv("CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD")
    password_file = os.getenv("CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD_FILE")
    if password and password_file:
        raise ValueError("set only one bootstrap password source")
    if password_file:
        password = Path(password_file).read_text(encoding="utf-8").rstrip("\r\n")
    return password


def _bootstrap_admin(company_id, log):
    username = os.getenv("CLEARML_IAM_BOOTSTRAP_ADMIN_USERNAME")
    password = _read_bootstrap_password()
    if not username and not password:
        return
    if not username or not password:
        raise ValueError("both bootstrap admin username and password are required")
    if User.objects(company=company_id, username__ne=None, role=Role.admin).first():
        log.info("Skipping IAM bootstrap: an administrator already exists")
        return
    user = create_user(
        company=company_id,
        username=username,
        password=password,
        display_name=os.getenv("CLEARML_IAM_BOOTSTRAP_ADMIN_DISPLAY_NAME", username),
        email=os.getenv("CLEARML_IAM_BOOTSTRAP_ADMIN_EMAIL") or None,
        role=Role.admin,
        must_change_password=True,
        created_by="bootstrap",
    )
    audit(
        "USER_CREATED",
        company_id,
        "user",
        user.id,
        actor_username="bootstrap",
        metadata={"username": user.username, "role": user.role},
    )
    log.info("Created local IAM bootstrap administrator '%s'", user.username)


def _import_fixed_users(company_id, log):
    from apiserver.config_repo import config

    if not config.get("apiserver.auth.iam.import_fixed_users", False):
        return
    if not FixedUser.enabled():
        log.info("IAM fixed-user import requested, but fixed_users is disabled")
        return
    for fixed in FixedUser.from_config():
        if fixed.is_guest or User.objects(username=fixed.username.lower()).first():
            continue
        if FixedUser.pass_hashed():
            # The legacy format is base64(bcrypt). bcrypt hashes are directly
            # compatible with local IAM and need not be re-hashed.
            decoded_hash = base64.b64decode(fixed.password.encode("ascii")).decode("ascii")
            user = create_user(
                company=fixed.company or company_id,
                username=fixed.username,
                password=generate_temporary_password(),
                display_name=fixed.name,
                role=Role.user,
                must_change_password=False,
                created_by="fixed_users_import",
            )
            user.password_hash = decoded_hash
            user.save()
        else:
            user = create_user(
                company=fixed.company or company_id,
                username=fixed.username,
                password=generate_temporary_password(),
                display_name=fixed.name,
                role=Role.user,
                must_change_password=True,
                created_by="fixed_users_import",
            )
            user.password_hash = bcrypt.hashpw(
                fixed.password.encode("utf-8")[:72], bcrypt.gensalt()
            ).decode("ascii")
            user.save()
        audit(
            "USER_CREATED",
            user.company,
            "user",
            user.id,
            actor_username="fixed_users_import",
            metadata={"username": user.username, "source": "fixed_users"},
        )
        log.info("Imported fixed user '%s' into local IAM", user.username)


def initialize_local_iam(company_id, log):
    if not enabled():
        return
    _import_fixed_users(company_id, log)
    _bootstrap_admin(company_id, log)
