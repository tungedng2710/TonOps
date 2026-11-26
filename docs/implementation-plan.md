# MLflow platform implementation plan

The M0 and M1 gate covers a dedicated single-user deployment. The native MLflow UI uses HTTP port **7871** on all IPv4 interfaces in the trusted-server deployment. A dedicated Gitea instance uses loopback port **7872**. [Deployment and demo instructions](mlflow-deployment.md) · [Acceptance report](acceptance-report.md)

| Milestone | Deliverable and exit gate |
| --- | --- |
| M0 | Pin the runtime and review the exact upstream releases. Prove signed S3 compatibility and scoped access on RustFS. Record identity options and their release risks. |
| M1 | Bootstrap private RustFS buckets, restricted PostgreSQL databases, MLflow tracking and registry, and private Git hosting. Train a CPU model, retrieve and predict in a separate client, then recreate the containers and recover the same run, model, objects and Git commit. |
| M2 | Publish two DVC versions. Check each out by immutable Git commit into an empty workspace and link it to the resulting MLflow runs and models. |
| M3 | Deploy Keycloak and TLS ingress. Verify browser and SDK authentication, deny-by-default access, direct API and artifact denial, and revocation across services. |
| M4 | Implement the project-scoped portal and audited model promotion with reconciliation. |
| M5 | Implement durable job claiming and a restricted worker. Prove CPU execution, failure, cancellation, and recovery. |
| M6 | Produce an offline bundle and run the smoke and restore tests in a clean isolated environment. |

The repository already has a ClearML deployment at its root. The MLflow Make targets explicitly load `compose.mlflow.yaml` and `versions.lock.yaml`, and use MLflow-specific configuration and data. The baseline topology and implementation decisions are in [architecture](architecture.md) and [ADR 0001](adr/0001-mlflow-core.md). [ADR 0002](adr/0002-mlflow-identity-options.md) records the team identity evaluation.
