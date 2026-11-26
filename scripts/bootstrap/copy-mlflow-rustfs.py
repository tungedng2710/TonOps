"""Verify and copy legacy MLflow objects into the shared RustFS instance."""

import argparse
import hashlib
import os
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

BUCKETS = ("mlflow-artifacts", "ml-datasets", "ml-exports")
OBJECT_HEADERS = ("CacheControl", "ContentDisposition", "ContentEncoding", "ContentLanguage",
                  "ContentType", "Expires", "Metadata")


def client(endpoint: str, key: str, secret: str):
    return boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=key, aws_secret_access_key=secret,
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}, connect_timeout=5, read_timeout=60,
            retries={"total_max_attempts": 3},
        ),
    )


def digest_object(s3, bucket: str, key: str) -> str:
    digest = hashlib.sha256()
    with closing(s3.get_object(Bucket=bucket, Key=key)["Body"]) as stream:
        for chunk in stream.iter_chunks(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def copy_bucket(source, target, bucket: str, apply: bool) -> None:
    if source.get_bucket_versioning(Bucket=bucket).get("Status"):
        raise RuntimeError(f"{bucket}: migrate all object versions before switching")
    target.head_bucket(Bucket=bucket)
    count = size = copied = 0
    with TemporaryDirectory() as work:
        local = Path(work) / "object"
        for page in source.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for item in page.get("Contents", []):
                key = item["Key"]
                source_head = source.head_object(Bucket=bucket, Key=key)
                count += 1
                size += item["Size"]
                try:
                    target_head = target.head_object(Bucket=bucket, Key=key)
                except ClientError as error:
                    if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                        raise
                    copied += 1
                    if not apply:
                        continue
                    source.download_file(bucket, key, str(local))
                    with local.open("rb") as stream:
                        expected = hashlib.file_digest(stream, "sha256").hexdigest()
                    args = {field: source_head[field] for field in OBJECT_HEADERS if field in source_head}
                    # The cutover stops writers. Existing destination keys are always checked.
                    target.upload_file(str(local), bucket, key, ExtraArgs=args)
                    local.unlink()
                else:
                    if target_head["ContentLength"] != source_head["ContentLength"]:
                        raise RuntimeError(f"{bucket}: destination object size conflicts with source")
                    expected = digest_object(source, bucket, key)
                if digest_object(target, bucket, key) != expected:
                    raise RuntimeError(f"{bucket}: destination object checksum differs from source")
    operation = "copied" if apply else "to copy"
    print(f"{bucket}: {count} objects, {size} bytes, {copied} {operation}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.source.rstrip("/") == args.target.rstrip("/"):
        parser.error("source and target must be different")
    secrets = Path("/run/secrets")
    source = client(args.source, (secrets / "legacy_key").read_text().strip(),
                    (secrets / "legacy_secret").read_text().strip())
    target = client(args.target, os.environ["RUSTFS_ACCESS_KEY"], os.environ["RUSTFS_SECRET_KEY"])
    for bucket in BUCKETS:
        copy_bucket(source, target, bucket, args.apply)


if __name__ == "__main__":
    main()
