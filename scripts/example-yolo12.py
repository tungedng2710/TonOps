#!/usr/bin/env python3
"""Register the vehicle dataset, run a YOLO12n pipeline, and serve detections."""

import argparse
import base64
import getpass
import importlib
import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

shared = importlib.import_module("example-models")


def prepare(dataset_path, files_url, dataset_id=""):
    from pathlib import Path
    import yaml
    from clearml import Dataset, Task
    from ultralytics import YOLO

    root = Path(dataset_path).resolve()
    config = yaml.safe_load((root / "data.yaml").read_text())
    directory = Path("docker-data/examples/yolo12/vehicle_30oct2025").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in ("train", "valid", "test"):
        images = sorted(path for path in (root / split / "images").iterdir()
                        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
        if not images:
            raise ValueError(f"Missing images in {root / split}")
        counts[split] = len(images)
        for image in images:
            if not (root / split / "labels" / (image.stem + ".txt")).is_file():
                raise ValueError(f"Missing annotation for {image}")
    portable = {"train": "train/images", "val": "valid/images", "test": "test/images",
                "nc": len(config["names"]), "names": config["names"]}
    portable_yaml = directory / "data.yaml"
    portable_yaml.write_text(yaml.safe_dump(portable, sort_keys=False))
    if dataset_id:
        dataset = Dataset.get(dataset_id=dataset_id)
    else:
        dataset = Dataset.create(dataset_name=root.name, dataset_project="Examples",
                                 dataset_version="1.0.0", dataset_tags=["example", "vehicles", "yolo12"])
        dataset.set_description(f"Vehicle detection dataset from {root}. Split counts: {counts}. "
                                "Five classes; configuration paths normalized for portability.")
        for split in counts:
            dataset.add_files(path=str(root / split / "images"), local_base_folder=str(root), max_workers=4)
            dataset.add_files(path=str(root / split / "labels"), wildcard="*.txt",
                              local_base_folder=str(root), max_workers=4)
        dataset.add_files(path=str(portable_yaml), local_base_folder=str(directory))
        dataset.upload(output_url=files_url, max_workers=2)
        dataset.finalize()
    local = Path(dataset.get_local_copy())
    runtime_yaml = directory / f"data-{dataset.id}.yaml"
    runtime_yaml.write_text(yaml.safe_dump(dict(portable, path=str(local)), sort_keys=False))
    sample = str(sorted((local / "valid/images").glob("*.jpg"))[0])
    Task.current_task().upload_artifact("dataset_summary", artifact_object={
        "dataset_id": dataset.id, "source": str(root), "counts": counts, "classes": config["names"]})
    weights = Path("docker-data/examples/yolo12/yolo12n.pt").resolve()
    weights.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    return {"dataset": str(runtime_yaml), "dataset_id": dataset.id, "sample": sample,
            "counts": counts, "weights": str(model.ckpt_path)}


def train(inputs, epochs=1, device="cpu", imgsz=640, batch=8, disable_cudnn=False):
    from pathlib import Path
    import torch
    from ultralytics import YOLO

    torch.set_num_threads(4)
    if str(disable_cudnn).lower() in ("true", "1"):
        torch.backends.cudnn.enabled = False
    model = YOLO(inputs["weights"])
    model.train(data=inputs["dataset"], epochs=int(epochs), imgsz=int(imgsz), batch=int(batch), device=str(device),
                workers=2, plots=True, amp=False, seed=42, name="yolo12-vehicle-example",
                project=str(Path("docker-data/examples/yolo12/runs").resolve()))
    return str(model.trainer.best)


def evaluate(inputs, weights, device="cpu", imgsz=640, batch=8, disable_cudnn=False):
    from pathlib import Path
    import torch
    from clearml import Task, OutputModel
    from ultralytics import YOLO

    torch.set_num_threads(4)
    if str(disable_cudnn).lower() in ("true", "1"):
        torch.backends.cudnn.enabled = False
    model = YOLO(weights)
    metrics = model.val(data=inputs["dataset"], imgsz=int(imgsz), batch=int(batch), device=str(device), workers=2, plots=True,
                        project=str(Path("docker-data/examples/yolo12/runs").resolve()), name="validation")
    task = Task.current_task()
    for name, value in metrics.results_dict.items():
        task.get_logger().report_scalar("validation", name, float(value), iteration=0)
    for path in metrics.save_dir.glob("*.png"):
        task.get_logger().report_image("validation", path.stem, iteration=0, local_path=str(path))
    output = OutputModel(task=task, name="YOLO12n vehicle_30oct2025 example", framework="PyTorch",
                         label_enumeration={label: index for index, label in model.names.items()})
    output.update_weights(weights)
    output.wait_for_uploads()
    output.publish()
    return {"model_id": output.id, "dataset_id": inputs["dataset_id"], "sample": inputs["sample"],
            "counts": inputs["counts"], "classes": model.names,
            "metrics": {k: float(v) for k, v in metrics.results_dict.items()}}


def pipeline(files_url, epochs, dataset_path, dataset_id, device, imgsz, batch, disable_cudnn):
    from clearml import PipelineController, Task

    pipe = PipelineController(name="YOLO12 vehicle detection", project="Examples", version="2.0.0",
                              pool_frequency=0.05, add_pipeline_tags=True, output_uri=files_url)
    common = {"packages": ["clearml", "ultralytics", "torch"], "output_uri": files_url}
    pipe.add_parameter("epochs", epochs)
    pipe.add_parameter("dataset_path", dataset_path)
    pipe.add_parameter("dataset_id", dataset_id or "")
    pipe.add_parameter("device", device)
    pipe.add_parameter("imgsz", imgsz)
    pipe.add_parameter("batch", batch)
    pipe.add_parameter("disable_cudnn", disable_cudnn)
    compute = {"device": "${pipeline.device}", "imgsz": "${pipeline.imgsz}", "batch": "${pipeline.batch}",
               "disable_cudnn": "${pipeline.disable_cudnn}"}
    pipe.add_function_step(name="prepare", function=prepare, function_return=["inputs"],
                           function_kwargs={"dataset_path": "${pipeline.dataset_path}",
                                            "dataset_id": "${pipeline.dataset_id}", "files_url": files_url},
                           task_type="data_processing", **common)
    pipe.add_function_step(name="train", function=train,
                           function_kwargs={"inputs": "${prepare.inputs}", "epochs": "${pipeline.epochs}", **compute},
                           function_return=["weights"], task_type="training", **common)
    pipe.add_function_step(name="evaluate", function=evaluate,
                           function_kwargs={"inputs": "${prepare.inputs}", "weights": "${train.weights}", **compute},
                           function_return=["result"], task_type="testing", **common)
    try:
        pipe.start_locally(run_pipeline_steps_locally=True)
        if not pipe.is_successful():
            raise RuntimeError("YOLO12 pipeline failed; inspect its run in ClearML")
        task = Task.get_task(task_id=pipe.get_pipeline_dag()["evaluate"].executed)
        return task.artifacts["result"].get()
    finally:
        pipe.stop()


class Handler(BaseHTTPRequestHandler):
    reply = shared.PredictionHandler.reply

    def detect(self, image, confidence=0.25):
        started = time.monotonic()
        with self.server.model_lock:
            result = self.server.model.predict(image, imgsz=self.server.imgsz, conf=confidence, device="cpu", verbose=False)[0]
        detections = [{"class_id": int(box.cls.item()), "label": result.names[int(box.cls.item())],
                       "confidence": float(box.conf.item()), "bbox_xyxy": box.xyxy[0].tolist()}
                      for box in result.boxes]
        with self.server.stats_lock:
            self.server.stats["requests"] += 1
            self.server.stats["latency_ms"] = round((time.monotonic() - started) * 1000)
        self.reply(200, {"model": "YOLO12n", "image_size": list(result.orig_shape), "detections": detections})

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"status": "ok", "model": "YOLO12n"})
        elif self.path == "/predict/yolo12":
            self.detect(self.server.sample)
        else:
            self.reply(404, {"error": "unknown route"})

    def do_POST(self):
        from PIL import Image, UnidentifiedImageError
        if self.path != "/predict/yolo12":
            return self.reply(404, {"error": "unknown route"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 8_000_000:
                raise ValueError("body must contain at most 8 MB")
            payload = json.loads(self.rfile.read(length))
            confidence = float(payload.get("confidence", 0.25))
            if not 0 < confidence <= 1:
                raise ValueError("confidence must be between 0 and 1")
            image = Image.open(io.BytesIO(base64.b64decode(payload["image_base64"], validate=True)))
            if image.width * image.height > 16_000_000:
                raise ValueError("image must contain at most 16 million pixels")
            self.detect(image.convert("RGB"), confidence)
        except (ValueError, TypeError, KeyError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            self.reply(400, {"error": str(error)})

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:7862")
    parser.add_argument("--web-url", default="http://27.66.108.30:7861")
    parser.add_argument("--files-url", default="http://27.66.108.30:7863")
    parser.add_argument("--public-url", default="http://27.66.108.30:7872")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7872)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--dataset-path", default="/root/tungn197/AI-Traffic-Analysis/data/vehicle_30oct2025")
    parser.add_argument("--dataset-id", help="reuse a registered ClearML dataset")
    parser.add_argument("--device", default="cpu", help="training device, e.g. cpu or 1")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--disable-cudnn", action="store_true", help="use native CUDA kernels if cuDNN libraries are incompatible")
    parser.add_argument("--train-only", action="store_true", help="publish the run and model without starting an endpoint")
    parser.add_argument("--model-id", help="serve an existing model without running the pipeline again")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("epochs must be positive")
    api = shared.Api(args.api_url, "admin", os.environ.pop("EXAMPLES_PASSWORD", None) or getpass.getpass("Admin password: "))
    os.environ.update(CLEARML_API_HOST=args.api_url, CLEARML_WEB_HOST=args.web_url,
                      CLEARML_FILES_HOST=args.files_url, CLEARML_AUTH_TOKEN=api.token)
    from clearml import Dataset, Model, StorageManager
    from ultralytics import YOLO
    from pathlib import Path
    import torch

    torch.set_num_threads(4)
    if args.model_id:
        if not args.dataset_id:
            parser.error("--model-id requires --dataset-id to select a vehicle sample")
        result = {"model_id": args.model_id, "dataset_id": args.dataset_id}
    else:
        result = pipeline(args.files_url, args.epochs, args.dataset_path, args.dataset_id,
                          args.device, args.imgsz, args.batch, args.disable_cudnn)
        manifest = Path("docker-data/examples/yolo12/vehicle_30oct2025/result.json")
        manifest.write_text(json.dumps(result, indent=2))
    if args.train_only:
        print(json.dumps(result), flush=True)
        return
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    serving = False
    registered = False
    entry = None
    try:
        model = Model(model_id=result["model_id"])
        server.model = YOLO(StorageManager.get_local_copy(model.url))
        local = Path(Dataset.get(dataset_id=result["dataset_id"]).get_local_copy())
        server.sample = str(sorted((local / "valid/images").glob("*.jpg"))[0])
        server.imgsz = args.imgsz
        server.model_lock = threading.Lock()
        server.stats_lock = threading.Lock()
        server.stats = {"requests": 0, "latency_ms": 0}
        server.model.predict(server.sample, imgsz=args.imgsz, device="cpu", verbose=False)
        entry = {"container_id": f"examples-yolo12-{args.port}", "endpoint_name": "YOLO12 vehicle detection",
                 "endpoint_url": args.public_url.rstrip("/") + "/predict/yolo12", "model_name": "YOLO12n vehicle_30oct2025 example",
                 "model_source": "Ultralytics", "model_version": "2.0.0", "input_type": "image",
                 "input_size": f"{args.imgsz}x{args.imgsz}", "tags": ["example", "yolo12", "vehicles"],
                 "reference": [{"type": "model", "value": model.id},
                               {"type": "task", "value": result["dataset_id"]}]}
        threading.Thread(target=server.serve_forever, daemon=True).start()
        serving = True
        api.call("serving.register_container", dict(entry, timeout=120))
        registered = True
        print(json.dumps(result), flush=True)
        print("Endpoint online: " + entry["endpoint_url"], flush=True)
        started = time.monotonic()
        previous = 0
        while True:
            with server.stats_lock:
                stats = dict(server.stats)
            try:
                api.call("serving.container_status_report", dict(entry, uptime_sec=int(time.monotonic() - started),
                         requests_num=stats["requests"], requests_min=(stats["requests"] - previous) * 2,
                         latency_ms=stats["latency_ms"]))
                previous = stats["requests"]
            except (shared.requests.RequestException, RuntimeError) as error:
                print(f"Heartbeat failed: {type(error).__name__}; retrying", flush=True)
            time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        if serving:
            server.shutdown()
        if registered:
            api.call("serving.unregister_container", {"container_id": entry["container_id"]})
        server.server_close()


if __name__ == "__main__":
    main()
