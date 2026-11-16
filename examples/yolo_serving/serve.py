"""Serve registered YOLO checkpoints and report real ClearML endpoint activity."""

import base64
import binascii
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import threading
import time

os.environ.setdefault("YOLO_AUTOINSTALL", "false")

from clearml.backend_api.session import Session
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from ultralytics import YOLO

LOG = logging.getLogger("yolo-serving")
ROOT = Path(os.environ.get("MODEL_DIRECTORY", "/models"))
PUBLIC_URL = os.environ.get("SERVING_PUBLIC_URL", "http://localhost:7872").rstrip("/")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_BODY_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 20_000_000
HEARTBEAT_SECONDS = 15


class ImageRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=4 * ((MAX_IMAGE_BYTES + 2) // 3))


@dataclass
class ModelEntry:
    metadata: dict
    model: object
    started: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)
    stats_lock: threading.Lock = field(default_factory=threading.Lock)
    requests: int = 0
    failures: int = 0
    latency_ms: int = 0
    previous_requests: int = 0
    previous_report: float = field(default_factory=time.monotonic)
    last_heartbeat: float = 0

    def public_info(self):
        return {key: self.metadata[key] for key in ("alias", "id", "name", "version")}

    def registration(self):
        meta = self.metadata
        return {
            "container_id": f"tungn197-yolo-{meta['alias']}-{meta['id'][:8]}",
            "endpoint_name": f"{meta['alias'].upper()} image detection",
            "endpoint_url": f"{PUBLIC_URL}/predict/{meta['alias']}",
            "model_name": meta["name"], "model_version": meta["version"],
            "model_source": "Ultralytics / PyTorch", "input_type": "image/base64",
            "tags": ["yolo", "smoke-model", "owner:tungn197"],
            "reference": [{"type": "model", "value": meta["id"]}],
        }


def api_call(session, action, body):
    service, action = action.split(".", 1)
    response = session.send_request(service=service, action=action, json=body)
    response.raise_for_status()
    envelope = response.json()
    if envelope.get("meta", {}).get("result_code", 200) != 200:
        raise RuntimeError("ClearML API rejected the serving report")
    return envelope.get("data", {})


def report_activity(session, entries, stop):
    while not stop.is_set():
        for entry in entries.values():
            now = time.monotonic()
            with entry.stats_lock:
                count = entry.requests
                report = dict(entry.registration(), uptime_sec=int(now - entry.started),
                              requests_num=count, latency_ms=entry.latency_ms,
                              requests_min=60 * (count - entry.previous_requests) /
                              max(now - entry.previous_report, 0.001))
            try:
                api_call(session, "serving.container_status_report", report)
                with entry.stats_lock:
                    entry.previous_requests = count
                    entry.previous_report = now
                    entry.last_heartbeat = time.time()
            except Exception as error:
                LOG.warning("Endpoint metrics update failed: %s", type(error).__name__)
        stop.wait(HEARTBEAT_SECONDS)


@asynccontextmanager
async def lifespan(application):
    credentials = json.loads((ROOT / "clearml-api.json").read_text())
    session = Session(host=credentials["api_url"], api_key=credentials["access_key"],
                      secret_key=credentials["secret_key"])
    identity = api_call(session, "users.get_current_user", {})["user"]
    if identity["id"] != credentials["user_id"]:
        raise RuntimeError("Serving account differs from the prepared account")
    entries = {}
    registered = []
    stop = threading.Event()
    thread = None
    try:
        for meta in json.loads((ROOT / "models.json").read_text())["models"]:
            path = (ROOT / meta["file"]).resolve()
            if not path.is_relative_to(ROOT.resolve()):
                raise RuntimeError("Model file must be inside the model directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
                raise RuntimeError("Model checkpoint hash differs from its manifest")
            record = api_call(session, "models.get_by_id", {"model": meta["id"]})["model"]
            if record["user"] != identity["id"] or record["uri"] != meta["uri"]:
                raise RuntimeError("Model ownership or registered weights changed")
            entry = ModelEntry(meta, YOLO(str(path)))
            # Load and execute before reporting an endpoint as ready.
            entry.model.predict(Image.new("RGB", (320, 320)), device="cpu", imgsz=320, verbose=False)
            entries[meta["alias"]] = entry
        application.state.entries = entries
        application.state.owner = identity["name"]
        for entry in entries.values():
            api_call(session, "serving.register_container", dict(entry.registration(), timeout=120))
            registered.append(entry)
        thread = threading.Thread(target=report_activity, args=(session, entries, stop), daemon=True)
        thread.start()
        LOG.info("Serving %s models as %s", len(entries), identity["name"])
        yield
    finally:
        stop.set()
        if thread:
            thread.join(timeout=5)
        for entry in registered:
            try:
                api_call(session, "serving.unregister_container",
                         {"container_id": entry.registration()["container_id"]})
            except Exception:
                LOG.warning("Endpoint unregister failed; registration expires in 120 seconds")


app = FastAPI(title="Tung Nguyen YOLO model serving", lifespan=lifespan,
              description="Real inference from registered smoke-training checkpoints. "
                          "Prediction routes follow the existing trusted-network demo pattern.")


@app.middleware("http")
async def bound_request_size(request, call_next):
    if request.method == "POST":
        try:
            length = int(request.headers.get("content-length", ""))
        except ValueError:
            return JSONResponse({"detail": "Content-Length is required"}, status_code=411)
        if length > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Request exceeds 12 MiB"}, status_code=413)
    return await call_next(request)


@app.get("/health")
def health():
    entries = app.state.entries
    return {"status": "ok", "owner": app.state.owner, "device": "cpu",
            "models": [entry.public_info() for entry in entries.values()],
            "telemetry": {alias: {"last_heartbeat": entry.last_heartbeat,
                                  "reporting": time.time() - entry.last_heartbeat < 120}
                          for alias, entry in entries.items()}}


@app.get("/models")
def models():
    return [{**entry.public_info(), "endpoint": entry.registration()["endpoint_url"],
             "multipart_endpoint": entry.registration()["endpoint_url"] + "/image"}
            for entry in app.state.entries.values()]


def run_prediction(alias, content, confidence):
    entry = app.state.entries.get(alias)
    if entry is None:
        raise HTTPException(404, "Unknown model")
    started = time.monotonic()
    success = False
    try:
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image must contain 1 byte to 8 MiB")
        try:
            with Image.open(BytesIO(content)) as source:
                if source.width * source.height > MAX_PIXELS:
                    raise HTTPException(413, "Image exceeds 20 million pixels")
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ImportError):
            raise HTTPException(400, "Upload a supported image") from None
        with entry.lock:
            result = entry.model.predict(image, device="cpu", conf=confidence, imgsz=640, verbose=False)[0]
        detections = [{"class_id": int(box.cls.item()),
                       "label": result.names[int(box.cls.item())],
                       "confidence": float(box.conf.item()),
                       "bbox_xyxy": box.xyxy[0].tolist()} for box in result.boxes]
        success = True
        return {"model": alias, "model_id": entry.metadata["id"],
                "version": entry.metadata["version"], "width": image.width, "height": image.height,
                "detections": detections, "latency_ms": round(1000 * (time.monotonic() - started), 2)}
    finally:
        with entry.stats_lock:
            entry.requests += 1
            entry.failures += int(not success)
            entry.latency_ms = round(1000 * (time.monotonic() - started))


@app.post("/predict/{alias}")
def predict_json(alias: str, payload: ImageRequest, confidence: float = Query(0.1, gt=0, le=1)):
    try:
        content = base64.b64decode(payload.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "image_base64 must contain valid base64") from None
    return run_prediction(alias, content, confidence)


@app.post("/predict/{alias}/image")
def predict_image(alias: str, file: UploadFile, confidence: float = Query(0.1, gt=0, le=1)):
    return run_prediction(alias, file.file.read(MAX_IMAGE_BYTES + 1), confidence)
