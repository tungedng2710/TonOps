#!/usr/bin/env python3
"""Use TonOps to version an object detection dataset, train, and predict."""

import argparse
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
IMAGE = "clearml/yolo12-worker:torch2.7.1-cu126"
PROJECT = "Vehicle Detection/YOLO12"
STATE = ROOT / "docker-data/examples/object-detection"


def api_call(session, service, action, payload):
    response = session.send_request(service=service, action=action, method="post", json=payload)
    response.raise_for_status()
    body = response.json()
    if body.get("meta", {}).get("result_code", 200) != 200:
        raise RuntimeError(f"{service}.{action}: {body.get('meta', {}).get('result_msg', 'API error')}")
    return body["data"]


def ensure_queue(session, name):
    result = api_call(session, "queues", "get_all", {"name": "^" + re.escape(name) + "$"})
    matches = [queue for queue in result.get("queues", []) if queue["name"] == name]
    if matches:
        return matches[0]["id"]
    return api_call(session, "queues", "create", {"name": name})["id"]


def check_task(task, wait, timeout, poll_interval):
    deadline = time.monotonic() + timeout
    while True:
        task.reload()
        status = str(task.status)
        print(json.dumps({"task_id": task.id, "status": status,
                          "message": task.data.status_message,
                          "worker": task.data.last_worker}), flush=True)
        if status in {"completed", "published"}:
            print(json.dumps({"metrics": task.get_last_scalar_metrics(),
                              "artifacts": list(task.artifacts),
                              "output_models": [model.id for model in task.models.get("output", [])]}, indent=2))
            return 0
        if status in {"failed", "stopped", "closed"}:
            return 1
        if not wait:
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print("Timed out waiting; the task remains queued/running. Use check again.", file=sys.stderr)
            return 2
        time.sleep(min(poll_interval, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-file", type=Path, help="Private SDK/worker config (default: ~/clearml.conf)")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Check YOLO images/labels locally before uploading")
    register = commands.add_parser("register", help="Upload and finalize a versioned detection dataset")
    for command in (validate, register):
        command.add_argument("--data", type=Path, default=HERE / "data.yaml")
        command.add_argument("--dataset-root", type=Path, required=True)
    register.add_argument("--project", default=PROJECT)
    register.add_argument("--name", default="vehicles")
    register.add_argument("--version", default="1.0.0")
    register.add_argument("--output-uri", help="Dataset storage URI; defaults to your ClearML storage settings")
    register.add_argument("--dataset-id-file", type=Path, default=STATE / "dataset-id")
    queue = commands.add_parser("queue", help="Create the queue if absent")
    queue.add_argument("--queue", default="gpu")
    commands.add_parser("workers", help="List workers seen in the last 120 seconds")
    submit = commands.add_parser("submit")
    submit.add_argument("--queue", default="gpu")
    submit.add_argument("--project", default=PROJECT)
    submit.add_argument("--name", default="YOLO12n Docker GPU smoke")
    submit.add_argument("--image", default=IMAGE)
    submit.add_argument("--dataset-id", default="")
    submit.add_argument("--model", default="yolo12n.pt")
    submit.add_argument("--data", default="coco8.yaml")
    submit.add_argument("--epochs", type=int, default=1)
    submit.add_argument("--imgsz", type=int, default=320)
    submit.add_argument("--batch", type=int, default=2)
    submit.add_argument("--workers", type=int, default=0)
    submit.add_argument("--fraction", type=float, default=1.0)
    submit.add_argument("--output-uri", help="Defaults to the project's configured output storage")
    submit.add_argument("--task-id-file", type=Path, default=STATE / "task-id")
    check = commands.add_parser("check")
    check.add_argument("--task-id", required=True)
    predict = commands.add_parser("predict", help="Download a TonOps model and detect objects in an image")
    predict.add_argument("--model-id", required=True)
    predict.add_argument("--source", type=Path, required=True, help="Input image")
    predict.add_argument("--device", default="cpu")
    predict.add_argument("--confidence", type=float, default=0.25)
    predict.add_argument("--output-dir", type=Path, default=STATE / "predictions")
    for command in (submit, check):
        command.add_argument("--wait", action="store_true")
        command.add_argument("--timeout", type=float, default=1800)
        command.add_argument("--poll-interval", type=float, default=10)
    args = parser.parse_args()
    if hasattr(args, "timeout") and (args.timeout <= 0 or args.poll_interval <= 0):
        parser.error("timeout and poll-interval must be positive")
    if args.command == "submit" and (args.epochs < 1 or args.imgsz < 32 or args.batch < 1
                                     or args.workers < 0 or not 0 < args.fraction <= 1):
        parser.error("Invalid training parameters: epochs/batch > 0, imgsz >= 32, workers >= 0, fraction in (0,1]")
    if args.command == "predict" and (not args.source.is_file() or not 0 < args.confidence <= 1):
        parser.error("source must be an image file and confidence must be in (0,1]")
    if args.config_file:
        import os
        os.environ["CLEARML_CONFIG_FILE"] = str(args.config_file.expanduser().resolve())
    if args.command == "validate":
        from dataset import prepare_dataset
        report, _ = prepare_dataset(args.data, args.dataset_root)
        print(json.dumps(report, indent=2))
        return 0
    if args.command == "register":
        from dataset import register_dataset
        dataset_id, report = register_dataset(args.data, args.dataset_root, args.project,
                                              args.name, args.version, args.output_uri)
        args.dataset_id_file.parent.mkdir(parents=True, exist_ok=True)
        args.dataset_id_file.write_text(dataset_id + "\n")
        print(json.dumps({"dataset_id": dataset_id, "validation": report}, indent=2))
        return 0
    if args.command == "predict":
        return predict_image(args)
    from clearml import Task
    from clearml.backend_api.session import Session

    if args.command == "check":
        task = Task.get_task(task_id=args.task_id)
    else:
        session = Session()
        if args.command == "workers":
            print(json.dumps(api_call(session, "workers", "get_all", {"last_seen": 120}), indent=2))
            return 0
        queue_id = ensure_queue(session, args.queue)
        print(f"Queue {args.queue}: {queue_id}", flush=True)
        if args.command == "queue":
            return 0
        task = Task.create(
            project_name=args.project, task_name=args.name, task_type=Task.TaskTypes.training,
            script=str(ROOT / "examples/vehicle_detection_yolo12/train.py"),
            force_single_script_file=True, add_task_init_call=False,
            requirements_file=str(ROOT / "workers/clearml-agent/requirements-task.txt"),
            docker=args.image, docker_args="--network=host --shm-size=2g",
        )
        task.set_parameters({f"Training/{name}": getattr(args, name) for name in
                             ("data", "dataset_id", "model", "epochs", "imgsz", "batch", "workers", "fraction")})
        if args.output_uri:
            task.output_uri = args.output_uri
        # Persist ID before enqueueing so a failed enqueue can be investigated.
        args.task_id_file.parent.mkdir(parents=True, exist_ok=True)
        args.task_id_file.write_text(task.id + "\n")
        print(f"Task ID: {task.id}\nResults: {task.get_output_log_web_page()}", flush=True)
        Task.enqueue(task, queue_id=queue_id)
    return check_task(task, args.wait, args.timeout, args.poll_interval)


def predict_image(args):
    from clearml import Model
    from ultralytics import YOLO

    weights = Model(model_id=args.model_id).get_local_copy(raise_on_error=True)
    results = YOLO(weights).predict(source=str(args.source), device=args.device,
                                   conf=args.confidence, verbose=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = results[0]
    image = args.output_dir / args.source.name
    result.save(filename=str(image))
    detections = [{"class_id": int(box.cls.item()), "label": result.names[int(box.cls.item())],
                   "confidence": float(box.conf.item()), "bbox_xyxy": box.xyxy[0].tolist()}
                  for box in result.boxes]
    payload = {"model_id": args.model_id, "source": str(args.source.resolve()),
               "annotated_image": str(image.resolve()), "detections": detections}
    (args.output_dir / (args.source.stem + ".json")).write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
