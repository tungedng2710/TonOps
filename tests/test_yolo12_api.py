"""Check serving input validation with the same dependencies used by CI."""

from io import BytesIO
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

AVAILABLE = all(importlib.util.find_spec(name) for name in ("fastapi", "ultralytics", "httpx"))
if AVAILABLE:
    from fastapi.testclient import TestClient
    from PIL import Image
    source = Path(__file__).resolve().parents[1] / "examples/vehicle_detection_yolo12/cicd/serve.py"
    spec = importlib.util.spec_from_file_location("serving_example", source)
    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)


@unittest.skipUnless(AVAILABLE, "Run in tonops/yolo12-ci:local for the serving dependencies")
class ServingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "metrics.json").write_text(json.dumps({"revision": "test-commit"}))
        self.model = MagicMock()
        box = MagicMock()
        box.cls.item.return_value = 2
        box.conf.item.return_value = 0.8
        box.xyxy.__getitem__.return_value.tolist.return_value = [1, 2, 3, 4]
        result = MagicMock(names={2: "car"}, boxes=[box])
        self.model.predict.return_value = [result]
        for manager in (patch.object(serve, "MODEL_PATH", root / "best.pt"),
                        patch.object(serve, "REVISION", "test-commit"),
                        patch.object(serve, "YOLO", return_value=self.model)):
            manager.start()
            self.addCleanup(manager.stop)
        self.client = TestClient(serve.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_valid_image_returns_boxes_labels_and_commit(self):
        image = BytesIO()
        Image.new("L", (16, 16)).save(image, format="PNG")
        response = self.client.post("/predict", files={"file": ("image.png", image.getvalue(), "image/png")})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["revision"], "test-commit")
        self.assertEqual(result["detections"][0]["label"], "car")
        self.assertEqual(result["detections"][0]["bbox_xyxy"], [1, 2, 3, 4])
        self.assertEqual(self.model.predict.call_args.args[0].mode, "RGB")

    def test_invalid_image_is_400_even_with_ultralytics_codec_fallback(self):
        response = self.client.post("/predict", files={"file": ("bad.jpg", b"invalid", "image/jpeg")})
        self.assertEqual(response.status_code, 400)
        self.model.predict.assert_not_called()

    def test_missing_optional_codec_is_a_client_error(self):
        with patch.object(serve.Image, "open", side_effect=ImportError("optional image codec")):
            response = self.client.post("/predict", files={"file": ("bad.heic", b"invalid")})
        self.assertEqual(response.status_code, 400)
        self.model.predict.assert_not_called()

    def test_invalid_confidence_is_rejected_before_prediction(self):
        response = self.client.post("/predict?confidence=2", files={"file": ("bad.jpg", b"invalid")})
        self.assertEqual(response.status_code, 422)
        self.model.predict.assert_not_called()

    def test_oversize_upload_is_rejected_before_decoding(self):
        response = self.client.post("/predict", files={"file": ("big.jpg", b"x" * (serve.MAX_IMAGE_BYTES + 1))})
        self.assertEqual(response.status_code, 413)
        self.model.predict.assert_not_called()

    def test_health_reports_the_deployed_commit_and_training_metadata(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], "test-commit")
        self.assertEqual(response.json()["training"], {"revision": "test-commit"})


if __name__ == "__main__":
    unittest.main()
