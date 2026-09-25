from datetime import datetime

from dateutil.parser import parse as parse_datetime
from mongoengine import Q
from mongoengine.errors import NotUniqueError

from apiserver.apierrors import errors
from apiserver.bll.auth import AuthBLL
from apiserver.bll.iam import (
    audit,
    create_user as create_local_user,
    enabled,
    generate_temporary_password,
    self_signup_enabled,
    serialize_user,
    set_password,
    verify_password,
)
from apiserver.config_repo import config
from apiserver.database.model.auth import Role, User
from apiserver.database.model.iam import IAMAuditEvent, IAMGroup, IAMGroupMember
from apiserver.database.model.user import User as BackendUser
from apiserver.database import utils as database_utils
from apiserver.redis_manager import redman
from apiserver.service_repo import APICall, endpoint


redis = redman.connection("apiserver")
USER_SORT_FIELDS = {
    "username": "username",
    "display_name": "name",
    "role": "role",
    "status": "status",
    "last_login_at": "validated",
    "created_at": "created",
}
AUDIT_SORT_FIELDS = {"timestamp": "timestamp", "action": "action"}


def _require_enabled():
    if not enabled():
        raise errors.bad_request.NotSupported("local IAM is disabled")


def _actor(call: APICall) -> User:
    user = User.objects(id=call.identity.user, company=call.identity.company).first()
    if not user:
        raise errors.bad_request.InvalidUserId(user=call.identity.user)
    return user


def _user(user_id: str, company: str) -> User:
    user = User.objects(id=user_id, company=company, username__ne=None).first()
    if not user:
        raise errors.bad_request.InvalidUserId(user=user_id)
    return user


def _page(data: dict):
    page = max(0, int(data.get("page", 0)))
    page_size = min(200, max(1, int(data.get("page_size", 50))))
    return page, page_size


def _sort(data: dict, allowed: dict, default: str):
    requested = data.get("sort", default)
    descending = requested.startswith("-")
    field = requested[1:] if descending else requested
    if field not in allowed:
        raise errors.bad_request.ValidationError("invalid sort field", field="sort")
    return ("-" if descending else "+") + allowed[field]


def _last_active_admin(user: User) -> bool:
    return (
        user.role == Role.admin
        and user.status == "active"
        and User.objects(
            company=user.company,
            username__ne=None,
            role=Role.admin,
            status="active",
        ).count()
        <= 1
    )


def _protect_last_admin(user: User, *, role=None, status=None, deleting=False):
    removing_admin = deleting or role == Role.user or status == "disabled"
    if removing_admin and _last_active_admin(user):
        raise errors.bad_request.FieldsValueError(
            "cannot disable, delete, or downgrade the last active administrator",
            user=user.id,
        )


@endpoint("iam.status", validate_schema=True)
def status(call: APICall, company_id: str, _):
    return {
        "enabled": enabled(),
        "self_signup_enabled": self_signup_enabled(),
    }


@endpoint("iam.signup", validate_schema=True)
def signup(call: APICall, company_id: str, _):
    _require_enabled()
    if not self_signup_enabled():
        raise errors.bad_request.NotSupported("self-service signup is disabled")

    data = call.data
    company_id = company_id or config.get("apiserver.default_company")
    user = create_local_user(
        company=company_id,
        username=data["username"],
        password=data["password"],
        display_name=data.get("display_name"),
        email=data["email"],
        # This is intentionally not client-controlled. Only an authenticated
        # administrator may grant the admin role through iam.update_user.
        role=Role.user,
        must_change_password=False,
        created_by="self_signup",
    )
    audit(
        "USER_SIGNED_UP",
        company_id,
        "user",
        user.id,
        actor=user,
        call=call,
        metadata={"username": user.username, "role": Role.user},
    )
    return {"user": serialize_user(user)}


@endpoint("iam.me", validate_schema=True)
def me(call: APICall, company_id: str, _):
    _require_enabled()
    user = _actor(call)
    result = serialize_user(user)
    result["groups"] = list(
        IAMGroupMember.objects(company=company_id, user_id=user.id).scalar("group_id")
    )
    return {"user": result}


@endpoint("iam.list_users", validate_schema=True)
def list_users(call: APICall, company_id: str, _):
    _require_enabled()
    data = call.data
    page, page_size = _page(data)
    query = Q(company=company_id) & Q(username__ne=None)
    search = (data.get("search") or "").strip()
    if search:
        query &= Q(username__icontains=search) | Q(name__icontains=search) | Q(
            email__icontains=search
        )
    if data.get("role"):
        query &= Q(role=data["role"])
    if data.get("status"):
        query &= Q(status=data["status"])
    users = User.objects(query)
    total = users.count()
    items = users.order_by(_sort(data, USER_SORT_FIELDS, "username"))[
        page * page_size : (page + 1) * page_size
    ]
    return {
        "users": [serialize_user(user) for user in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@endpoint("iam.get_user", validate_schema=True)
def get_user(call: APICall, company_id: str, _):
    _require_enabled()
    user = _user(call.data["user_id"], company_id)
    result = serialize_user(user)
    result["groups"] = list(
        IAMGroupMember.objects(company=company_id, user_id=user.id).scalar("group_id")
    )
    return {"user": result}


@endpoint("iam.create_user", validate_schema=True)
def create_user(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    data = call.data
    user = create_local_user(
        company=company_id,
        username=data["username"],
        password=data["password"],
        display_name=data.get("display_name"),
        email=data.get("email"),
        role=data.get("role", Role.user),
        must_change_password=data.get("must_change_password", True),
        created_by=actor.id,
    )
    audit(
        "USER_CREATED",
        company_id,
        "user",
        user.id,
        actor=actor,
        call=call,
        metadata={"username": user.username, "role": user.role},
    )
    return {"user": serialize_user(user)}


@endpoint("iam.update_user", validate_schema=True)
def update_user(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    data = call.data
    user = _user(data["user_id"], company_id)
    changes = {}
    if "display_name" in data:
        changes["name"] = data["display_name"].strip()
    if "email" in data:
        changes["email"] = data["email"] or None
    if "role" in data:
        if data["role"] not in (Role.admin, Role.user):
            raise errors.bad_request.ValidationError("role must be admin or user")
        changes["role"] = data["role"]
    if "status" in data:
        changes["status"] = data["status"]
    if not changes:
        return {"user": serialize_user(user)}

    with redis.lock(f"iam:last-admin:{company_id}", timeout=10, blocking_timeout=5):
        _protect_last_admin(user, role=changes.get("role"), status=changes.get("status"))
        critical = any(
            changes.get(key) is not None and changes[key] != getattr(user, key)
            for key in ("role", "status")
        )
        old_role = user.role
        old_status = user.status
        for key, value in changes.items():
            setattr(user, key, value)
        user.updated = datetime.utcnow()
        if critical:
            user.auth_version = (user.auth_version or 1) + 1
        try:
            user.save()
        except NotUniqueError:
            raise errors.bad_request.FieldsValueError("email already exists", field="email")

    if "name" in changes:
        BackendUser.objects(id=user.id, company=company_id).update_one(
            set__name=user.name
        )
    audit(
        "USER_UPDATED",
        company_id,
        "user",
        user.id,
        actor=actor,
        call=call,
        metadata={"fields": sorted(changes)},
    )
    if old_role != user.role:
        audit(
            "ROLE_CHANGED",
            company_id,
            "user",
            user.id,
            actor=actor,
            call=call,
            metadata={"from": old_role, "to": user.role},
        )
    if old_status != user.status:
        audit(
            "USER_ENABLED" if user.status == "active" else "USER_DISABLED",
            company_id,
            "user",
            user.id,
            actor=actor,
            call=call,
        )
    return {"user": serialize_user(user)}


def _set_status(call: APICall, company_id: str, status: str):
    _require_enabled()
    actor = _actor(call)
    user = _user(call.data["user_id"], company_id)
    with redis.lock(f"iam:last-admin:{company_id}", timeout=10, blocking_timeout=5):
        _protect_last_admin(user, status=status)
        if user.status != status:
            user.status = status
            user.updated = datetime.utcnow()
            user.auth_version = (user.auth_version or 1) + 1
            user.save()
    action = "USER_ENABLED" if status == "active" else "USER_DISABLED"
    audit(action, company_id, "user", user.id, actor=actor, call=call)
    return {"user": serialize_user(user)}


@endpoint("iam.disable_user", validate_schema=True)
def disable_user(call: APICall, company_id: str, _):
    return _set_status(call, company_id, "disabled")


@endpoint("iam.enable_user", validate_schema=True)
def enable_user(call: APICall, company_id: str, _):
    return _set_status(call, company_id, "active")


@endpoint("iam.delete_user", validate_schema=True)
def delete_user(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    user = _user(call.data["user_id"], company_id)
    if user.id == actor.id:
        raise errors.bad_request.FieldsValueError("cannot delete yourself")
    with redis.lock(f"iam:last-admin:{company_id}", timeout=10, blocking_timeout=5):
        _protect_last_admin(user, deleting=True)
        IAMGroupMember.objects(company=company_id, user_id=user.id).delete()
        BackendUser.objects(company=company_id, id=user.id).delete()
        user.delete()
    audit(
        "USER_DELETED",
        company_id,
        "user",
        user.id,
        actor=actor,
        call=call,
        metadata={"username": user.username},
    )
    return {"deleted": 1}


@endpoint("iam.reset_password", validate_schema=True)
def reset_password(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    user = _user(call.data["user_id"], company_id)
    generated = "password" not in call.data
    temporary_password = call.data.get("password") or generate_temporary_password()
    set_password(user, temporary_password, must_change=True)
    audit("PASSWORD_RESET", company_id, "user", user.id, actor=actor, call=call)
    result = {"updated": 1, "must_change_password": True}
    if generated:
        result["temporary_password"] = temporary_password
    return result


@endpoint("iam.change_password", validate_schema=True)
def change_password(call: APICall, company_id: str, _):
    _require_enabled()
    user = _actor(call)
    if not verify_password(call.data["current_password"], user.password_hash):
        raise errors.unauthorized.InvalidCredentials("invalid username or password")
    set_password(user, call.data["new_password"], must_change=False)
    audit("PASSWORD_CHANGED", company_id, "user", user.id, actor=user, call=call)
    token = AuthBLL.get_token_for_user(user.id, company_id).token
    call.result.set_auth_cookie(token)
    return {"updated": 1}


def _group(group_id: str, company: str) -> IAMGroup:
    group = IAMGroup.objects(id=group_id, company=company).first()
    if not group:
        raise errors.bad_request.InvalidId(group=group_id)
    return group


def _validate_group_name(name: str) -> str:
    name = (name or "").strip()
    if not 1 <= len(name) <= 64:
        raise errors.bad_request.ValidationError("group name must be 1-64 characters")
    return name


def _serialize_group(group: IAMGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "created_by": group.created_by,
        "member_count": IAMGroupMember.objects(group_id=group.id).count(),
    }


@endpoint("iam.list_groups", validate_schema=True)
def list_groups(call: APICall, company_id: str, _):
    _require_enabled()
    page, page_size = _page(call.data)
    groups = IAMGroup.objects(company=company_id)
    search = (call.data.get("search") or "").strip()
    if search:
        groups = groups.filter(Q(name__icontains=search) | Q(description__icontains=search))
    total = groups.count()
    items = groups.order_by("+name")[page * page_size : (page + 1) * page_size]
    return {
        "groups": [_serialize_group(group) for group in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@endpoint("iam.get_group", validate_schema=True)
def get_group(call: APICall, company_id: str, _):
    _require_enabled()
    group = _group(call.data["group_id"], company_id)
    member_ids = list(IAMGroupMember.objects(group_id=group.id).scalar("user_id"))
    users = User.objects(id__in=member_ids)
    result = _serialize_group(group)
    result["members"] = [serialize_user(user) for user in users]
    return {"group": result}


@endpoint("iam.create_group", validate_schema=True)
def create_group(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    now = datetime.utcnow()
    group = IAMGroup(
        id=database_utils.id(),
        company=company_id,
        name=_validate_group_name(call.data["name"]),
        description=(call.data.get("description") or "").strip(),
        created_at=now,
        updated_at=now,
        created_by=actor.id,
    )
    try:
        group.save()
    except NotUniqueError:
        raise errors.bad_request.FieldsValueError("group name already exists")
    audit("GROUP_CREATED", company_id, "group", group.id, actor=actor, call=call)
    return {"group": _serialize_group(group)}


@endpoint("iam.update_group", validate_schema=True)
def update_group(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    group = _group(call.data["group_id"], company_id)
    if "name" in call.data:
        group.name = _validate_group_name(call.data["name"])
    if "description" in call.data:
        group.description = (call.data["description"] or "").strip()
    group.updated_at = datetime.utcnow()
    try:
        group.save()
    except NotUniqueError:
        raise errors.bad_request.FieldsValueError("group name already exists")
    audit("GROUP_UPDATED", company_id, "group", group.id, actor=actor, call=call)
    return {"group": _serialize_group(group)}


@endpoint("iam.delete_group", validate_schema=True)
def delete_group(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    group = _group(call.data["group_id"], company_id)
    IAMGroupMember.objects(group_id=group.id).delete()
    group.delete()
    audit("GROUP_DELETED", company_id, "group", group.id, actor=actor, call=call)
    return {"deleted": 1}


@endpoint("iam.add_group_member", validate_schema=True)
def add_group_member(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    group = _group(call.data["group_id"], company_id)
    user = _user(call.data["user_id"], company_id)
    try:
        IAMGroupMember(
            id=database_utils.id(),
            company=company_id,
            group_id=group.id,
            user_id=user.id,
            created_at=datetime.utcnow(),
            created_by=actor.id,
        ).save()
    except NotUniqueError:
        raise errors.bad_request.FieldsValueError("user is already a group member")
    audit(
        "GROUP_MEMBER_ADDED",
        company_id,
        "group",
        group.id,
        actor=actor,
        call=call,
        metadata={"user_id": user.id},
    )
    return {"added": 1}


@endpoint("iam.remove_group_member", validate_schema=True)
def remove_group_member(call: APICall, company_id: str, _):
    _require_enabled()
    actor = _actor(call)
    group = _group(call.data["group_id"], company_id)
    removed = IAMGroupMember.objects(
        company=company_id, group_id=group.id, user_id=call.data["user_id"]
    ).delete()
    audit(
        "GROUP_MEMBER_REMOVED",
        company_id,
        "group",
        group.id,
        actor=actor,
        call=call,
        metadata={"user_id": call.data["user_id"]},
    )
    return {"removed": removed}


@endpoint("iam.list_audit", validate_schema=True)
def list_audit(call: APICall, company_id: str, _):
    _require_enabled()
    page, page_size = _page(call.data)
    query = Q(company=company_id)
    for field in ("actor_user_id", "action", "target_type", "target_id"):
        if call.data.get(field):
            query &= Q(**{field: call.data[field]})
    if call.data.get("from_timestamp"):
        query &= Q(timestamp__gte=parse_datetime(call.data["from_timestamp"]))
    if call.data.get("to_timestamp"):
        query &= Q(timestamp__lte=parse_datetime(call.data["to_timestamp"]))
    events = IAMAuditEvent.objects(query)
    total = events.count()
    items = events.order_by(_sort(call.data, AUDIT_SORT_FIELDS, "-timestamp"))[
        page * page_size : (page + 1) * page_size
    ]
    return {
        "events": [event.to_proper_dict() for event in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
