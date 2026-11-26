# Run the MLflow core

Use a Linux host with Docker Engine, Docker Compose v2, Make, Python 3 and access to the Docker daemon. First-time preparation needs access to the pinned image registries and Python wheels. Use the main MLflow Compose targets from the repository root. Set up the shared RustFS configuration in the root `.env` and prepare its data directory as described in the [shared RustFS guide](shared-rustfs.md).

```sh
make init
make up
make status
make demo
```

Open [MLflow](http://localhost:7871) after forwarding port 7871. Docker publishes the native HTTP server on `0.0.0.0:7871`. The UI and API trust any caller who can reach that port.

To open MLflow directly from another device, add its server address to `infra/mlflow/.env.local` as a comma-separated list of `host:port` entries, then run `make up`. Set `MLFLOW_SERVER_CORS_ALLOWED_ORIGINS` to the matching browser URLs. Include the scheme and any nonstandard port. For a forwarded domain, use the domain and origin visible in the browser. The standard localhost addresses are always available.

```dotenv
MLFLOW_EXTRA_ALLOWED_HOSTS=mlflow.example.internal:7871
MLFLOW_SERVER_CORS_ALLOWED_ORIGINS=http://mlflow.example.internal:7871
```

Use your existing ClearML Gitea account and repositories for MLflow source code. On the Docker host, the shared [Gitea](http://127.0.0.1:7864) uses the port configured by `GITEA_PORT` in the root `.env`.

MLflow's PostgreSQL and artifact credentials are in the owner-only `infra/mlflow/.secrets` directory. The shared RustFS administrator credentials stay in the root `.env`. Preserve these files with their corresponding data. Re-running `make init` keeps existing credentials.

`make demo` trains a CPU logistic regression on deterministic, locally generated data. It logs parameters, held-out accuracy, training/test inputs, an evaluation report, and a model signature and input example. It registers a new version of `mlops-sklearn-demo`, assigns `candidate`, and starts a separate client to download the report and predict through both the exact version and the alias. The command prints identifiers for the run and version. The demo client uses only the tracking URL. `make smoke` repeats verification against the most recently completed demo.

```sh
make test
```

The integration test uses the configured MLflow stack, stops its PostgreSQL service to verify readiness failure and then recreates the MLflow containers. The shared RustFS continues serving ClearML. Run it during a test window. It checks the existing ClearML Gitea endpoint before and after recreation. It retains the integration run, model, and RustFS multipart fixture as evidence. It removes only the temporary S3 policy test identities, policies and objects it created.

`make logs` displays core logs. `make down` removes only the selected project's containers and networks and retains its named volumes. To run a separate MLflow acceptance project against the same RustFS, assign its own ports, service identity, secret directory, and project name. Use a separate storage deployment and network for fully isolated testing.

```sh
export MLFLOW_PORT=17871
export MLFLOW_SECRETS_DIR=./infra/mlflow/.secrets/acceptance
make MLFLOW_PROJECT=mlops-mlflow-acceptance init up
make MLFLOW_PROJECT=mlops-mlflow-acceptance test
```

The Makefile uses `infra/mlflow/.env.local` when present and otherwise uses `infra/mlflow/.env.example`. To use another file, set `MLFLOW_ENV_FILE`. Keep alternate file-backed credentials in an ignored owner-only directory and use a separate Compose project name. An explicit Docker context or `DOCKER` command can select the intended daemon.
