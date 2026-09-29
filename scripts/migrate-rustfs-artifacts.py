#!/usr/bin/env python3
"""Copy existing model and task output artifacts to RustFS, then update their URIs.

Run from the Compose host after rustfs_init completes. Existing source files are kept.
"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parent.parent


def settings():
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def source_path(uri, files_root):
    parsed = urlsplit(uri)
    if parsed.scheme in ("http", "https") and parsed.port == 7863:
        path = (files_root / unquote(parsed.path).lstrip("/")).resolve()
        if not path.is_relative_to(files_root.resolve()):
            raise ValueError(f"File path escapes the fileserver root: {uri}")
        return path
    if parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
        return Path(unquote(parsed.path)).resolve()
    return None


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_verified(s3, bucket, key, path):
    expected = sha256(path)
    size = path.stat().st_size
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        if head["ContentLength"] == size and head.get("Metadata", {}).get("sha256") == expected:
            return
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
    s3.upload_file(str(path), bucket, key, ExtraArgs={"Metadata": {"sha256": expected}})
    head = s3.head_object(Bucket=bucket, Key=key)
    if head["ContentLength"] != size or head.get("Metadata", {}).get("sha256") != expected:
        raise RuntimeError(f"RustFS upload verification failed: {key}")
    actual = hashlib.sha256()
    response = s3.get_object(Bucket=bucket, Key=key)
    for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
        actual.update(chunk)
    if actual.hexdigest() != expected:
        raise RuntimeError(f"RustFS download verification failed: {key}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="copy and update the records")
    args = parser.parse_args()
    env = settings()
    bucket = env["RUSTFS_BUCKET"]
    endpoint = f"{env['RUSTFS_PUBLIC_HOST']}:{env.get('RUSTFS_API_PORT', '7868')}"
    output_uri = f"s3://{endpoint}/{bucket}"
    files_root = Path(env.get("CLEARML_DATA_ROOT", "./docker-data")).resolve() / "data/fileserver"
    mongo_host = os.getenv("RUSTFS_MONGO_HOST") or subprocess.check_output(
        ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", "clearml-local-mongo-1"],
        text=True,
    ).strip()
    db = MongoClient(mongo_host, 27017, serverSelectionTimeoutMS=5000).backend
    entries = []
    for model in db.model.find({}, {"uri": 1}):
        uri = model.get("uri") or ""
        path = source_path(uri, files_root)
        if path:
            key = f"migrated/models/{model['_id']}/{path.name}"
            entries.append(("model", model["_id"], None, uri, key, path))
    for task in db.task.find({}, {"execution.artifacts": 1}):
        for artifact_id, artifact in (task.get("execution", {}).get("artifacts") or {}).items():
            if artifact.get("mode") != "output":
                continue
            uri = artifact.get("uri") or ""
            path = source_path(uri, files_root)
            if path:
                key = f"migrated/task-artifacts/{task['_id']}/{artifact_id}/{path.name}"
                entries.append(("task", task["_id"], artifact_id, uri, key, path))
    for _, _, _, uri, _, path in entries:
        if not path.is_file():
            raise FileNotFoundError(f"Missing source for {uri}: {path}")
    print(f"{len(entries)} artifact files ready for migration; destination {output_uri}")
    if not args.apply:
        print("Dry run only. Pass --apply to copy verified files and update URIs.")
        return

    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "destination": output_uri,
        "artifacts": [
            {"type": kind, "id": entity_id, "artifact_id": artifact_id, "old_uri": old_uri,
             "new_uri": f"{output_uri}/{quote(key, safe='/')}"}
            for kind, entity_id, artifact_id, old_uri, key, _ in entries
        ],
    }
    config_dir = Path(env.get("CLEARML_DATA_ROOT", "./docker-data")).resolve() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / f"rustfs-migration-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    manifest_path.chmod(0o600)

    s3 = boto3.client(
        "s3", endpoint_url=f"http://127.0.0.1:{env.get('RUSTFS_API_PORT', '7868')}",
        aws_access_key_id=env["RUSTFS_ACCESS_KEY"], aws_secret_access_key=env["RUSTFS_SECRET_KEY"],
        region_name="us-east-1", config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    s3.head_bucket(Bucket=bucket)
    for kind, entity_id, artifact_id, old_uri, key, path in entries:
        upload_verified(s3, bucket, key, path)
        new_uri = f"{output_uri}/{quote(key, safe='/')}"
        if kind == "model":
            result = db.model.update_one({"_id": entity_id, "uri": old_uri}, {"$set": {"uri": new_uri}})
        else:
            field = f"execution.artifacts.{artifact_id}.uri"
            result = db.task.update_one({"_id": entity_id, field: old_uri}, {"$set": {field: new_uri}})
        if result.matched_count != 1:
            raise RuntimeError(f"Artifact changed during migration: {kind} {entity_id}")
    projects = db.project.update_many(
        {"$or": [{"default_output_destination": {"$exists": False}}, {"default_output_destination": None}, {"default_output_destination": ""}]},
        {"$set": {"default_output_destination": output_uri}},
    )
    tasks = db.task.update_many(
        {"$or": [{"output.destination": {"$exists": False}}, {"output.destination": None}, {"output.destination": ""}]},
        {"$set": {"output.destination": output_uri}},
    )
    print(f"Migrated {len(entries)} files; updated {projects.modified_count} project and {tasks.modified_count} task destinations")
    print(f"Rollback manifest: {manifest_path}")


if __name__ == "__main__":
    main()
