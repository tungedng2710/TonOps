#!/usr/bin/env python3
"""TonOps task: fetch a detection dataset, train YOLO12, and register the model."""

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="coco8.yaml")
    parser.add_argument("--dataset-id", default="", help="ClearML Dataset containing portable data.yaml")
    parser.add_argument("--model", default="yolo12n.pt")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--fraction", type=float, default=1.0)
    return parser.parse_args()


def dataset_yaml(dataset_id):
    import yaml
    from clearml import Dataset

    root = Path(Dataset.get(dataset_id=dataset_id).get_local_copy()).resolve()
    source = root / "data.yaml"
    config = yaml.safe_load(source.read_text())
    for split in ("train", "val", "test"):
        entries = config.get(split)
        if entries:
            paths = entries if isinstance(entries, list) else [entries]
            if any(Path(path).is_absolute() for path in paths):
                raise ValueError(f"Dataset {split} paths must be relative to its root: {source}")
    config["path"] = str(root)
    target = Path.cwd() / "dataset-runtime.yaml"
    target.write_text(yaml.safe_dump(config, sort_keys=False))
    return str(target)


def main():
    args = parse_args()
    from clearml import OutputModel, Task

    task = Task.init(project_name="Vehicle Detection/YOLO12", task_name="YOLO12 GPU worker",
                     task_type=Task.TaskTypes.training, reuse_last_task_id=False)
    try:
        params = task.connect(vars(args).copy(), name="Training")
        args = argparse.Namespace(**params)
        if args.epochs < 1 or args.imgsz < 32 or args.batch < 1 or args.workers < 0:
            raise ValueError("epochs/batch must be positive, imgsz >= 32, workers >= 0")
        if not 0 < args.fraction <= 1:
            raise ValueError("fraction must be in (0, 1]")

        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("GPU job requires CUDA; check NVIDIA Container Toolkit and agent --gpus")
        gpu = {"name": torch.cuda.get_device_name(0), "count": torch.cuda.device_count(),
               "torch": torch.__version__, "cuda": torch.version.cuda,
               "cudnn": torch.backends.cudnn.version()}
        print("GPU runtime: " + json.dumps(gpu), flush=True)
        task.upload_artifact("gpu-runtime", gpu)
        data = dataset_yaml(args.dataset_id) if args.dataset_id else args.data
        if args.dataset_id:
            task.upload_artifact("dataset", {"dataset_id": args.dataset_id}, wait_on_upload=True)
            task.connect_configuration(str(Path(data).resolve()), name="Dataset")

        from ultralytics import YOLO

        model = YOLO(args.model)
        model.train(data=data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                    workers=args.workers, fraction=args.fraction, device="0", seed=42,
                    amp=False, project="runs", name=task.id, plots=True)
        # Container device 0 is the first GPU allocated by the agent, regardless
        # of the physical host index. The image supplies a consistent cuDNN stack.
        metrics = {key: float(value) for key, value in model.trainer.metrics.items()}
        for name, value in metrics.items():
            task.get_logger().report_scalar("final", name, value, iteration=args.epochs)
        task.upload_artifact("final-metrics", metrics, wait_on_upload=True)
        best = Path(model.trainer.best)
        if not best.is_file():
            raise RuntimeError(f"Training produced no best checkpoint: {best}")
        output = OutputModel(task=task, name=f"{Path(args.model).stem} trained detector", framework="PyTorch",
                             label_enumeration={label: index for index, label in model.names.items()})
        output.update_weights(str(best))
        output.wait_for_uploads()
        print(f"Output model ID: {output.id}", flush=True)
    except Exception as exc:
        task.mark_failed(status_reason="YOLO12 GPU training failed", status_message=str(exc))
        task.close()
        raise
    task.close()


if __name__ == "__main__":
    main()
