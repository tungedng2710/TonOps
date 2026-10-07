"""Check project dataset portability, label validation, and registered-model use."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from test_clearml_gpu_workflow import job, load_module

dataset_code = load_module("detection_dataset", "examples/vehicle_detection_yolo12/dataset.py")


def yaml_module():
    # JSON is a YAML subset; use it for fixtures so these tests need no packages.
    module = types.ModuleType("yaml")
    module.safe_load = json.loads
    module.safe_dump = lambda value, **kwargs: json.dumps(value)
    return module


def make_dataset(root):
    config = {"path": "/another/host/vehicles", "train": "train/images",
              "val": "valid/images", "names": ["car"]}
    source = root / "source.yaml"
    source.write_text(json.dumps(config))
    for split in ("train", "valid"):
        images = root / split / "images"
        labels = root / split / "labels"
        images.mkdir(parents=True)
        labels.mkdir(parents=True)
        (images / "car.jpg").write_bytes(b"image fixture")
        (labels / "car.txt").write_text("0 0.5 0.5 0.2 0.3\n")
    return source, config


class DatasetTests(unittest.TestCase):
    def test_root_override_produces_portable_config_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"yaml": yaml_module()}):
            root = Path(directory)
            source, original = make_dataset(root)
            report, portable = dataset_code.prepare_dataset(source, root)
            self.assertEqual(portable, {"path": ".", "names": ["car"],
                                        "train": "train/images", "val": "valid/images"})
            self.assertEqual(report["splits"]["train"]["objects_by_class"], {"car": 1})
            self.assertEqual(json.loads(source.read_text()), original)

    def test_empty_images_missing_labels_and_nonfinite_class_fail_validation(self):
        for failure in ("empty", "missing", "nan"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory, \
                    patch.dict(sys.modules, {"yaml": yaml_module()}):
                root = Path(directory)
                source, _ = make_dataset(root)
                label = root / "train/labels/car.txt"
                if failure == "empty":
                    (root / "train/images/car.jpg").unlink()
                    label.unlink()
                elif failure == "missing":
                    label.unlink()
                else:
                    label.write_text("nan 0.5 0.5 0.2 0.3\n")
                with self.assertRaisesRegex(ValueError, "Dataset validation failed"):
                    dataset_code.prepare_dataset(source, root)

    def test_registration_uploads_normalized_yaml_then_finalizes_with_metadata(self):
        clearml = types.ModuleType("clearml")
        clearml.Dataset = MagicMock()
        registered = clearml.Dataset.create.return_value
        registered.id = "registered-dataset"
        uploaded_configs = []
        registered.add_files.side_effect = lambda **kw: uploaded_configs.append(
            json.loads(Path(kw["path"]).read_text())) if Path(kw["path"]).is_file() else None
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(sys.modules, {"yaml": yaml_module(), "clearml": clearml}):
            root = Path(directory)
            source, original = make_dataset(root)
            dataset_id, _ = dataset_code.register_dataset(source, root, "Detection", "cars", "1.0.0", "s3://host/bucket")
            self.assertEqual(dataset_id, "registered-dataset")
            self.assertEqual(uploaded_configs[0]["path"], ".")
            self.assertEqual(json.loads(source.read_text()), original)
        registered.set_metadata.assert_called_once()
        registered.upload.assert_called_once_with(output_url="s3://host/bucket", max_workers=2)
        self.assertLess([call[0] for call in registered.mock_calls].index("upload"),
                        [call[0] for call in registered.mock_calls].index("finalize"))


class ProjectCommandsTests(unittest.TestCase):
    def test_submit_records_selected_dataset_and_model_and_saves_task_id(self):
        clearml = types.ModuleType("clearml")
        clearml.Task = MagicMock()
        task = clearml.Task.create.return_value
        task.id = "training-task"
        session_module = types.ModuleType("clearml.backend_api.session")
        session_module.Session = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            task_file = Path(directory) / "task-id"
            argv = ["project", "submit", "--project", "Detection", "--dataset-id", "data-v1",
                    "--model", "yolo12s.pt", "--task-id-file", str(task_file)]
            with patch.dict(sys.modules, {"clearml": clearml, "clearml.backend_api.session": session_module}), \
                    patch.object(sys, "argv", argv), patch.object(job, "ensure_queue", return_value="gpu-queue"), \
                    patch.object(job, "check_task", return_value=0), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(job.main(), 0)
            self.assertEqual(task_file.read_text().strip(), "training-task")
        params = task.set_parameters.call_args.args[0]
        self.assertEqual(params["Training/dataset_id"], "data-v1")
        self.assertEqual(params["Training/model"], "yolo12s.pt")
        self.assertTrue(clearml.Task.create.call_args.kwargs["force_single_script_file"])
        self.assertTrue(Path(clearml.Task.create.call_args.kwargs["script"]).is_file())
        clearml.Task.enqueue.assert_called_once_with(task, queue_id="gpu-queue")

    def test_predict_downloads_registered_model_and_writes_detection_result(self):
        clearml = types.ModuleType("clearml")
        clearml.Model = MagicMock()
        clearml.Model.return_value.get_local_copy.return_value = "/cache/model.pt"
        ultralytics = types.ModuleType("ultralytics")
        ultralytics.YOLO = MagicMock()
        result = MagicMock()
        result.names = {0: "car"}
        box = MagicMock()
        box.cls.item.return_value = 0
        box.conf.item.return_value = 0.9
        box.xyxy.__getitem__.return_value.tolist.return_value = [1, 2, 30, 40]
        result.boxes = [box]
        ultralytics.YOLO.return_value.predict.return_value = [result]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.jpg"
            source.write_bytes(b"image fixture")
            argv = ["project", "predict", "--model-id", "model-v1", "--source", str(source),
                    "--output-dir", str(root / "predictions")]
            with patch.dict(sys.modules, {"clearml": clearml, "ultralytics": ultralytics}), \
                    patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(job.main(), 0)
            payload = json.loads((root / "predictions/input.json").read_text())
        clearml.Model.assert_called_once_with(model_id="model-v1")
        self.assertEqual(payload["detections"][0]["label"], "car")
        self.assertEqual(payload["detections"][0]["bbox_xyxy"], [1, 2, 30, 40])


if __name__ == "__main__":
    unittest.main()
