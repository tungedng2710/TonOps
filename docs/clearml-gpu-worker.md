# TonOps GPU worker setup

Run these commands from the repository root on a **Linux NVIDIA GPU host**.
The worker listens to the `gpu` queue and executes one task at a time in Docker.
Use the [object detection project walkthrough](../examples/vehicle_detection_yolo12/README.md)
for dataset registration, training, model review, and prediction.

## 1. Prepare Docker and the NVIDIA runtime

Install Docker Engine and Python 3.10 or 3.11, including its `venv` package.
Verify the host driver first:

```bash
nvidia-smi
docker info
```

On Ubuntu/Debian, install the NVIDIA Container Toolkit if it is missing:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -sSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

The final command restarts Docker, including the ClearML server's containers if
they run on this host. Run it when the server can tolerate the restart. These
commands follow the [NVIDIA installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
The training image uses CUDA 12.6; use a compatible NVIDIA driver and let the
container smoke check below verify actual compatibility. See
[CUDA driver compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

The account running the agent must be able to use Docker. For a Docker socket
permission error, grant that account access according to your host's Docker
installation and start a fresh login session.

## 2. Install and configure the agent

```bash
python3 scripts/clearml-gpu-worker.py install --python python3.10
source .venv/clearml-agent/bin/activate

# Only needed if you do not already have a working ~/clearml.conf:
clearml-agent init

python scripts/clearml-gpu-worker.py configure
```

Installation pins ClearML Agent 3.0.3 and the SDK with S3 support in a dedicated
virtual environment. Create API credentials in **Account settings** in the
ClearML Web UI. For this repository's default server ports, use:

| Setting | Server on this GPU host | Server on another machine |
| --- | --- | --- |
| API | `http://localhost:7862` | `http://SERVER_HOST:7862` |
| Web | `http://localhost:7861` | `http://SERVER_HOST:7861` |
| Files | `http://localhost:7863` | `http://SERVER_HOST:7863` |

Use a hostname or IP reachable from the GPU host. The task containers use Linux
host networking, so `localhost` refers to the GPU host. When the ClearML server
is elsewhere, both the agent and submission client need the remote addresses.

The configure command creates `docker-data/agent/clearml.conf`. It includes your
private `~/clearml.conf` first, then the checked-in
[`agent.conf`](../workers/clearml-agent/agent.conf) overrides. It preserves API
credentials, RustFS credentials, and output storage settings. To use another
private configuration:

```bash
python scripts/clearml-gpu-worker.py configure --base-config /path/to/private/clearml.conf
```

Keep private configuration files out of Git. Configure the RustFS S3 credentials
in the private file as shown in the [stack README](../README.md#start-with-docker-compose).
The configured S3 host must be reachable from the worker and must match the host
in task output URIs. The worker config and saved task ID are under the ignored
`docker-data/` directory. The agent also caches packages and datasets in
`~/.clearml/`.

## 3. Build, verify, and start the GPU worker

```bash
python scripts/clearml-gpu-worker.py build
python scripts/clearml-gpu-worker.py doctor --gpus 0

# Foreground: leave this terminal running while submitting from another terminal.
python scripts/clearml-gpu-worker.py start --queue gpu --gpus 0
```

The image pins PyTorch 2.7.1, torchvision 0.22.1, ClearML, and Ultralytics.
It supplies a complete CUDA/cuDNN environment and OpenCV libraries. The agent
inherits the image's packages and uses the same pinned agent version inside
task containers. `doctor` checks the host driver, Docker, and a real CUDA matrix
multiplication inside the task image. `start` repeats that check before launching
the daemon and creates the queue if necessary.

For background operation:

```bash
python scripts/clearml-gpu-worker.py start --queue gpu --gpus 0 --detached
python scripts/clearml-gpu-worker.py list
python examples/vehicle_detection_yolo12/project.py workers
```

Confirm the worker also appears in the Web UI's **Workers & Queues** page,
listening to `gpu`. Queue selection and GPU allocation follow the
[ClearML Agent deployment instructions](https://clear.ml/docs/latest/docs/clearml_agent/clearml_agent_deployment_bare_metal/).
To use physical GPU 1, pass `--gpus 1` to both `doctor` and `start`. The job uses
device `0` **inside the container**, where it is the first allocated GPU.

For two independent workers, start one with `--gpus 0` and another with
`--gpus 1`, both on `gpu`. Their default worker IDs include the host and GPU
selection. Avoid assigning overlapping GPU selections to simultaneous workers.
Passing `--gpus 0,1` gives a single worker access to both GPUs; this example
still trains on its first GPU. Build the image on every host listening to the
queue, or publish it to your own registry and pass the same `--image` to worker
and submit commands.

## 4. Verify with a project job

With the worker running, submit a small YOLO12 job from another terminal:

```bash
source .venv/clearml-agent/bin/activate
python examples/vehicle_detection_yolo12/project.py submit --queue gpu --wait
```

Confirm the job completes and reports its GPU runtime, validation metrics,
and output model. Then follow the [TonOps object detection walkthrough](../examples/vehicle_detection_yolo12/README.md)
to register your own dataset and train a detector. A client on another machine
can install `examples/vehicle_detection_yolo12/requirements-client.txt` and submit
using that server's API credentials; it does not need a local GPU.

## 5. Stop and troubleshoot

```bash
python scripts/clearml-gpu-worker.py stop --queue gpu --gpus 0
```

Use the same GPU selection and custom `--worker-id` used at startup. Detached
agents need starting again after a host reboot. For a foreground worker, Ctrl+C
stops the process. Check task state in the UI after stopping an active worker.

| Symptom | Check |
| --- | --- |
| Task stays queued | Worker is online, listening to the same queue, and using the same server/workspace. Run `workers` and inspect the worker console. |
| Docker socket permission denied | The agent account can run `docker info`. |
| Host `nvidia-smi` fails | Repair the host driver before debugging the agent. |
| CUDA fails in Docker | Toolkit configuration, driver compatibility, and selected GPU; rerun `doctor`. |
| API/files/S3 connection fails | Use reachable server addresses and correct API/S3 credentials in the private config. |
| Image is unavailable | Build the image on the worker host or use a registry image consistently. |
| Dataset YAML is missing or has absolute split paths | Register a portable dataset containing its YAML, images, and labels. |
| Out of memory | Reduce `--batch` and `--imgsz`; inspect GPU memory for other jobs. |

## Offline code checks

```bash
python3 -m unittest discover -s tests -v
```

These checks cover job lifecycle and dataset portability using test doubles.
Use `doctor` and a completed training task to verify the actual GPU deployment.
