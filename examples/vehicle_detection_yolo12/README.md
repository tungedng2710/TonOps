# Build an object detection project with TonOps

[English](README.md) | [Tiếng Việt](README.vi.md)

This walkthrough uses YOLO12 to show how to manage a detection project in TonOps:
connect your account, version your dataset, send training to a GPU worker,
compare experiments, and run predictions with a registered model. Replace the
vehicle classes and dataset paths with those from your own project.

The commands below run from the **repository root**. Use
`python examples/vehicle_detection_yolo12/project.py --help` to see the project CLI.

## 1. Connect to your TonOps workspace

Start the stack using the [stack setup instructions](../../README.md#start-with-docker-compose).
Open the Web UI, sign in to your account, and create API credentials in
**Account settings**. Install the client on the machine that holds your dataset:

```bash
python3.10 -m venv .venv/tonops-example
source .venv/tonops-example/bin/activate
python -m pip install -r examples/vehicle_detection_yolo12/requirements-client.txt
clearml-init
```

Enter your account's API credentials and your deployment's addresses:

| Service | Same machine | Remote server |
| --- | --- | --- |
| Web | `http://localhost:7861` | `http://SERVER_HOST:7861` |
| API | `http://localhost:7862` | `http://SERVER_HOST:7862` |
| Files | `http://localhost:7863` | `http://SERVER_HOST:7863` |

Configure the RustFS credentials and S3 connection in your private
`~/clearml.conf` using the [storage configuration example](../../README.md#start-with-docker-compose).
Use a RustFS hostname reachable from both your client and GPU worker. Keep the
private configuration out of Git.

Choose a project name and your deployment's artifact storage URI:

```bash
export TONOPS_PROJECT='Vehicle Detection/YOLO12'
export TONOPS_OUTPUT_URI='s3://YOUR_RUSTFS_HOST:7868/tonops-artifacts'
```

The example's ClearML SDK calls connect to TonOps; dataset versions, experiments,
metrics, and models appear in the TonOps Web UI. RustFS stores uploaded files.

## 2. Start a GPU worker and check the training path

On the GPU host, follow the [GPU worker setup guide](../../docs/clearml-gpu-worker.md)
to install the agent, configure its API/storage credentials, and build the
training image. Start it with:

```bash
python scripts/clearml-gpu-worker.py start --queue gpu --gpus 0 --detached
```

On your client, verify that the worker is online and submit the small COCO8 job:

```bash
python examples/vehicle_detection_yolo12/project.py workers
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --queue gpu \
  --output-uri "$TONOPS_OUTPUT_URI" --wait
```

In **Workers & Queues**, confirm the worker listens to `gpu`. In the project's
experiment list, open the submitted task. Its console should show a GPU runtime,
and its status should progress from queued to in progress to completed. The
one-epoch smoke job checks execution and uploads; use your own dataset for
project training and accuracy comparisons.

The client uploads the training script with its requirements, parameters, and
Docker image. The worker fetches that task and runs it inside the image. The
client needs no PyTorch installation or GPU for submission. Every worker on the
queue needs the image built locally or available from your registry.

## 3. Prepare and validate your dataset

Use YOLO detection labels: one object per line, with
`class_id x_center y_center width height`. Coordinates are normalized to the
image dimensions, and class IDs start at zero. Empty label files represent
images with no objects.

For the bundled vehicle configuration, arrange your data as:

```text
/path/to/vehicles/
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
└── test/                 # optional; remove the YAML entry if absent
    ├── images/
    └── labels/
```

Each image needs a corresponding `.txt` label with the same relative name in
its split's `labels` directory. The [example data.yaml](data.yaml) defines
bicycle, bus, car, motorbike, and truck. Copy it for your project and change
`names`, `train`, `val`, and optionally `test` to match your dataset. Each split
must point to an `images` directory with a sibling `labels` directory.

```bash
export TONOPS_DATA_ROOT=/path/to/vehicles

python examples/vehicle_detection_yolo12/project.py validate \
  --dataset-root "$TONOPS_DATA_ROOT" \
  --data examples/vehicle_detection_yolo12/data.yaml
```

Validation checks split paths, nonempty image sets, matching labels, class IDs,
and normalized boxes. It prints split and class counts without contacting the
server. For another schema, pass `--data /path/to/your/data.yaml` in validation
and registration. `--dataset-root` overrides that YAML's `path` field; split
paths must resolve inside the supplied root.

## 4. Register a dataset version

```bash
python examples/vehicle_detection_yolo12/project.py register \
  --project "$TONOPS_PROJECT" --name vehicles --version 1.0.0 \
  --dataset-root "$TONOPS_DATA_ROOT" \
  --data examples/vehicle_detection_yolo12/data.yaml \
  --output-uri "$TONOPS_OUTPUT_URI"

export TONOPS_DATASET_ID=$(cat docker-data/examples/object-detection/dataset-id)
```

Registration validates again, uploads images and labels, and adds a portable
`data.yaml` with relative split paths. It saves validation metadata and finalizes
the dataset. Your source YAML stays unchanged. Find the version in **Datasets**
and retain its Dataset ID; workers use that ID to download the same data.

When annotations or splits change, register a new version such as `1.1.0` and
use its new Dataset ID in subsequent runs. Existing finalized versions remain
available to reproduce earlier experiments. Registration creates a new version
on each invocation; reuse the saved ID when the dataset has not changed.

## 5. Train your detector through the GPU queue

Start with a small run on your registered dataset:

```bash
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --name 'vehicles-smoke' --queue gpu \
  --dataset-id "$TONOPS_DATASET_ID" --model yolo12n.pt \
  --epochs 1 --fraction 0.01 --imgsz 320 --batch 2 \
  --output-uri "$TONOPS_OUTPUT_URI" --wait
```

Then submit a baseline using the full training split:

```bash
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --name 'vehicles-baseline' --queue gpu \
  --dataset-id "$TONOPS_DATASET_ID" --model yolo12n.pt \
  --epochs 50 --imgsz 640 --batch 8 --workers 2 \
  --output-uri "$TONOPS_OUTPUT_URI"

export TONOPS_TASK_ID=$(cat docker-data/examples/object-detection/task-id)
python examples/vehicle_detection_yolo12/project.py check \
  --task-id "$TONOPS_TASK_ID" --wait --timeout 7200
```

The worker downloads the dataset, resolves paths against its own cache, trains
on the training split, and reports validation metrics. It logs the Dataset ID,
GPU runtime, final metrics, and an output model containing the best checkpoint
and class labels. The optional test split is reserved for a separate evaluation;
this example does not use it for model selection.

Submission prints the task ID and a results URL. The saved task ID is the most
recent submission; retain earlier IDs or use `--task-id-file` for separate runs.
`check --wait` returns `0` on completion, `1` on failure/stop/closure, and `2` on
timeout. A timeout leaves the job running or queued. Without `--wait`, the
command displays the current state without waiting for completion.

## 6. Compare experiments and choose a model

Open the project in TonOps and select runs to compare their training parameters,
validation precision/recall, mAP, and losses. Keep the Dataset ID fixed while
changing one training choice, for example `--imgsz 640` versus `--imgsz 320`.
Give each run a descriptive name so its purpose is clear.

The task's artifacts include `dataset`, `gpu-runtime`, and `final-metrics` for
your own dataset runs. Its output model links the checkpoint to the training
run. `check` also prints the output model IDs. Copy the chosen Model ID from
these results or the model's page for prediction. Project members need access
to both the project and its artifact storage to retrieve the model.

## 7. Run prediction with the registered model

Install the inference dependencies on a machine that can access TonOps and
RustFS. Prediction defaults to CPU:

```bash
python -m pip install -r examples/vehicle_detection_yolo12/requirements.txt
export TONOPS_MODEL_ID=YOUR_OUTPUT_MODEL_ID

python examples/vehicle_detection_yolo12/project.py predict \
  --model-id "$TONOPS_MODEL_ID" --source /path/to/image.jpg
```

The command downloads the registered checkpoint and writes an annotated image
and a JSON file under `docker-data/examples/object-detection/predictions/`.
Detections contain class IDs, class names, confidence scores, and bounding boxes
in original image pixels. Use `--confidence 0.4`, `--device 0` on a GPU machine,
or `--output-dir /path/to/results` when needed.

This command lets you inspect a selected model on new images. To serve it as an
application, use the same Model ID and inference logic in your service and
choose authentication, networking, and deployment settings for that application.

## Code to adapt for your project

| File | Responsibility |
| --- | --- |
| [project.py](project.py) | User commands: validate, register, submit, check, workers, and predict |
| [dataset.py](dataset.py) | Label validation and portable dataset registration |
| [train.py](train.py) | Self-contained training task executed by the worker |
| [data.yaml](data.yaml) | Example layout and class names |
| [requirements-client.txt](requirements-client.txt) | Lightweight dataset/submission client |
| [requirements.txt](requirements.txt) | Client plus local inference dependencies |

The root `scripts/example-yolo12.py` and `scripts/clearml-yolo12-job.py` forward
to this project CLI and accept the same subcommands. The previous local pipeline
and HTTP endpoint flags have been replaced by the register → submit → check →
predict workflow above. `train.py` is the worker entry point; submit experiments
through `project.py` to record the dataset, container, and parameters together.
