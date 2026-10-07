#!/usr/bin/env python3
"""Train the shared YOLO12 example on COCO8 and gate the serving checkpoint."""

import argparse
import json
import math
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from train import train_detector


def validate_metrics(metrics, minimum_map50):
    if not 0 <= minimum_map50 <= 1:
        raise ValueError("minimum mAP50 must be in [0, 1]")
    if not metrics or not all(math.isfinite(float(value)) for value in metrics.values()):
        raise ValueError("Training returned missing or nonfinite metrics")
    score = float(metrics["metrics/mAP50(B)"])
    if not 0 <= score <= 1 or score < minimum_map50:
        raise ValueError(f"mAP50 {score:.6f} is below the gate {minimum_map50:.6f}")
    return score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--minimum-map50", type=float, default=0.01)
    parser.add_argument("--revision", default="local")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("epochs must be positive")
    from ultralytics import settings
    import torch

    torch.set_num_threads(2)
    settings.update({"clearml": False, "wandb": False, "mlflow": False})
    output = HERE / "build"
    output.mkdir(parents=True, exist_ok=True)
    # Never leave an older checkpoint eligible for a failed run's image build.
    for name in ("best.pt", "metrics.json"):
        (output / name).unlink(missing_ok=True)
    training = argparse.Namespace(model="yolo12n.pt", epochs=args.epochs, imgsz=320,
                                  batch=2, workers=0, fraction=1.0)
    model = train_detector(training, "coco8.yaml", args.revision, device="cpu",
                           project=str(output / "runs"))
    metrics = {key: float(value) for key, value in model.trainer.metrics.items()}
    score = validate_metrics(metrics, args.minimum_map50)
    best = Path(model.trainer.best)
    if not best.is_file():
        raise RuntimeError("Training produced no best checkpoint")
    shutil.copy2(best, output / "best.pt")
    report = {"revision": args.revision, "dataset": "coco8", "epochs": args.epochs,
              "minimum_map50": args.minimum_map50, "metrics": metrics}
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    # Select a validation image with a detection at the API's default threshold.
    # This checks serving mechanics; the accuracy gate above uses all val images.
    from ultralytics import YOLO
    detector = YOLO(str(best))
    dataset_root = Path(model.trainer.data["path"])
    for sample in sorted((dataset_root / "images/val").glob("*.jpg")):
        prediction = detector.predict(str(sample), device="cpu", conf=0.1, imgsz=320, verbose=False)[0]
        if len(prediction.boxes):
            shutil.copy2(sample, output / "sample.jpg")
            break
    else:
        raise RuntimeError("No COCO8 validation image produced a detection for the serving smoke check")
    print(json.dumps({"gate": "passed", "map50": score, "revision": args.revision}), flush=True)


if __name__ == "__main__":
    main()
