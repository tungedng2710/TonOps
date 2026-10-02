# Vehicle detection with YOLO12 and ClearML

This example fine-tunes `yolo12n.pt` on the local vehicle dataset and records
parameters, console output, metrics, plots, dataset validation, and the best
weights in the ClearML project **Vehicle Detection/YOLO12**.

The source dataset remains at:

```text
/root/tungn197/AI-Traffic-Analysis/data/vehicle_30oct2025
```

The project-local [`data.yaml`](data.yaml) fixes the stale paths in the YAML
shipped with the dataset. It defines five classes: bicycle, bus, car,
motorbike, and truck.

## Configure ClearML once

In the Web UI at <http://27.66.108.30:7861>, open **Account settings**, create new app
credentials for your user, then run:

```bash
conda activate tungn197
clearml-init
```

Use these server addresses when prompted:

```text
API:   http://27.66.108.30:7862
Web:   http://27.66.108.30:7861
Files: http://27.66.108.30:7863
```

Do not commit the generated `~/clearml.conf`; it contains your secret key.
Configure the RustFS S3 credentials and default output URI in the same private file as
described in the [stack README](../../README.md#start-with-docker-compose) before training.

## Validate and train

```bash
conda activate tungn197
cd /root/tungn197/mlops/examples/vehicle_detection_yolo12
python -m pip install -r requirements.txt

# Fast dataset integrity check (does not contact ClearML)
python train.py --validate-only

# Full tracked baseline
python train.py
```

A short GPU smoke run can be launched with:

```bash
python train.py --no-clearml --epochs 1 --fraction 0.01 \
  --imgsz 320 --batch 2 --workers 2 --run-name smoke-test
```

Use `--no-clearml` for any local-only run. See all options with
`python train.py --help`.

YOLO12 is attention-based and can consume more memory than similarly sized
CNN models. The nano checkpoint and one GPU (`--device 0`) are conservative
defaults for this server's NVIDIA A30 GPUs. The launcher also ensures PyTorch
uses one complete cuDNN installation, preventing mixed-library version errors
on this host.
