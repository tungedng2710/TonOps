"""Check tracking storage and the scoped artifact identity through live requests."""

import os
from pathlib import Path
from urllib.request import urlopen

import boto3
from botocore.config import Config


def secret(name: str) -> str:
    return Path("/run/secrets", name).read_text().strip()


with urlopen("http://127.0.0.1:5000/api/2.0/mlflow/experiments/get?experiment_id=0", timeout=3):
    pass

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["MLFLOW_S3_ENDPOINT_URL"],
    aws_access_key_id=secret("artifact_key"),
    aws_secret_access_key=secret("artifact_secret"),
    config=Config(
        s3={"addressing_style": "path"},
        connect_timeout=2,
        read_timeout=2,
        retries={"total_max_attempts": 1},
    ),
)
s3.head_bucket(Bucket="mlflow-artifacts")
