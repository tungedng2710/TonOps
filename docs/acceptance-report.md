# MLflow M0 and M1 acceptance report

**Result: M0 PASS · M1 PASS.** The integration suite exited successfully and the demo remained usable through the native UI after restart.

Test host on 2026-11-26, Linux x86-64 with Docker Engine 29.9.3 and Docker Compose 5.7.0. Training and prediction used CPU. The deployment used PostgreSQL 17.12 Alpine, RustFS 1.0.6 GA with bundled `rc` 0.1.37, Gitea 28.4.0 rootless and MLflow 3.18.0 on Python 3.12.13. The installed wheel resolution included psycopg 3.3.9, boto3 1.44.12, scikit-learn 1.9.1 and skops 0.16.0. The [image lock](../versions.lock.yaml) and [Python lock](../infra/mlflow/requirements.lock) record the exact inputs.

## Original M0 and M1 run

This run used the original loopback listener. Subsequent listener changes appear below.

### Commands

```sh
docker compose --env-file infra/mlflow/.env.example --profile tools \
  -f compose.mlflow.yaml -f versions.lock.yaml config --quiet
sg docker -c 'make init up'
sg docker -c 'make demo && make test && make smoke'
sg docker -c 'make status'
```

The shell initially lacked the Docker group in its effective group list. Running the commands with `sg docker` used the account's existing Docker group membership. No Docker permission or ClearML configuration changes were required.

A second Compose project verified fresh initialization with new credentials and empty volumes. Its containers and networks were shut down after the check, and its volumes were retained.

```sh
sg docker -c 'export MLFLOW_PORT=17871 MLFLOW_GITEA_PORT=17872 MLFLOW_SECRETS_DIR=./infra/mlflow/.secrets/acceptance; make MLFLOW_PROJECT=mlops-mlflow-acceptance init up'
curl -fsS http://127.0.0.1:17871/version
sg docker -c 'export MLFLOW_PORT=17871 MLFLOW_GITEA_PORT=17872 MLFLOW_SECRETS_DIR=./infra/mlflow/.secrets/acceptance; make MLFLOW_PROJECT=mlops-mlflow-acceptance down'
```

## Diagnostics and fixes

| Initial result | Diagnosis and correction |
| --- | --- |
| FAIL · RustFS initialization stopped at the public access block command. | The installed image's bundled `rc` 0.1.37 lacks that command. Bootstrap now enforces private bucket policies with the CLI's supported anonymous access command, and the integration test checks unsigned reads, writes and listing. |
| FAIL · MLflow did not become ready under the core resource limit. | The pinned release defaults to launching its native job backend. The core disables native job execution and runs one Uvicorn worker. |
| FAIL · Tracking routes returned HTTP 403 for the legitimate loopback endpoint. | The pinned server matches the complete Host header including the port. The allowlist now includes the required loopback and Compose host/port pairs, and keeps the rejection check for an unlisted host. |
| FAIL · The registry lineage assertion looked for an empty SDK field. | In 3.18.0 the registry REST response carries the logged-model identifier in `source`, with the original run ID in `run_id`. Verification now resolves the source through the logged-model API. [Pinned model-version serialization](https://github.com/mlflow/mlflow/blob/v3.18.0/mlflow/entities/model_registry/model_version.py) |
| FAIL · The first integration run's Git helper could not create a scratch directory. | The rootless image's temporary directory is created by the web service entrypoint. The standalone test uses its own directory under `/tmp`. Actual Git push and clone succeeded in the subsequent check. |

## Verified behavior

| Check | Outcome | Observed evidence |
| --- | --- | --- |
| M0 version and identity review | PASS | The dependency matrix and release-specific identity options are recorded in the [core ADR](adr/0001-mlflow-core.md) and [identity ADR](adr/0002-mlflow-identity-options.md). Identity provider and team policy execution remain M3 tests. |
| Fresh bootstrap and repeated initialization | PASS | The fresh project created its PostgreSQL databases, private buckets and local Git administrator. A repeat `make init` left all eight existing secret files byte-for-byte unchanged. |
| Database separation | PASS | PostgreSQL returned `f\|f` when asked whether either application role could connect to the other's database. |
| UI and local ports | PASS | The pinned UI loaded on `127.0.0.1:7871`. Headless Chromium rendered the registered model, its alias and its source run on the model version page. The integration test received HTTP 403 with an unlisted Host header. PostgreSQL and RustFS have no published ports. |
| MLflow experiment and registry | PASS | A CPU run logged parameters, accuracy, two input contexts, an evaluation JSON report, and a model with signature and input example. A fresh client downloaded the report and produced predictions `[1, 0]` using both the registered version and its alias. |
| Artifact proxy and direct storage access | PASS | The tracking client had no S3 credentials, RustFS DNS or direct TCP connectivity to the RustFS container IP. The report and `MLmodel` keys were independently verified in RustFS. Unsigned list/get/put returned HTTP 403. |
| RustFS S3 and IAM | PASS | Signed path-style list/get/put, three-part upload, and ranged download passed. The independent SHA-256 was `9888f0b03a7af3c4f2c036d242650719a8d2f66df10cf36e4f1941f9d692bbec`. The MLflow key was denied dataset and export access. Two scoped test identities exercised own-prefix access and cross-project list/get/put denial with HTTP 403. |
| Gitea Git HTTP | PASS | The test created a private repository, pushed a real Git commit and cloned it with authentication. An unauthenticated `git ls-remote` failed. |
| Dependency health | PASS | MLflow became unhealthy with RustFS stopped and recovered after RustFS restarted. The same sequence passed with PostgreSQL stopped and restarted. |
| Persistence and repeated service bootstrap | PASS | `docker compose down` followed by `up -d --pull never --no-build --wait --wait-timeout 180` reran bootstrap and recreated containers. A fresh client loaded the same run, report, model version and alias. RustFS returned the same multipart SHA-256, and Git cloned the same commit. |
| Static validation | PASS | Compose configuration rendered successfully, all new Python modules compiled, shell syntax checks passed, and Ruff reported no issues in the Python code. |

The demo available on port 7871 registered `mlops-sklearn-demo` v3 with alias `candidate` and held-out accuracy `0.99609375` (255 of 256). The [run](http://127.0.0.1:7871/#/experiments/1/runs/d6260b4a19de43a1b3ca16a5547f897f) is `d6260b4a19de43a1b3ca16a5547f897f`. The logged model is `m-250f4bd6bbe9456baa524b3b177bc1a3`. [Open registry version](http://127.0.0.1:7871/#/models/mlops-sklearn-demo/versions/3)

The integration run was `7fed0d6fad55487295a559cdc44e5cbe`, with registered model `mlflow-core-test-23ffa4bc8c2a` v1 and logged model `m-8742b1e102e741a8a205d17ec85bb506`. Its private Git fixture commit was `364b60aeb6c7bd265ad91dba93cdde1cec9ffcc6`.

## Integration log excerpt

```text
PostgreSQL denied both cross-database connections
Tracking client has no S3 credentials, RustFS DNS entry, or direct TCP route
RustFS scoped identities passed same-project list/get/put and cross-project denial checks
MLflow became unhealthy with rustfs stopped
MLflow recovered after rustfs restarted
MLflow became unhealthy with postgres stopped
MLflow recovered after postgres restarted
PASS: run, report, model, RustFS multipart object, and Git commit survived container recreation
Verified run d6260b4a19de43a1b3ca16a5547f897f, artifact, and mlops-sklearn-demo v3 via exact version and @candidate
```

## Remaining release gates

| Milestone | Outcome | Tests still required |
| --- | --- | --- |
| M2 | NOT RUN | Fresh DVC checkout of two immutable versions and source/dataset/run/model lineage. |
| M3 | NOT RUN | Keycloak and team-scoped browser/API login, viewer and cross-project access checks across all services, auth revocation and bypass tests. |
| M4 | NOT RUN | Portal authorization, audited promotion to `champion` and rollback. |
| M5 | NOT RUN | Durable job execution, cancellation, retry, resource limits and recovery. GPU execution was outside the CPU-only core. |
| M6 | NOT RUN | Egress-blocked operation, offline bundle, backup/restore rehearsal and dependency/image scanning. |

## Superseded HTTPS listener

This section records the earlier HTTPS deployment. The current listener is native HTTP.

The Docker port mapping is `0.0.0.0:7871 -> 8443/tcp` on NGINX 1.30.8. MLflow's backend port is private and Gitea remains loopback-only. The private CA and single operator credential are generated in the MLflow secret directory.

| Check | Outcome | Observed evidence |
| --- | --- | --- |
| IPv4 binding and TLS | PASS | `ss -ltn` showed `0.0.0.0:7871`. Local requests through loopback and both host IPv4 addresses passed certificate and hostname verification with the generated CA. |
| Authentication and artifact proxy | PASS | Requests over HTTPS to a known RustFS-backed artifact returned HTTP 401 anonymously and HTTP 200 with the operator login. The authenticated browser-style experiment search also returned HTTP 200 from both network addresses. |
| MLflow SDK through HTTPS | PASS | A fresh SDK process loaded `models:/mlops-sklearn-demo@candidate` through the host's Tailscale address using the generated CA and operator login. Predictions stayed `[1, 0]`. |
| Existing core and ClearML | PASS | `make smoke` retrieved the original demo after the listener change. The ClearML Docker containers stayed running. |
| Integration and restart | PASS | `sg docker -c 'make test && make smoke'` exited zero. The HTTPS authentication, Host and Origin checks passed before and after container recreation, and the same run, model, RustFS object and Git commit persisted. |

Repeated `make init` preserved all 15 existing credentials and certificate files byte for byte. A fresh temporary CA directory passed leaf reissue for a new hostname while preserving its CA and operator login.

Initial listener startup failed on NGINX's default cache directory with a read-only root filesystem. A writable in-memory cache mount resolved the startup failure. The first manual experiment-search probe omitted the required positive `max_results` value and returned HTTP 400. The corrected request passed.

## Current direct HTTP listener

`sg docker -c 'make up && make smoke'` exited zero after switching the Docker port mapping to `0.0.0.0:7871 -> 5000/tcp`. The native MLflow UI and registry version 3 returned HTTP 200 from both `http://localhost:7871` and the server's Tailscale address. An unlisted Host header returned HTTP 403. The smoke test retrieved the original artifacts and loaded the existing model by version and alias. ClearML continued running on its existing deployment.

### Forwarded browser access

Exact Host and Origin entries were added to the local deployment config. The forwarded domain served the MLflow UI and experiment search over HTTP and HTTPS. The direct IPv4 address, Tailscale address, and localhost also passed. Chromium rendered the existing model version, alias, and source run through the forwarded domain. An unlisted Host and Origin still returned HTTP 403. The post-restart model smoke test passed.
