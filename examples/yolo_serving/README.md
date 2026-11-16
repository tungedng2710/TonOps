# Serve registered YOLO models

This separate inference deployment loads existing ClearML models, verifies their
checkpoint hashes and ownership, and registers live endpoints in **Model
endpoints**. It reuses the installed YOLO12 demo image and serves YOLO11, YOLO12
and YOLO26 checkpoints supported by that runtime. It does not train new models,
publish drafts, change ClearML authentication or replace the existing demo.

## Prepare and start

From the repository root, use the Python environment configured for the account
that owns the models. The preparation step downloads registered RustFS objects
and stores a private API credential file with mode `0600` under ignored
`docker-data`; credentials and weights are mounted read-only, outside the image.

```bash
python examples/yolo_serving/prepare.py \
  --model yolo11=YOUR_YOLO11_MODEL_ID \
  --model yolo12=YOUR_YOLO12_MODEL_ID \
  --model yolo26=YOUR_YOLO26_MODEL_ID
```

Create `docker-data/examples/yolo-serving/deployment.env` locally:

```dotenv
YOLO_SERVING_PORT=7872
YOLO_SERVING_PUBLIC_URL=http://YOUR_SERVER_HOST:7872
```

Build and start the independent service:

```bash
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml up -d --build --wait
```

The default base image is the existing local YOLO demo image. Override
`SERVING_BASE_IMAGE` as a Docker build argument if that image is unavailable.
The serving process uses CPU, two CPU cores and a 3 GiB memory limit. It has an
automatic restart policy and a read-only root filesystem. Docker must be running
after reboot. The model mount must be readable by container UID 1000.

Only model records owned by the configured account are accepted. The model's
registered URI must still match the prepared manifest at startup. Changing a
checkpoint requires preparing and redeploying it. Startup executes each model
before registering the endpoints. Activity reports run every 15 seconds; stale
registrations expire after 120 seconds. `/health` reports telemetry freshness.

## Send an image

Open `http://YOUR_SERVER_HOST:7872/docs` for the actual OpenAPI contract and an
interactive file upload. `/health` lists loaded model IDs; `/models` lists their
JSON and multipart prediction URLs.

Multipart image upload:

```bash
curl -F 'file=@/path/to/image.jpg' \
  'http://YOUR_SERVER_HOST:7872/predict/yolo12/image?confidence=0.1'
```

The existing standard-library client sends base64 JSON and needs no ML packages:

```bash
python examples/call_yolo12_endpoint.py /path/to/image.jpg \
  --endpoint http://YOUR_SERVER_HOST:7872/predict/yolo12
```

Python with `requests`:

```python
import base64
from pathlib import Path
import requests

response = requests.post(
    "http://YOUR_SERVER_HOST:7872/predict/yolo12",
    json={"image_base64": base64.b64encode(Path("image.jpg").read_bytes()).decode()},
    timeout=60,
)
response.raise_for_status()
print(response.json())
```

Replace `yolo12` with `yolo11` or `yolo26` to select another loaded model. Results
include the actual registry model ID, checkpoint version, image dimensions,
inference latency and detected class IDs/labels/confidence/pixel bounding boxes
(`x1, y1, x2, y2`). Confidence must be greater than zero and at most one.

Images are limited to 8 MiB and 20 million pixels; request bodies to 12 MiB.
POST requests require Content-Length, which standard JSON and multipart clients
send automatically. Invalid base64/images are rejected; unknown model names
return 404. Runtime package auto-installation is disabled.

Prediction routes are unauthenticated, matching the existing serving demo.
Expose them only on a trusted network. ClearML API credentials remain private to
the reporting process. Smoke-training checkpoints demonstrate deployment and
are not a claim of production detection accuracy.

## Operate and verify

Use the same `--env-file` and Compose file when recreating the service:

```bash
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml ps
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml logs --tail 100 inference
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml restart inference
```

Stop it with `down` using the same file arguments. Clean shutdown unregisters
only this service's endpoints; registered models and source weights remain.
API/reporting outages do not simulate successful heartbeats; inference continues
while `/health` shows stale telemetry.

Run input-contract tests with the serving dependencies installed:

```bash
YOLO_AUTOINSTALL=false python -m unittest discover -s tests -p test_yolo_serving.py -v
```
