from apiserver.bll.project.assistant import ask_project, get_project
from apiserver.bll.project.access import require_write, require_project_path_write
from apiserver.bll.task import TaskBLL
from apiserver.database.model import EntityVisibility
from apiserver.database.model.task.task import TaskType
from apiserver.service_repo import APICall, endpoint
from apiserver.services.reports import _ensure_reports_project, reports_tag, reports_project_name
from apiserver.apierrors import errors


@endpoint("project_ai.ask", validate_schema=True)
def ask(call: APICall, company: str, _):
    return ask_project(call.data["project"], company, call.identity, call.data["question"], call.data.get("history", []))


@endpoint("project_ai.generate_report", validate_schema=True)
def generate_report(call: APICall, company: str, _):
    return ask_project(call.data["project"], company, call.identity,
                       call.data.get("question") or "Summarize task progress and available metrics.",
                       call.data.get("history", []), report=True)


@endpoint("project_ai.save_report", validate_schema=True)
def save_report(call: APICall, company: str, _):
    project = get_project(call.data["project"], company, call.identity)
    require_write(project, call.identity)
    require_project_path_write(f"{project.name}/{reports_project_name}", company, call.identity)
    title = call.data["title"].strip()
    if len(title) < 3 or not call.data["content"].strip():
        raise errors.bad_request.ValidationError("A report needs a title and content")
    report_project = _ensure_reports_project(company, call.identity.user, project.name)
    task = TaskBLL.create(company, call.identity.user, {
        "project": report_project, "name": title,
        "comment": "AI-generated project report", "report": call.data["content"],
        "type": TaskType.report, "tags": ["ai-generated"],
        "system_tags": [reports_tag, EntityVisibility.hidden.value],
    })
    task.save()
    return {"id": task.id, "project_id": report_project}
