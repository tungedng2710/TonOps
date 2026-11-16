"""Prepare owned registry weights and a private credential mount for serving."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from clearml.backend_api.session import Session
import requests


def call(session, service, action, body):
    response = session.send_request(service=service, action=action, json=body)
    response.raise_for_status()
    envelope = response.json()
    if envelope.get("meta", {}).get("result_code", 200) != 200:
        raise RuntimeError(f"{service}.{action} was rejected")
    return envelope["data"]


def prepare(directory, model_specs):
    session = Session()
    user = call(session, "users", "get_current_user", {})["user"]
    if not session.access_key or not session.secret_key:
        raise RuntimeError("Configure this account's existing SDK API credentials first")
    directory.mkdir(parents=True, exist_ok=True)
    models = []
    for specification in model_specs:
        alias, model_id = specification.split("=", 1)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", alias):
            raise ValueError("Model aliases must use lowercase letters, digits, _ or -")
        if any(model["alias"] == alias for model in models):
            raise ValueError("Duplicate model alias")
        model = call(session, "models", "get_by_id", {"model": model_id})["model"]
        if model["user"] != user["id"]:
            raise RuntimeError("Only models owned by the configured account can be deployed")
        uri = model["uri"]
        if uri.startswith("s3://"):
            source = call(session, "storage", "sign_rustfs_url", {"url": uri})["signed"]
            if not source:
                raise RuntimeError("This example requires the registered RustFS artifact URL")
            headers = {}
        elif uri.startswith(session.get_files_server_host().rstrip("/") + "/"):
            source, headers = uri, {"Authorization": "Bearer " + session.token}
        else:
            raise RuntimeError("Unsupported model storage for this serving example")
        filename = alias + ".pt"
        temporary = directory / (filename + ".part")
        digest = hashlib.sha256()
        with requests.get(source, headers=headers, stream=True, timeout=60) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
        temporary.replace(directory / filename)
        models.append({"alias": alias, "id": model_id, "name": model["name"],
                       "project": model["project"], "user": user["id"], "uri": uri,
                       "file": filename, "sha256": digest.hexdigest(),
                       "bytes": (directory / filename).stat().st_size, "version": model_id[:8]})
        print(f"Prepared {alias}: {model['name']} ({model_id})", flush=True)
    descriptor = os.open(directory / "clearml-api.json", os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump({"api_url": session.host, "access_key": session.access_key,
                   "secret_key": session.secret_key, "user_id": user["id"]}, output)
    os.chmod(directory / "clearml-api.json", 0o600)
    (directory / "models.json").write_text(json.dumps({"models": models}, indent=2) + "\n")
    print(f"Prepared {len(models)} models for {user['name']}. Private credentials stay outside Git.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        default=Path(__file__).resolve().parents[2] / "docker-data/examples/yolo-serving")
    parser.add_argument("--model", action="append", required=True, metavar="ALIAS=MODEL_ID")
    args = parser.parse_args()
    prepare(args.directory.resolve(), args.model)
