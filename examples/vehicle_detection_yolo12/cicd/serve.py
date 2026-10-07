"""Small YOLO12 image prediction API for the CI/CD deployment example."""

from contextlib import asynccontextmanager
from io import BytesIO
import json
import os
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

MODEL_PATH = Path(os.environ.get("MODEL_PATH", "/opt/yolo12/model/best.pt"))
REVISION = os.environ.get("MODEL_REVISION", "local")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
lock = Lock()


@asynccontextmanager
async def lifespan(app):
    app.state.model = YOLO(str(MODEL_PATH))
    app.state.metrics = json.loads(MODEL_PATH.with_name("metrics.json").read_text())
    yield


app = FastAPI(title="YOLO12 CI/CD demo", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "revision": REVISION, "model": "yolo12n",
            "training": app.state.metrics}


@app.post("/predict")
def predict(file: UploadFile, confidence: float = Query(0.1, gt=0, le=1)):
    content = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds 8 MiB")
    try:
        image = Image.open(BytesIO(content))
        if image.width * image.height > 20_000_000:
            raise HTTPException(413, "Image exceeds 20 million pixels")
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ImportError):
        # Ultralytics tries optional HEIF codecs after Pillow rejects a file.
        raise HTTPException(400, "Upload a valid supported image")
    with lock:
        result = app.state.model.predict(image, device="cpu", conf=confidence,
                                         imgsz=320, verbose=False)[0]
    detections = [{"class_id": int(box.cls.item()),
                   "label": result.names[int(box.cls.item())],
                   "confidence": float(box.conf.item()),
                   "bbox_xyxy": box.xyxy[0].tolist()} for box in result.boxes]
    return {"revision": REVISION, "width": image.width, "height": image.height,
            "detections": detections}
