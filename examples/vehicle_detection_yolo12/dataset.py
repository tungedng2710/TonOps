"""Validate a YOLO dataset and register a portable version in TonOps."""

from collections import Counter
import math
from pathlib import Path
import tempfile
from typing import Any

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def _class_names(dataset: dict[str, Any]) -> list[str]:
    names = dataset.get("names")
    if isinstance(names, list):
        if not names:
            raise ValueError("Dataset must define at least one class")
        return [str(name) for name in names]
    if isinstance(names, dict):
        ordered = sorted(((int(index), name) for index, name in names.items()))
        if not ordered or [index for index, _ in ordered] != list(range(len(ordered))):
            raise ValueError("Dataset class IDs must be contiguous and start at zero")
        return [str(name) for _, name in ordered]
    raise ValueError("data.yaml must define 'names' as a list or ID-to-name mapping")


def prepare_dataset(data_file: Path, dataset_root: Path | None = None):
    """Validate annotations and return a report plus YAML portable to any worker."""
    import yaml

    data_file = data_file.expanduser().resolve()
    if not data_file.is_file():
        raise FileNotFoundError(f"Dataset configuration not found: {data_file}")

    dataset = yaml.safe_load(data_file.read_text())
    if not isinstance(dataset, dict):
        raise ValueError(f"Invalid YAML mapping in {data_file}")

    names = _class_names(dataset)
    root = Path(dataset_root if dataset_root is not None else dataset.get("path", data_file.parent)).expanduser()
    if not root.is_absolute():
        root = (Path.cwd() / root if dataset_root is not None else data_file.parent / root)
    root = root.resolve()
    portable = {"path": ".", "names": names}

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

        if not isinstance(configured_path, str):
            errors.append(f"{config_key} must point to one images directory")
            continue
        image_dir = Path(configured_path).expanduser()
        if not image_dir.is_absolute():
            image_dir = root / image_dir
        image_dir = image_dir.resolve()
        label_dir = image_dir.parent / "labels"
        try:
            portable[config_key] = image_dir.relative_to(root).as_posix()
        except ValueError:
            errors.append(f"{display_name} directory must be inside dataset root: {image_dir}")
            continue
        if image_dir.name != "images":
            errors.append(f"{display_name} directory must be named 'images' with sibling 'labels'")
            continue

        if not image_dir.is_dir():
            errors.append(f"Missing {display_name} image directory: {image_dir}")
            continue
        if not label_dir.is_dir():
            errors.append(f"Missing {display_name} label directory: {label_dir}")
            continue

        images = sorted(path for path in image_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
        if not images:
            errors.append(f"No images in {display_name} directory: {image_dir}")
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
                if not math.isfinite(class_value):
                    errors.append(f"{label}:{line_number}: contains a non-finite class ID")
                    continue
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
    return report, portable


def register_dataset(data_file, dataset_root, project, name, version, output_uri):
    """Upload images, labels, normalized YAML, and validation metadata together."""
    import yaml
    from clearml import Dataset

    report, portable = prepare_dataset(data_file, dataset_root)
    root = Path(report["dataset_root"])
    dataset = Dataset.create(dataset_project=project, dataset_name=name,
                             dataset_version=version, output_uri=output_uri,
                             dataset_tags=["object-detection", "yolo"])
    for split in ("train", "val", "test"):
        if split not in portable:
            continue
        images = root / portable[split]
        dataset.add_files(path=str(images), local_base_folder=str(root),
                          wildcard=[f"*{suffix}" for suffix in IMAGE_SUFFIXES] +
                                   [f"*{suffix.upper()}" for suffix in IMAGE_SUFFIXES], max_workers=4)
        dataset.add_files(path=str(images.parent / "labels"), local_base_folder=str(root),
                          wildcard="*.txt", max_workers=4)
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "data.yaml"
        config.write_text(yaml.safe_dump(portable, sort_keys=False))
        dataset.add_files(path=str(config), local_base_folder=directory)
        dataset.set_metadata(report, metadata_name="validation", ui_visible=False)
        dataset.upload(output_url=output_uri, max_workers=2)
        dataset.finalize()
    return dataset.id, report

