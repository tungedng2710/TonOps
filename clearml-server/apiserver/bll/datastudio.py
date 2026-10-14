import fcntl
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography.fernet import Fernet, InvalidToken

from apiserver.apierrors import APIError, errors
from apiserver.database.model.datastudio import DataStudioConnection


def unavailable(message):
    return APIError(code=503, subcode=0, msg=message)


def _url(value):
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise unavailable("The DataStudio service URL is not configured correctly.")
    return value


def api_url():
    value = os.environ.get("DATASTUDIO_API_URL", "").strip()
    if not value:
        raise unavailable("DataStudio is not configured. Ask your administrator to set DATASTUDIO_API_URL.")
    return _url(value)


def web_url():
    return _url(os.environ.get("DATASTUDIO_WEB_URL", "http://localhost:3000"))


def cipher():
    """Use a deployment key or generate one in the persistent API config volume."""
    key = os.environ.get("DATASTUDIO_TOKEN_KEY", "").strip()
    try:
        if not key:
            path = Path(os.environ.get("DATASTUDIO_TOKEN_KEY_FILE", "/opt/clearml/config/datastudio-token.key"))
            path.parent.mkdir(parents=True, exist_ok=True)
            # Multiple gunicorn workers may establish their first connection at
            # once. Lock both creation and reading so none sees a partial key.
            fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
            with os.fdopen(fd, "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if not path.exists():
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as target:
                        target.write(Fernet.generate_key())
                key = path.read_bytes().strip()
        return Fernet(key)
    except (OSError, ValueError, TypeError):
        raise unavailable("DataStudio credential storage is unavailable. Check the API server's encryption key configuration.") from None


def connection(company, user):
    return DataStudioConnection.objects(company=company, user=user).first()


def status(company, user):
    saved = connection(company, user)
    current_url = api_url() if os.environ.get("DATASTUDIO_API_URL", "").strip() else None
    return {
        "configured": current_url is not None,
        "connected": bool(saved and saved.api_url == current_url),
        "username": saved.username if saved else None,
        "checked_at": saved.checked_at.isoformat() + "Z" if saved else None,
        "web_url": web_url(),
    }


def request(token, path, base_url=None):
    base_url = base_url or api_url()
    try:
        with requests.Session() as client:
            # The configured local service should not inherit proxy routing or
            # .netrc credentials. Never follow redirects with the user's token.
            client.trust_env = False
            response = client.get(base_url + path, headers={"Authorization": "Bearer " + token},
                                  timeout=(5, 20), allow_redirects=False)
        if response.status_code in (401, 403):
            raise errors.bad_request.ValidationError("DataStudio rejected the token. Check that it is valid and has read access.")
        if response.status_code == 404:
            raise errors.bad_request.ValidationError("The DataStudio dataset or API endpoint is unavailable to this account.")
        if response.status_code != 200:
            raise unavailable("DataStudio could not complete the request. Please try again.")
        return response.json()
    except requests.Timeout:
        raise unavailable("DataStudio took too long to respond. Please try again.") from None
    except (requests.RequestException, ValueError):
        # Upstream response bodies and exception URLs can contain credentials.
        raise unavailable("Cannot connect to DataStudio. Check the service and its API URL.") from None


def verify(token, username, base_url):
    account = request(token, "/auth/me", base_url)
    if not isinstance(account, dict) or not isinstance(account.get("username"), str):
        raise unavailable("DataStudio returned an invalid account response.")
    if account["username"].lower() != username:
        raise errors.bad_request.ValidationError("The token belongs to a different DataStudio username.")


def parse_credentials(data):
    token = data.pop("token", None)
    if set(data) != {"username"}:
        raise errors.bad_request.ValidationError("Provide only your DataStudio username and token.")
    return data.get("username"), token


def connect(company, user, username, token):
    if not isinstance(username, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", username.strip().lower()):
        raise errors.bad_request.ValidationError("Enter a valid DataStudio username.")
    username = username.strip().lower()
    if not isinstance(token, str) or not re.fullmatch(r"ds_pat_[A-Za-z0-9_-]{20,200}", token.strip()):
        raise errors.bad_request.ValidationError("Enter a valid DataStudio personal API token.")
    token = token.strip()
    base_url = api_url()
    verify(token, username, base_url)
    _dataset_items(request(token, "/datasets", base_url))
    encrypted = cipher().encrypt(token.encode()).decode()
    identity = hashlib.sha256((company + "\0" + user).encode()).hexdigest()
    DataStudioConnection.objects(id=identity, company=company, user=user).modify(
        upsert=True, new=True, set__username=username, set__encrypted_token=encrypted,
        set__api_url=base_url, set__checked_at=datetime.utcnow(),
    )
    return status(company, user)


def disconnect(company, user):
    DataStudioConnection.objects(company=company, user=user).delete()
    return status(company, user)


def _credentials(company, user):
    saved = connection(company, user)
    if not saved:
        raise errors.bad_request.ValidationError("Connect your DataStudio account first.")
    base_url = api_url()
    if saved.api_url != base_url:
        raise errors.bad_request.ValidationError("The DataStudio server has changed. Connect your account again.")
    try:
        token = cipher().decrypt(saved.encrypted_token.encode()).decode()
    except (InvalidToken, UnicodeError):
        raise unavailable("The saved DataStudio token cannot be read. Connect your account again.") from None
    return saved, token, base_url


DATASET_FIELDS = ("id", "namespace", "slug", "description", "visibility", "data_stage", "tags", "updated_at")
REVISION_FIELDS = ("revision_id", "status", "data_stage", "commit_message", "created_at", "manifest_sha256")


def _dataset_items(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise unavailable("DataStudio returned an invalid dataset response.")
    items = []
    for item in payload["items"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ("id", "namespace", "slug")):
            raise unavailable("DataStudio returned an invalid dataset response.")
        result = {key: item.get(key) for key in DATASET_FIELDS}
        revision = item.get("latest_revision")
        result["latest_revision"] = {key: revision.get(key) for key in REVISION_FIELDS} if isinstance(revision, dict) else None
        items.append(result)
    return items


def datasets(company, user):
    saved, token, base_url = _credentials(company, user)
    verify(token, saved.username, base_url)
    items = _dataset_items(request(token, "/datasets", base_url))
    saved.update(set__checked_at=datetime.utcnow())
    return {"items": items, "connection": status(company, user)}


def revisions(company, user, namespace, dataset):
    if not isinstance(namespace, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", namespace):
        raise errors.bad_request.ValidationError("Invalid DataStudio namespace.")
    if not isinstance(dataset, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,95}", dataset):
        raise errors.bad_request.ValidationError("Invalid DataStudio dataset name.")
    saved, token, base_url = _credentials(company, user)
    verify(token, saved.username, base_url)
    payload = request(token, f"/datasets/{namespace}/{dataset}/revisions", base_url)
    if not isinstance(payload, list) or any(not isinstance(r, dict) or not isinstance(r.get("revision_id"), str) for r in payload):
        raise unavailable("DataStudio returned an invalid revision response.")
    return {"revisions": [{key: revision.get(key) for key in REVISION_FIELDS} for revision in payload]}
