"""Exercise the deployed serving contract without loading weights or contacting ClearML."""

import base64
from io import BytesIO
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from PIL import Image

SOURCE = Path(__file__).resolve().parents[1] / "examples/yolo_serving/serve.py"
spec = importlib.util.spec_from_file_location("yolo_serving_example", SOURCE)
serving = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = serving
spec.loader.exec_module(serving)


class YoloServingTests(unittest.TestCase):
    def setUp(self):
        model = MagicMock()
        box = MagicMock()
        box.cls.item.return_value = 2
        box.conf.item.return_value = 0.9
        box.xyxy.__getitem__.return_value.tolist.return_value = [1, 2, 3, 4]
        model.predict.return_value = [MagicMock(names={2: "car"}, boxes=[box])]
        self.entry = serving.ModelEntry({"alias": "yolo12", "id": "model-id", "name": "Detector",
                                         "version": "version-id"}, model)
        serving.app.state.entries = {"yolo12": self.entry}
        serving.app.state.owner = "Test user"
        self.client = TestClient(serving.app)
        output = BytesIO()
        Image.new("RGB", (16, 16)).save(output, format="PNG")
        self.image = output.getvalue()

    def test_json_and_multipart_return_same_real_model_contract(self):
        encoded = base64.b64encode(self.image).decode()
        first = self.client.post("/predict/yolo12", json={"image_base64": encoded})
        second = self.client.post("/predict/yolo12/image", files={"file": ("test.png", self.image)})
        for response in (first, second):
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result["model_id"], "model-id")
            self.assertEqual(result["width"], 16)
            self.assertEqual(result["detections"][0]["bbox_xyxy"], [1, 2, 3, 4])
            self.assertEqual(result["detections"][0]["label"], "car")
        self.assertEqual(self.entry.requests, 2)
        self.assertEqual(self.entry.failures, 0)

    def test_invalid_base64_and_image_never_run_inference(self):
        response = self.client.post("/predict/yolo12", json={"image_base64": "invalid!"})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/predict/yolo12/image", files={"file": ("test.png", b"invalid")})
        self.assertEqual(response.status_code, 400)
        self.entry.model.predict.assert_not_called()
        self.assertEqual(self.entry.failures, 1)

    def test_unknown_model_and_invalid_confidence(self):
        response = self.client.post("/predict/missing/image", files={"file": ("test.png", self.image)})
        self.assertEqual(response.status_code, 404)
        response = self.client.post("/predict/yolo12/image?confidence=2", files={"file": ("test.png", self.image)})
        self.assertEqual(response.status_code, 422)
        self.entry.model.predict.assert_not_called()

    def test_request_size_gate_and_missing_length(self):
        response = self.client.post("/predict/yolo12", content=b"{}",
                                    headers={"Content-Length": str(serving.MAX_BODY_BYTES + 1)})
        self.assertEqual(response.status_code, 413)
        response = self.client.post("/predict/yolo12", content=iter([b"{}"]),
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 411)

    def test_health_does_not_claim_unreported_metrics_are_current(self):
        result = self.client.get("/health").json()
        self.assertEqual(result["owner"], "Test user")
        self.assertFalse(result["telemetry"]["yolo12"]["reporting"])
        self.assertEqual(result["models"][0]["id"], "model-id")


if __name__ == "__main__":
    unittest.main()
