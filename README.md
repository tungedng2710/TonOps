# Run the local ClearML IAM fork

This starts MongoDB, Redis, Elasticsearch, the API server, file server, async
delete worker, and the locally built ClearML Web application. Docker data is
persisted under `/opt/clearml` by the upstream Compose configuration.

## 1. Build the web application

```bash
conda activate tungn197
cd /root/tungn197/mlops/clearml-web
corepack pnpm@10.18.3 install --frozen-lockfile
corepack pnpm@10.18.3 run build
corepack pnpm@10.18.3 run build-widgets
```

For an air-gapped host, the Docker images and pnpm packages must already exist in
an internal registry/cache.

## 2. Configure the first administrator

Create a password file without placing the password in shell history:

```bash
sudo install -d -m 700 /opt/clearml/config
sudo install -d -m 755 /opt/clearml/logs /opt/clearml/data/fileserver \
  /opt/clearml/data/mongo_4/db /opt/clearml/data/mongo_4/configdb \
  /opt/clearml/data/elastic_7 /opt/clearml/data/redis /opt/clearml/agent
# Elasticsearch runs as uid 1000 inside its container.
sudo chown -R 1000:0 /opt/clearml/data/elastic_7
sudoedit /opt/clearml/config/iam-admin-password
sudo chmod 600 /opt/clearml/config/iam-admin-password

export CLEARML_IAM_ENABLED=true
export CLEARML_IAM_BOOTSTRAP_ADMIN_USERNAME=admin
export CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD_FILE=/opt/clearml/config/iam-admin-password
```

Bootstrap is idempotent and only creates an administrator when none exists.

## 3. Start the complete stack

```bash
conda activate tungn197
cd /root/tungn197/mlops/clearml-server
docker compose \
  -f docker/compose.yaml \
  -f docker/compose.iam-local.yaml \
  up -d mongo redis elasticsearch fileserver apiserver async_delete webserver
```

The override mounts this checkout's IAM backend modules and Angular build into
the standard ClearML containers. Check startup with:

```bash
docker compose -f docker/compose.yaml -f docker/compose.iam-local.yaml ps
docker compose -f docker/compose.yaml -f docker/compose.iam-local.yaml logs -f apiserver
curl http://localhost:7862/debug.ping
```

Open:

- Web application: <http://localhost:7861>
- API server: <http://localhost:7862>
- File server: <http://localhost:7863>

For remote access, replace `localhost` with the server address. The public
firewall must allow TCP ports 7861 (web), 7862 (API), and 7863 (files).

Log in as `admin`, change the temporary password, and confirm that **Settings →
User Management** is visible. After bootstrap succeeds, remove the secret and
unset only the bootstrap variables; keep `CLEARML_IAM_ENABLED=true` whenever the
stack is recreated.

```bash
sudo rm /opt/clearml/config/iam-admin-password
unset CLEARML_IAM_BOOTSTRAP_ADMIN_USERNAME
unset CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD_FILE
```

## Stop or restart

Rebuild the UI, recreate all TonOps services, wait for readiness, and print the
final service state with:

```bash
cd /root/tungn197/mlops
./scripts/restart-tonops.sh
```

Use `--skip-build` when the frontend has not changed, or `--no-recreate` to
restart the existing containers without recreating them. The script activates
the `tungn197` Conda environment and keeps IAM and self-signup enabled by default.
Persistent data under `/opt/clearml/data` is not removed.
