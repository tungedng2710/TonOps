# Shared RustFS for ClearML and MLflow

The application projects are `mlops-clearml` and `mlops-mlflow`. The `mlops-storage` project runs the only RustFS server. Both applications reach it at `http://rustfs:9000` through the internal `mlops-artifacts` network. The RustFS API and console retain the ports in the root `.env`.

ClearML keeps its existing artifact bucket and S3 URLs. MLflow uses `s3://mlflow-artifacts` with its own scoped service identity. The shared RustFS administrator credential can manage both platforms’ buckets. Existing ClearML clients using that credential retain its administrator access.

## Start and stop

Prepare `.env` and the `RUSTFS_DATA_ROOT` directory using the [root setup instructions](../README.md). Then run the commands appropriate to the applications you want.

```sh
make storage-up
docker compose up -d

make init
make up
make smoke
```

`make up` also checks that shared storage is running. `docker compose down` and `make down` stop their application projects. Stop shared storage separately when both applications are offline.

```sh
docker compose -f compose.storage.yaml down
```

## Migrate an existing installation

Plan a brief maintenance window. Keep the old Compose files, project names, and data paths for rollback. The shared service uses the existing ClearML RustFS image, bind directory, and published ports. Keep that data directory mounted by only one running RustFS server.

1. Stop the old ClearML project and stop MLflow's tracking server to pause artifact writes. Keep the old MLflow RustFS running and its volume attached.
2. Start shared storage with `make storage-up`, then start ClearML under `mlops-clearml`. Include `compose.cicd.yaml` if the old stack ran the Gitea runner.
3. Run the MLflow `storage-init` service to create the private buckets and scoped service identity on the shared instance. Obtain the legacy RustFS IP on `mlops-mlflow_storage` and the shared RustFS IP on `mlops-artifacts` with `docker inspect`. Pass both complete internal URLs below. Existing installations can override `MLOPS_LEGACY_STORAGE_NETWORK` and `MLOPS_LEGACY_SECRETS_DIR` when needed.

   ```sh
   mlflow_compose() {
     docker compose --env-file .env --env-file infra/mlflow/.env.local \
       -f compose.mlflow.yaml -f versions.lock.yaml "$@"
   }
   mlflow_compose run --rm --no-deps storage-init
   mlflow_compose run --rm --no-deps storage-copy \
     --source "$LEGACY_RUSTFS_URL" --target "$SHARED_RUSTFS_URL" --apply
   mlflow_compose run --rm --no-deps storage-copy \
     --source "$LEGACY_RUSTFS_URL" --target "$SHARED_RUSTFS_URL"
   ```

   Use `infra/mlflow/.env.example` in the command if you have no local override file. The second copy command verifies that every source object is present with identical content. The copy aborts if an existing destination object differs or the source bucket has versioning enabled.
4. Stop the old MLflow RustFS and run `make up`, followed by `make smoke`. Confirm MLflow is attached to `mlops-artifacts`. Verify the ClearML API and a known ClearML artifact. Retire old containers after these checks and retain their data volumes and bind directories.

For rollback, stop writers first. Stop shared RustFS before restarting the old ClearML RustFS against the same bind directory. Start the old Compose files with their original project names and data paths. If MLflow has written new artifacts after cutover, reconcile those with the retained legacy volume before switching MLflow back.
