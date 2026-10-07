# Build an object detection project with TonOps

[English](README.md) | [Tiếng Việt](README.vi.md)

This walkthrough uses YOLO12 to show how to manage a detection project in TonOps:
connect your account, version your dataset, send training to a GPU worker,
compare experiments, and run predictions with a registered model. Replace the
vehicle classes and dataset paths with those from your own project.

For an automated Gitea test → train → build → deploy example using this training
code, see the [CI/CD walkthrough](cicd/README.md). Its small COCO8 CPU run deploys
a prediction API on port `7865`.

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

## 8. Frequently asked questions

### Must all code and data be stored on the server running TonOps?

No. The TonOps services, original dataset, and training process can run on
different machines. Each machine needs connectivity and credentials for the
services it uses.

| Component | Possible location |
| --- | --- |
| Project source | The user's machine or a Git repository; this example submits a copy of the training script with the task |
| Original data | The user's machine, a shared drive, or the team's storage system |
| Registered datasets and uploaded checkpoints | RustFS or the configured artifact storage, which can run separately from the TonOps server |
| Training process | The user's GPU machine or a GPU worker on another host |
| Experiment information | TonOps services manage task state, parameters, logs, metrics, and references to datasets/models |

In this guide's queued workflow, `register` uploads a versioned dataset to
storage. The worker downloads that version by Dataset ID and retrieves the
training code from the task. You do not need to manually copy the entire project
and original dataset into a directory on the TonOps server. The Docker image
must also be available locally on the worker or through its registry.

For direct training on your own machine, you can read local data and use TonOps
to track the experiment. Starting training does not automatically register the
original dataset; dataset registration and result uploads are separate actions
in this example.

### What if users want to train on their own machines?

Choose between running code directly and letting an agent manage execution.

**Run directly with TonOps tracking.** Configure your account and server
addresses in `~/clearml.conf` as in step 1. Install CUDA-enabled PyTorch suitable
for your machine, then install the example packages and run training:

```bash
source .venv/tonops-example/bin/activate
python -m pip install -r examples/vehicle_detection_yolo12/requirements.txt
python examples/vehicle_detection_yolo12/train.py \
  --data /path/to/vehicles/data.yaml --epochs 1 --imgsz 320 --batch 2
```

That YAML must reference data on your machine; set `path` to the actual dataset
root. `train.py` does not accept `--dataset-root`. To download a registered
version instead, replace `--data /path/to/vehicles/data.yaml` with
`--dataset-id "$TONOPS_DATASET_ID"`.

Training runs on your machine. The script creates a task in
`Vehicle Detection/YOLO12`, reports logs/metrics to TonOps, and uploads artifacts
and the checkpoint to configured storage. This mode needs no ClearML Agent,
Docker, or queue. The current `train.py` requires an NVIDIA GPU with CUDA and
uses device `0` as visible to the process.

**Run an agent on your machine.** For the same queued Docker workflow as other
workers, install the agent and build the image on your machine using the
[GPU worker guide](../../docs/clearml-gpu-worker.md). Use a dedicated queue to
choose where training runs:

```bash
python scripts/clearml-gpu-worker.py start --queue my-gpu --gpus 0 --detached
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --queue my-gpu \
  --dataset-id "$TONOPS_DATASET_ID" --epochs 1 --imgsz 320 --batch 2 \
  --output-uri "$TONOPS_OUTPUT_URI" --wait
```

Have only the agent on your machine listen to `my-gpu` if tasks must run there.
The TonOps server manages the task; the machine hosting the agent performs training.

### Why does submitting a task not start training on my machine?

`project.py submit` creates a task and puts it in a queue. It does not start a
worker or train in the client process. Check **Workers & Queues** or run
`project.py workers` to confirm a worker is online and listening to the correct
queue. When multiple workers listen to the same queue, another worker may take
the task; use a dedicated queue to select a specific machine.

### Can I use local data without uploading it to RustFS?

Yes, when running directly with `train.py --data /path/to/vehicles/data.yaml`.
The training machine reads images and labels from local paths. Artifacts and
checkpoints uploaded by the script still need accessible storage.

For a worker on another machine or inside Docker, client paths are not
automatically available in the training environment. This guide uses Dataset
IDs and registered data to make the dataset accessible. Shared-drive workflows
require you to configure access, container mounts, and matching YAML paths.

### Which TonOps services must a user's machine reach?

Submission and training clients need the API for authentication and task
updates. Dataset/model downloads and result uploads need the corresponding
storage service, such as RustFS or the Files server. Users access the Web app
to review and manage experiments. This guide's default ports are API `7862`,
Web `7861`, Files `7863`, and RustFS S3 `7868`; use your deployment's actual
addresses and ports.

When the server runs elsewhere, replace `localhost` with a hostname or IP
reachable from your machine. Configure API and storage credentials on each
client/worker that uses those services; server configuration does not
automatically configure users' machines.

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
