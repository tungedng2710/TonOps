"""Verify exact RustFS objects, multipart transfer, and denied direct access."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3
from boto3.s3.transfer import TransferConfig
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

BUCKET = "mlflow-artifacts"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def client(*, signed: bool):
    credentials = {}
    if signed:
        credentials = {
            "aws_access_key_id": Path("/run/secrets/artifact_key").read_text().strip(),
            "aws_secret_access_key": Path("/run/secrets/artifact_secret").read_text().strip(),
        }
    return boto3.client(
        "s3", endpoint_url=os.environ["S3_ENDPOINT"], region_name="us-east-1",
        config=Config(
            signature_version="s3v4" if signed else UNSIGNED,
            s3={"addressing_style": "path"},
            connect_timeout=3, read_timeout=20, retries={"total_max_attempts": 1},
        ),
        **credentials,
    )


def denied(operation, **kwargs) -> None:
    try:
        operation(**kwargs)
    except ClientError as error:
        if error.response["ResponseMetadata"]["HTTPStatusCode"] == 403:
            return
        raise
    raise RuntimeError(f"{operation.__name__} unexpectedly succeeded for {kwargs}")


def check(reference: Path, action: str) -> None:
    result = json.loads(reference.read_text())
    s3 = client(signed=True)
    s3.head_bucket(Bucket=BUCKET)
    for object_key in (result["run_artifact_key"], result["model_artifact_key"]):
        listed = s3.list_objects_v2(Bucket=BUCKET, Prefix=object_key)
        require(object_key in {item["Key"] for item in listed.get("Contents", [])},
                f"MLflow object {object_key} missing in RustFS")
    report = s3.get_object(Bucket=BUCKET, Key=result["run_artifact_key"])
    with report["Body"] as body:
        require(json.loads(body.read())["accuracy"] == result["accuracy"],
                "RustFS holds a different evaluation report")

    anonymous = client(signed=False)
    denied(anonymous.list_objects_v2, Bucket=BUCKET)
    denied(anonymous.get_object, Bucket=BUCKET, Key=result["run_artifact_key"])
    denied(anonymous.put_object, Bucket=BUCKET, Key=f"core-checks/{result['run_id']}/unsigned", Body=b"denied")
    # An S3 identity for MLflow cannot list or read/write known keys in other buckets.
    for bucket in ("ml-datasets", "ml-exports"):
        denied(s3.list_objects_v2, Bucket=bucket)
        denied(s3.get_object, Bucket=bucket, Key="forbidden")
        denied(s3.put_object, Bucket=bucket, Key="forbidden", Body=b"denied")

    key = f"core-checks/{result['run_id']}/multipart.bin"
    payload = b"rustfs-multipart\x00" * 786432
    digest = hashlib.sha256(payload).hexdigest()
    config = TransferConfig(multipart_chunksize=5 * 1024**2, multipart_threshold=5 * 1024**2)
    with TemporaryDirectory() as directory:
        path = Path(directory, "multipart.bin")
        if action == "write":
            path.write_bytes(payload)
            s3.upload_file(str(path), BUCKET, key, Config=config)
            path.unlink()
        head = s3.head_object(Bucket=BUCKET, Key=key)
        require(head["ETag"].strip('"').endswith("-3"), f"Expected three S3 parts, got {head['ETag']}")
        s3.download_file(BUCKET, key, str(path), Config=config)
        require(digest == hashlib.sha256(path.read_bytes()).hexdigest(), "Multipart SHA-256 mismatch")
    print(f"RustFS {action} verified MLflow objects, S3 access denials, and multipart SHA-256 {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["write", "read"])
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    check(args.reference, args.action)
