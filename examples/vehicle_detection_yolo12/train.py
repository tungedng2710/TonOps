#!/usr/bin/env python3
"""Train a YOLO12 vehicle detector and track the run in ClearML."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any


def _use_consistent_cudnn() -> None:
    """Keep all dynamically loaded cuDNN components on the same version.

    This host has both pip and system cuDNN installations. PyTorch otherwise
    loads the pip shim and a system sublibrary, which produces a version mismatch.
    """
    marker = "YOLO12_CUDNN_PATH_CONFIGURED"
    if os.environ.get(marker) == "1":
        return

    env = os.environ.copy()
    system_cudnn = Path("/lib/x86_64-linux-gnu/libcudnn.so.9")
    if system_cudnn.is_file():
        current = env.get("LD_PRELOAD", "")
        env["LD_PRELOAD"] = f"{system_cudnn}:{current}" if current else str(system_cudnn)
    else:
        python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
        bundled = Path(sys.prefix) / "lib" / python_dir / "site-packages" / "nvidia" / "cudnn" / "lib"
        if not bundled.is_dir():
            return
        current = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{bundled}:{current}" if current else str(bundled)
    env[marker] = "1"
    os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], env)


_use_consistent_cudnn()

# This shared environment contains a newer chardet used by unrelated packages.
# Requests can use charset-normalizer instead, so keep that non-fatal warning out
# of the training log.
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 .* or chardet .* doesn't match a supported version!",
)

import yaml


HERE = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.yaml")
    parser.add_argument("--model", default="yolo12n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--fraction", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=HERE / "runs")
    parser.add_argument("--run-name", default="yolo12n-baseline")
    parser.add_argument("--clearml-project", default="Vehicle Detection/YOLO12")
    parser.add_argument("--clearml-task", default="YOLO12n baseline")
    parser.add_argument(
        "--clearml",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable ClearML tracking (use --no-clearml for a local-only run).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate paths and YOLO labels without loading a model.",
    )
    return parser.parse_args()


def _class_names(dataset: dict[str, Any]) -> list[str]:
    names = dataset.get("names")
    if isinstance(names, list):
        return [str(name) for name in names]
    if isinstance(names, dict):
        ordered = sorted(((int(index), name) for index, name in names.items()))
        if [index for index, _ in ordered] != list(range(len(ordered))):
            raise ValueError("Dataset class IDs must be contiguous and start at zero")
        return [str(name) for _, name in ordered]
    raise ValueError("data.yaml must define 'names' as a list or ID-to-name mapping")


def validate_dataset(data_file: Path) -> dict[str, Any]:
    data_file = data_file.expanduser().resolve()
    if not data_file.is_file():
        raise FileNotFoundError(f"Dataset configuration not found: {data_file}")

    dataset = yaml.safe_load(data_file.read_text())
    if not isinstance(dataset, dict):
        raise ValueError(f"Invalid YAML mapping in {data_file}")

    names = _class_names(dataset)
    root = Path(dataset.get("path", data_file.parent)).expanduser()
    if not root.is_absolute():
        root = (data_file.parent / root).resolve()

    errors: list[str] = []
    report: dict[str, Any] = {
        "dataset_root": str(root),
        "classes": names,
        "splits": {},
    }

    for config_key, display_name in (("train", "train"), ("val", "valid"), ("test", "test")):
        configured_path = dataset.get(config_key)
        if not configured_path:
            if config_key != "test":
                errors.append(f"Missing required '{config_key}' entry")
            continue

        image_dir = Path(configured_path).expanduser()
        if not image_dir.is_absolute():
            image_dir = root / image_dir
        image_dir = image_dir.resolve()
        label_dir = image_dir.parent / "labels"

        if not image_dir.is_dir():
            errors.append(f"Missing {display_name} image directory: {image_dir}")
            continue
        if not label_dir.is_dir():
            errors.append(f"Missing {display_name} label directory: {label_dir}")
            continue

        images = sorted(path for path in image_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
        labels = sorted(label_dir.rglob("*.txt"))
        expected_labels: set[Path] = set()
        class_counts: Counter[int] = Counter()
        object_count = 0

        for image in images:
            relative = image.relative_to(image_dir)
            label = (label_dir / relative).with_suffix(".txt")
            expected_labels.add(label)
            if not label.is_file():
                errors.append(f"Image has no label file: {image}")
                continue

            for line_number, line in enumerate(label.read_text().splitlines(), start=1):
                if not line.strip():
                    continue
                fields = line.split()
                if len(fields) != 5:
                    errors.append(f"{label}:{line_number}: expected 5 fields, found {len(fields)}")
                    continue
                try:
                    class_value, x_center, y_center, width, height = map(float, fields)
                except ValueError:
                    errors.append(f"{label}:{line_number}: contains a non-numeric value")
                    continue
                values = (x_center, y_center, width, height)
                class_id = int(class_value)
                if class_value != class_id or not 0 <= class_id < len(names):
                    errors.append(f"{label}:{line_number}: invalid class ID {class_value}")
                    continue
                if not all(math.isfinite(value) for value in values):
                    errors.append(f"{label}:{line_number}: contains a non-finite box value")
                    continue
                if not (0 <= x_center <= 1 and 0 <= y_center <= 1 and 0 < width <= 1 and 0 < height <= 1):
                    errors.append(f"{label}:{line_number}: box values must be normalized to [0, 1]")
                    continue
                class_counts[class_id] += 1
                object_count += 1

        extra_labels = set(labels) - expected_labels
        for label in sorted(extra_labels):
            errors.append(f"Label has no matching image: {label}")

        report["splits"][display_name] = {
            "images": len(images),
            "labels": len(labels),
            "objects": object_count,
            "objects_by_class": {names[index]: class_counts[index] for index in range(len(names))},
        }

    if errors:
        preview = "\n".join(f"- {error}" for error in errors[:25])
        suffix = f"\n- ... and {len(errors) - 25} more" if len(errors) > 25 else ""
        raise ValueError(f"Dataset validation failed with {len(errors)} error(s):\n{preview}{suffix}")
    return report


def init_clearml(args: argparse.Namespace, dataset_report: dict[str, Any]):
    if not args.clearml:
        return None

    from clearml import Task

    # ClearML stores hierarchical names without whitespace around separators.
    project_name = "/".join(part.strip() for part in args.clearml_project.split("/"))
    try:
        task = Task.init(
            project_name=project_name,
            task_name=args.clearml_task,
            task_type=Task.TaskTypes.training,
            auto_connect_frameworks=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "ClearML task initialization failed. Verify the API credentials and "
            "project name, or add --no-clearml for a local-only run."
        ) from exc

    parameters = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in {"validate_only"}
    }
    task.connect(parameters, name="Training")
    task.connect_configuration(configuration=str(args.data.resolve()), name="Dataset configuration")
    task.upload_artifact("dataset-validation", dataset_report)
    return task


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.imgsz < 32 or args.batch == 0:
        raise ValueError("epochs must be positive, imgsz >= 32, and batch must not be zero")
    if not 0 < args.fraction <= 1:
        raise ValueError("fraction must be in the interval (0, 1]")

    dataset_report = validate_dataset(args.data)
    print(json.dumps(dataset_report, indent=2))
    if args.validate_only:
        return

    task = init_clearml(args, dataset_report)
    try:
        from ultralytics import YOLO

        args.output_dir.mkdir(parents=True, exist_ok=True)
        model = YOLO(args.model)
        result = model.train(
            data=str(args.data.resolve()),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            workers=args.workers,
            fraction=args.fraction,
            seed=args.seed,
            deterministic=True,
            project=str(args.output_dir.resolve()),
            name=args.run_name,
            exist_ok=True,
            plots=True,
        )

        save_dir = Path(result.save_dir)
        best_weights = save_dir / "weights" / "best.pt"
        if task and best_weights.is_file():
            task.upload_artifact("best-weights", best_weights, wait_on_upload=True)
        print(f"Training output: {save_dir}")
    finally:
        if task:
            task.close()


if __name__ == "__main__":
    main()
