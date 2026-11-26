#!/bin/sh
set -eu

password=$(cat /run/secrets/tracking_db_password)
export MLFLOW_BACKEND_STORE_URI="postgresql+psycopg://mlflow:$password@postgres:5432/mlflow"
export AWS_ACCESS_KEY_ID="$(cat /run/secrets/artifact_key)"
export AWS_SECRET_ACCESS_KEY="$(cat /run/secrets/artifact_secret)"

exec mlflow server --host 0.0.0.0 --port 5000 --workers 1 --serve-artifacts
