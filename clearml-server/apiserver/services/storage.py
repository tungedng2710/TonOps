import os
import re
from urllib.parse import unquote, urlsplit

import boto3
from botocore.config import Config as BotoConfig

from apiserver.apimodels.storage import ResetSettingsRequest, SetSettingsRequest
from apiserver.apierrors import errors
from apiserver.bll.project.access import can_read
from apiserver.bll.storage import StorageBLL
from apiserver.database.model.model import Model
from apiserver.database.model.project import Project
from apiserver.database.model.task.task import Task
from apiserver.service_repo import endpoint, APICall

storage_bll = StorageBLL()


@endpoint("storage.sign_rustfs_url", validate_schema=True)
def sign_rustfs_url(call: APICall, company: str, _):
    """Presign only registered model or task artifacts visible to this user."""
    url = call.data["url"]
    parsed = urlsplit(url)
    host = os.getenv("RUSTFS_PUBLIC_HOST")
    port = os.getenv("RUSTFS_API_PORT", "7868")
    bucket = os.getenv("RUSTFS_BUCKET")
    if not host or not bucket or parsed.scheme != "s3" or parsed.netloc != f"{host}:{port}":
        return {"signed": None}
    path = unquote(parsed.path).lstrip("/")
    if not path.startswith(f"{bucket}/") or path == f"{bucket}/":
        raise errors.bad_request.InvalidId("invalid RustFS artifact URL")

    entities = list(Model.objects(company=company, uri=url).only("project", "user"))
    if not entities:
        task_ids = set(re.findall(r"\.([a-f0-9]{32})(?:/|$)", path))
        task_ids.update(re.findall(r"task-artifacts/([a-f0-9]{32})/", path))
        for task in Task.objects(company=company, id__in=task_ids).only("project", "user", "execution"):
            artifacts = task.execution.artifacts if task.execution else {}
            if any(artifact.uri == url for artifact in artifacts.values()):
                entities.append(task)
    if not entities:
        raise errors.bad_request.InvalidId("artifact is unavailable")

    allowed = False
    for entity in entities:
        project = Project.objects(id=entity.project, company=company).first()
        if (project and can_read(project, call.identity)) or (
            not project and entity.user == call.identity.user
        ):
            allowed = True
            break
    if not allowed:
        raise errors.bad_request.InvalidId("artifact is unavailable")

    client = boto3.client(
        "s3",
        endpoint_url=f"http://{host}:{port}",
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    return {
        "signed": client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": path[len(bucket) + 1:]}, ExpiresIn=300
        )
    }


@endpoint("storage.get_settings")
def get_settings(call: APICall, company: str, _):
    call.result.data = {"settings": storage_bll.get_company_settings(company)}


@endpoint("storage.set_settings")
def set_settings(call: APICall, company: str, request: SetSettingsRequest):
    call.result.data = {"updated": storage_bll.set_company_settings(company, request)}


@endpoint("storage.reset_settings")
def reset_settings(call: APICall, company: str, request: ResetSettingsRequest):
    call.result.data = {
        "updated": storage_bll.reset_company_settings(company, request.keys)
    }
