"""Create the artifact bucket before the API accepts new projects."""

import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def main():
    bucket = os.environ["RUSTFS_BUCKET"]
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("RUSTFS_ENDPOINT", "http://rustfs:9000"),
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
        s3.create_bucket(Bucket=bucket)
    print(f"RustFS bucket {bucket} is ready")


if __name__ == "__main__":
    main()
