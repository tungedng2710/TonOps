"""Owner-scoped project access for local IAM users."""

from mongoengine import Q

from apiserver.apierrors import errors
from apiserver.bll.iam import enabled as iam_enabled
from apiserver.database.model.auth import Role
from apiserver.database.model.project import Project


def restricted(identity):
    return iam_enabled() and identity.role not in (Role.admin, Role.root, Role.system)


def readable_query(identity):
    return Q(user=identity.user) | Q(visibility="public") | Q(visibility=None)


def can_read(project, identity):
    return not restricted(identity) or project.user == identity.user or project.visibility != "private"


def can_write(project, identity):
    return not restricted(identity) or project.user == identity.user


def require_read(project, identity):
    if not can_read(project, identity):
        raise errors.bad_request.InvalidProjectId("project is private", id=project.id)


def require_write(project, identity):
    if not can_write(project, identity):
        raise errors.bad_request.InvalidProjectId("only the project owner can change this project", id=project.id)


def readable_project_ids(company, identity):
    query = Q(company=company)
    if restricted(identity):
        query &= readable_query(identity)
    return list(Project.objects(query).scalar("id"))


def constrain_project_filter(data, company, identity):
    """Intersect expanded subproject filters with the viewer's projects."""
    if not restricted(identity):
        return
    allowed = set(readable_project_ids(company, identity))
    requested = data.get("project")
    if requested:
        allowed &= {requested} if isinstance(requested, str) else set(requested)
    data["project"] = list(allowed) or ["__no_accessible_project__"]


def require_project_path_write(name, company, identity):
    parts = (name or "").split("/")
    for index in range(1, len(parts) + 1):
        project = Project.objects(company=company, name="/".join(parts[:index])).first()
        if project:
            require_write(project, identity)


def authorize_entity_call(call, endpoint_name, company):
    """Apply the IAM project boundary before task/model endpoints execute.

    These endpoints predate user-scoped projects and normally authorize only
    by company. Keep the check in one place so direct API calls are covered.
    """
    if not restricted(call.identity) or not company:
        return
    service, _, action = endpoint_name.partition(".")
    if service not in ("projects", "tasks", "models", "events", "reports"):
        return

    if action in ("make_public", "make_private"):
        raise errors.bad_request.InvalidId("use project visibility settings")

    data = call.data
    read_only = action.startswith(("get_", "list_", "validate_"))
    if service == "projects":
        if action not in ("create", "get_all", "get_all_ex", "get_by_id", "authorize_file"):
            project_ids = []
            for field in ("project", "source", "destination", "ids"):
                value = data.get(field)
                if value:
                    project_ids.extend(value if isinstance(value, list) else [value])
            for project in Project.objects(id__in=project_ids, company=company):
                (require_read if read_only else require_write)(project, call.identity)
        return

    if data.get("project_name"):
        require_project_path_write(data["project_name"], company, call.identity)

    from apiserver.database.model.model import Model
    from apiserver.database.model.task.task import Task

    if service == "events":
        read_only = action not in ("add", "add_batch", "delete_for_task", "delete_for_model", "clear_task_log")
        records = call.batched_data if action == "add_batch" else [data]
        ids = []
        for record in records:
            for field in ("task", "tasks", "model"):
                value = record.get(field)
                if value:
                    ids.extend(value if isinstance(value, list) else [value])
        if not ids and action != "clear_scroll":
            raise errors.bad_request.InvalidId("task is required")
        for entity_id in set(ids):
            entity = Task.objects(id=entity_id, company=company).first() or Model.objects(id=entity_id, company=company).first()
            if not entity:
                raise errors.bad_request.InvalidId("entity is not accessible")
            project = Project.objects(id=entity.project, company=company).first()
            if project:
                (require_read if read_only else require_write)(project, call.identity)
            elif entity.user != call.identity.user:
                raise errors.bad_request.InvalidId("entity is not accessible")
        return

    entity_class = Model if service == "models" else Task

    if data.get("public"):
        raise errors.bad_request.InvalidId("global public entities are unavailable with local IAM")

    if service == "models" and action == "get_by_task_id":
        task = Task.objects(id=data.get("task"), company=company).first()
        if not task:
            raise errors.bad_request.InvalidId("task is not accessible")
        project = Project.objects(id=task.project, company=company).first()
        if project:
            require_read(project, call.identity)
        elif task.user != call.identity.user:
            raise errors.bad_request.InvalidId("task is not accessible")
        return

    if action in ("get_all", "get_all_ex", "get_task_data"):
        constrain_project_filter(data, company, call.identity)
        return

    identifiers = []
    if service == "tasks" and action == "update_batch":
        for item in call.batched_data or []:
            entity_id = item.get("task") or item.get("id")
            if entity_id:
                identifiers.append(entity_id)
    id_fields = ("model", "id", "models", "ids") if service == "models" else ("task", "id", "tasks", "ids")
    for field in id_fields:
        value = data.get(field)
        if value:
            identifiers.extend(value if isinstance(value, list) else [value])
    if identifiers:
        entities = list(entity_class.objects(id__in=identifiers, company=company).only("id", "project", "user"))
        if len(entities) != len(set(identifiers)):
            raise errors.bad_request.InvalidId("entity is not accessible")
        projects = {p.id: p for p in Project.objects(id__in=[e.project for e in entities if e.project], company=company)}
        for entity in entities:
            project = projects.get(entity.project)
            if project:
                (require_read if read_only else require_write)(project, call.identity)
            elif entity.user != call.identity.user:
                raise errors.bad_request.InvalidId("entity is not accessible")

    if service == "models" and data.get("task"):
        task = Task.objects(id=data["task"], company=company).first()
        if not task:
            raise errors.bad_request.InvalidId("task is not accessible")
        task_project = Project.objects(id=task.project, company=company).first()
        if task_project:
            (require_read if read_only else require_write)(task_project, call.identity)
        elif task.user != call.identity.user:
            raise errors.bad_request.InvalidId("task is not accessible")

    if service == "tasks" and data.get("projects"):
        allowed = set(readable_project_ids(company, call.identity))
        if any(project_id not in allowed for project_id in data["projects"]):
            raise errors.bad_request.InvalidProjectId("project is private")

    project_id = data.get("project") if action not in ("get_all", "get_all_ex") else None
    if project_id and isinstance(project_id, str):
        project = Project.objects(id=project_id, company=company).first()
        if not project:
            raise errors.bad_request.InvalidProjectId(id=project_id)
        (require_read if read_only else require_write)(project, call.identity)
