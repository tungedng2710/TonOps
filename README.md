# ClearML with local IAM

This repository contains a ClearML OSS fork with local user management, profile editing, and project visibility. The root [Dockerfile](Dockerfile) builds the checked-in Angular app and packages the checked-in API and fileserver code into one image. [Compose](compose.yaml) runs that image with MongoDB, Redis, Elasticsearch, RustFS, and an async file deletion worker.

## Start with Docker Compose

Docker Compose and at least 4 GB of available memory are recommended. Elasticsearch also needs `vm.max_map_count` of at least `262144` on Linux.

```bash
cp .env.example .env
mkdir -p docker-data/config docker-data/data/elastic_7 docker-data/rustfs
sudo chown -R 1000:0 docker-data/data/elastic_7
sudo chown 10001:10001 docker-data/rustfs
# Set unique RUSTFS_ACCESS_KEY and RUSTFS_SECRET_KEY in .env before starting.
printf 'Choose a strong temporary password: '
read -rs CLEARML_BOOTSTRAP_PASSWORD; printf '\n'
printf '%s' "$CLEARML_BOOTSTRAP_PASSWORD" > docker-data/config/iam-admin-password
unset CLEARML_BOOTSTRAP_PASSWORD
chmod 600 docker-data/config/iam-admin-password
docker compose up -d --build
```

The password file is read only by the API container. IAM creates the `admin` account only if no administrator already exists. Log in, change its password, then remove `docker-data/config/iam-admin-password` and clear `CLEARML_IAM_BOOTSTRAP_ADMIN_USERNAME` and `CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD_FILE` from `.env`. Keep `CLEARML_IAM_ENABLED=true`.

| Service | URL |
| --- | --- |
| Web app | <http://localhost:7861> |
| API | <http://localhost:7862> |
| Files | <http://localhost:7863> |
| RustFS S3 API | <http://localhost:7868> |
| RustFS console | <http://localhost:7869/rustfs/console/> |

Set `CLEARML_WEB_PORT`, `CLEARML_API_PORT`, and `CLEARML_FILES_PORT` in `.env` to change host ports. Set `CLEARML_FILES_HOST` to the URL that SDK clients use for the fileserver, so artifact cleanup recognizes it. The web app proxies `/api` and `/files` to the corresponding containers.

Data is stored under `CLEARML_DATA_ROOT` (default `./docker-data`) and survives `docker compose down`. For a host using the older `/opt/clearml` layout, set `CLEARML_DATA_ROOT=/opt/clearml` before starting this Compose stack. Stop the older stack first because it uses the same host ports. Do not run `docker compose down -v` when you want to retain data.

RustFS data is stored under `RUSTFS_DATA_ROOT` in `.env`. Set `RUSTFS_PUBLIC_HOST` to the hostname or IP that training clients and browsers can reach. The S3 endpoint is `http://RUSTFS_PUBLIC_HOST:RUSTFS_API_PORT`; the Compose stack creates `RUSTFS_BUCKET` automatically. The console uses the RustFS admin access and secret keys from `.env`. Keep `.env` private.

New projects default to `s3://RUSTFS_PUBLIC_HOST:RUSTFS_API_PORT/RUSTFS_BUCKET` for model and artifact outputs. A task's explicit `output_uri` still takes precedence. Configure every ClearML SDK or Agent that uploads artifacts with the RustFS credentials and a path-style S3 connection. For example, add this to the client's private `~/clearml.conf` (substitute values from `.env`):

```hocon
sdk {
  aws {
    s3 {
      credentials: [{
        host: "27.66.108.30:7868"
        key: "<RUSTFS_ACCESS_KEY>"
        secret: "<RUSTFS_SECRET_KEY>"
        region: "us-east-1"
        secure: false
        multipart: false
      }]
    }
    boto3.s3.addressing_style: "path"
  }
  development.default_output_uri: "s3://27.66.108.30:7868/tonops-artifacts"
}
```

To move existing registered model files and task output artifacts, run `python scripts/migrate-rustfs-artifacts.py` to preview, then `python scripts/migrate-rustfs-artifacts.py --apply`. The migration verifies each uploaded object before updating its URI and writes a rollback manifest under `CLEARML_DATA_ROOT/config`. Project deletion schedules the registered RustFS model and artifact objects for asynchronous removal; check `docker compose logs async_delete` if an object remains. Original fileserver files from migration are retained as a backup.

## Operate

```bash
docker compose ps
docker compose logs -f apiserver
docker compose up -d --build             # Rebuild after source changes
docker compose down                       # Stop without deleting data
```

Or run `./scripts/restart-tonops.sh` to rebuild, restart, and wait for the web, API, and fileserver endpoints.

The login and Create Account background comes from `brand_assets/background.png`. After replacing that file, rebuild the image and recreate the webserver so it serves the new artwork:

```bash
docker compose build apiserver
docker compose up -d --no-deps --force-recreate webserver
```

The image build needs access to the pinned Node, ClearML server, and package images and the packages in `pnpm-lock.yaml`. For an isolated network, preload those images and provide an internal npm registry or a populated pnpm store. Runtime has no external authentication dependency. Local fileserver authentication remains enabled so project file access is checked. See [project visibility](clearml-server/docs/iam/project-visibility.md) for storage limits and [IAM deployment](clearml-server/docs/iam/deployment.md) for bootstrap and migration details.
