# TonOps stack

TonOps builds on a ClearML OSS fork with local user management, profile editing, and project visibility. The root [Dockerfile](Dockerfile) builds the checked-in Angular app and packages the checked-in API and fileserver code into one image. [Compose](compose.yaml) runs that image with MongoDB, Redis, Elasticsearch, RustFS, and an async file deletion worker.

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
        host: "YOUR_RUSTFS_HOST:7868"
        key: "<RUSTFS_ACCESS_KEY>"
        secret: "<RUSTFS_SECRET_KEY>"
        region: "us-east-1"
        secure: false
        multipart: false
      }]
    }
    boto3.s3.addressing_style: "path"
  }
  development.default_output_uri: "s3://YOUR_RUSTFS_HOST:7868/tonops-artifacts"
}
```

To move existing registered model files and task output artifacts, run `python scripts/migrate-rustfs-artifacts.py` to preview, then `python scripts/migrate-rustfs-artifacts.py --apply`. The migration verifies each uploaded object before updating its URI and writes a rollback manifest under `CLEARML_DATA_ROOT/config`. Project deletion schedules the registered RustFS model and artifact objects for asynchronous removal; check `docker compose logs async_delete` if an object remains. Original fileserver files from migration are retained as a backup.

## Operate

### ClearML Agent and GPU worker

Follow the [GPU worker setup and YOLO12 job guide](docs/clearml-gpu-worker.md) to
install the agent, configure NVIDIA Docker, create a GPU queue, launch a worker,
and submit/check a containerized training job. It includes a small COCO8 smoke
run and vehicle training using a portable ClearML Dataset ID.

### Example pipelines and model endpoints

Run two small pipelines using scikit-learn's bundled Iris and Wine datasets:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate tungn197
python scripts/example-models.py --self-check
python scripts/example-models.py
```

The script prompts for the `admin` password, runs prepare → train → evaluate steps locally without an Agent, and uploads artifacts and published models through the authenticated fileserver. The **Pipelines** page shows both runs under `Examples`; **Model Endpoints** shows two live classifiers while the script remains running. Each endpoint reports actual request counts and latency every 30 seconds. Ctrl+C unregisters the endpoints; pipeline runs and models remain available. Running the script again creates new pipeline runs and model versions.

For a remote server, pass `--api-url`, `--web-url`, and `--files-url`. To allow access from another machine, pass `--bind 0.0.0.0 --public-url http://<reachable-host>:7870`; the demo prediction service has no authentication, so expose it only on a trusted network. Port `7870` must be reachable from the client. Passwords can also be supplied through the `EXAMPLES_PASSWORD` environment variable.

```bash
curl http://localhost:7870/health
curl http://localhost:7870/predict/iris \
  -H 'Content-Type: application/json' \
  -d '{"instances": [[5.1, 3.5, 1.4, 0.2]]}'
curl http://localhost:7870/predict/wine \
  -H 'Content-Type: application/json' \
  -d '{"instances": [[14.23, 1.71, 2.43, 15.6, 127, 2.8, 3.06, 0.28, 2.29, 5.64, 1.04, 3.92, 1065]]}'
```

### Object detection project with YOLO12

Follow the [TonOps object detection walkthrough](examples/vehicle_detection_yolo12/README.md)
to configure your account, validate and version a YOLO dataset, submit GPU training,
compare runs, and use a registered model for prediction. The example uses your
API credentials and a ClearML Dataset ID so the worker can fetch data from RustFS.
It includes a one-epoch COCO8 check before training your own dataset.

```bash
python examples/vehicle_detection_yolo12/project.py --help
```

The [GPU worker guide](docs/clearml-gpu-worker.md) covers agent installation,
Docker runtime configuration, GPU allocation, and worker operations.

### Project AI

Project overview includes **Ask AI** and **Generate report**. The API server retrieves tasks and metric summaries from the project and readable subprojects. Answers show which tasks were included; large projects use a bounded snapshot of the most recently updated tasks. Metric summaries include latest, first, minimum, maximum, and mean values when recorded, rather than complete event histories.

Configure `LLM_BASE_URL` (an OpenAI-compatible `/v1` URL), `LLM_MODEL` (the server's model ID), and `LLM_API_KEY` in the private root `.env`. The GLM endpoint uses model ID `glm53-flash`. `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS`, and `LLM_MAX_TASKS` control request limits. Compose passes these values only to the API container; credentials are excluded from source control, image builds, and browser bundles. Recreate the API container after changing settings.

Reports are generated as Markdown drafts. The project owner can edit the title and choose **Save to Reports**; saved drafts appear on their profile and open in the existing report editor. Questions and generation are read-only operations and respect project visibility. Saving checks ownership again. Conversation history stays in the browser component and is cleared when changing projects.

### Stack operations

```bash
docker compose ps
docker compose logs -f apiserver
docker compose up -d --build             # Rebuild after source changes
docker compose down                       # Stop without deleting data
```

Or run `./restart_all.sh` to rebuild, restart, and wait for the web, API, fileserver, and RustFS endpoints. Pass `--skip-build` to reuse the existing image or `--force-recreate` to recreate every container.

The login and Create Account background comes from `brand_assets/background.png`. After replacing that file, rebuild the image and recreate the webserver so it serves the new artwork:

```bash
docker compose build apiserver
docker compose up -d --no-deps --force-recreate webserver
```

The image build needs access to the pinned Node, ClearML server, and package images and the packages in `pnpm-lock.yaml`. For an isolated network, preload those images and provide an internal npm registry or a populated pnpm store. Runtime has no external authentication dependency. Local fileserver authentication remains enabled so project file access is checked. See [project visibility](clearml-server/docs/iam/project-visibility.md) for storage limits and [IAM deployment](clearml-server/docs/iam/deployment.md) for bootstrap and migration details.
