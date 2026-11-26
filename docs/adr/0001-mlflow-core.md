# ADR 0001 · MLflow tracking, registry and artifact proxy

Accepted for the M0/M1 single-user deployment.

Use native MLflow for experiment tracking, model storage and registry. Use PostgreSQL with separate service roles and databases, RustFS S3 for object storage, and the existing ClearML Gitea for internal Git. Keep the core under its own Compose project with direct HTTP access for MLflow on a trusted server and existing ClearML settings for Gitea. PostgreSQL stays on an internal network. MLflow reaches the shared RustFS through a private Docker network.

The MLflow 3.18.0 upstream example establishes the tracking server and proxy artifact layout with PostgreSQL and RustFS. This deployment pins stable service versions, preinstalls the Python dependencies, uses private S3 buckets, and issues a dedicated artifact identity. New experiments use the server-generated proxy URI. The registry REST API returns the logged-model reference in the version's `source` field and the source run ID in `run_id`. The client resolves the reference through the logged-model API. A small skops-serialized logistic model is registered using MLflow 3's logged-model URI and checked by both immutable version and alias. [Pinned upstream Compose example](https://github.com/mlflow/mlflow/blob/v3.18.0/docker-compose/docker-compose.yml) · [Tracking server documentation](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)

| Component | Selected release | Compatibility evidence or limit |
| --- | --- | --- |
| MLflow | 3.18.0 | Uvicorn Host validation compares the complete Host field including the port. Native job execution is disabled for the core. [Release](https://github.com/mlflow/mlflow/releases/tag/v3.18.0) · [Host validation source](https://github.com/mlflow/mlflow/blob/v3.18.0/mlflow/server/security_utils.py) |
| PostgreSQL | 17.12 Alpine | MLflow uses the SQLAlchemy `postgresql+psycopg` dialect. Bootstrap creates only the MLflow tracking database on a fresh PostgreSQL instance. [Release notes](https://www.postgresql.org/docs/17/release-17-12.html) |
| RustFS | 1.0.0 GA | ClearML’s existing deployment serves both platforms. The `rc` 0.1.37 client from the pinned 1.0.6 tooling image provisions the MLflow buckets and scoped identity. [Server release](https://github.com/rustfs/rustfs/releases/tag/1.0.0) · [Tooling release](https://github.com/rustfs/rustfs/releases/tag/1.0.6) · [IAM documentation](https://docs.rustfs.com/en/security-compliance/iam) |
| Gitea | Existing ClearML deployment | Reuses the current Git HTTP address, SQLite database, repositories, and CI runner. |
| Python runtime | 3.12.13 | MLflow, psycopg 3.3.9, boto3 1.44.12 and scikit-learn 1.9.1 are installed from the hash-locked wheel resolution. |

The single-node topology has one copy of each volume. The M6 gate covers backups, recovery and network-blocked operation. Before upgrading, back up and rehearse the vendor migrations in an isolated stack. Use the supported `mlflow db upgrade` command with the target image for tracking schema changes, and preserve the original database until validation completes. [MLflow upgrade documentation](https://mlflow.org/docs/latest/self-hosting/upgrade/)
