"""Offline checks for queue reuse, task outcomes, and remote GPU execution."""

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


job = load_module("gpu_job", "examples/vehicle_detection_yolo12/project.py")
worker = load_module("gpu_worker", "scripts/clearml-gpu-worker.py")
training = load_module("gpu_training", "examples/vehicle_detection_yolo12/train.py")


class QueueAndStatusTests(unittest.TestCase):
    def test_existing_queue_is_reused_and_missing_queue_is_created(self):
        with patch.object(job, "api_call", return_value={"queues": [{"name": "gpu", "id": "q1"}]}) as api:
            self.assertEqual(job.ensure_queue(object(), "gpu"), "q1")
            self.assertEqual(api.call_count, 1)
        with patch.object(job, "api_call", side_effect=[{"queues": []}, {"id": "q2"}]) as api:
            self.assertEqual(job.ensure_queue(object(), "gpu"), "q2")
            self.assertEqual(api.call_args.args[1:], ("queues", "create", {"name": "gpu"}))

    def test_wait_reports_completed_failed_and_timeout_distinctly(self):
        for status, expected in (("completed", 0), ("failed", 1), ("stopped", 1), ("closed", 1)):
            task = MagicMock(id="task1", status=status, artifacts={}, models={})
            task.data.status_message = "message"
            task.data.last_worker = "worker1"
            task.get_last_scalar_metrics.return_value = {}
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(job.check_task(task, True, 20, 1), expected)
        task.status = "queued"
        with patch.object(job.time, "monotonic", side_effect=[100, 121]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(job.check_task(task, True, 20, 1), 2)
        task.mark_stopped.assert_not_called()
        task.mark_failed.assert_not_called()


class WorkerTests(unittest.TestCase):
    def test_preflight_failure_does_not_launch_daemon(self):
        with patch.object(sys, "argv", ["worker", "start"]), \
                patch.object(worker, "agent_command", return_value=["clearml-agent", "daemon"]), \
                patch.object(worker, "doctor", return_value=1), patch.object(worker, "run") as run:
            self.assertEqual(worker.main(), 1)
            run.assert_not_called()

    def test_config_preserves_private_file_and_uses_absolute_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "private.conf"
            base.write_text('api { credentials { access_key: "private" } }\n')
            target = Path(directory) / "worker.conf"
            with patch.object(worker, "CONFIG", target), contextlib.redirect_stdout(io.StringIO()):
                worker.configure(base)
            self.assertIn(str(base), target.read_text())
            self.assertNotIn('access_key: "private"', target.read_text())
            self.assertEqual(base.read_text(), 'api { credentials { access_key: "private" } }\n')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_multi_gpu_selection_survives_docker_csv_parsing(self):
        calls = []
        with patch.object(worker, "run", side_effect=lambda command, **kwargs: calls.append(command)):
            self.assertEqual(worker.doctor(argparse.Namespace(gpus="0,1", image="image")), 0)
        command = calls[-1]
        self.assertEqual(command[command.index("--gpus") + 1], '"device=0,1"')


class RemoteTrainingTests(unittest.TestCase):
    def test_dataset_cache_root_replaces_submitters_path_without_changing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = {"path": "/old/host/dataset", "train": "train/images", "val": "valid/images"}
            source = root / "data.yaml"
            source.write_text(json.dumps(original))
            dataset = MagicMock()
            dataset.get.return_value.get_local_copy.return_value = directory
            clearml = types.ModuleType("clearml")
            clearml.Dataset = dataset
            yaml = types.ModuleType("yaml")
            yaml.safe_load = json.loads
            yaml.safe_dump = lambda data, **kwargs: json.dumps(data)
            with patch.dict(sys.modules, {"clearml": clearml, "yaml": yaml}), \
                    patch.object(training.Path, "cwd", return_value=root):
                target = training.dataset_yaml("dataset-id")
            rewritten = json.loads(Path(target).read_text())
            self.assertEqual(rewritten["path"], directory)
            self.assertEqual(rewritten["train"], "train/images")
            self.assertEqual(json.loads(source.read_text()), original)

    def test_dataset_absolute_split_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data.yaml").write_text('{"train": "/old/host/images"}')
            dataset = MagicMock()
            dataset.get.return_value.get_local_copy.return_value = directory
            clearml = types.ModuleType("clearml")
            clearml.Dataset = dataset
            yaml = types.ModuleType("yaml")
            yaml.safe_load = json.loads
            with patch.dict(sys.modules, {"clearml": clearml, "yaml": yaml}):
                with self.assertRaisesRegex(ValueError, "must be relative"):
                    training.dataset_yaml("dataset-id")

    def setup_modules(self, task, gpu_available, yolo):
        clearml = types.ModuleType("clearml")
        clearml.Task = MagicMock()
        clearml.Task.init.return_value = task
        clearml.OutputModel = MagicMock()
        torch = types.ModuleType("torch")
        torch.cuda = MagicMock()
        torch.cuda.is_available.return_value = gpu_available
        torch.cuda.get_device_name.return_value = "Test GPU"
        torch.cuda.device_count.return_value = 1
        torch.__version__ = "2.7.1"
        torch.version = types.SimpleNamespace(cuda="12.6")
        torch.backends = types.SimpleNamespace(cudnn=types.SimpleNamespace(version=lambda: 90000))
        ultralytics = types.ModuleType("ultralytics")
        ultralytics.YOLO = yolo
        return {"clearml": clearml, "torch": torch, "ultralytics": ultralytics}

    def test_cpu_only_runtime_fails_task_before_training(self):
        task = MagicMock()
        task.connect.side_effect = lambda params, **kwargs: params
        yolo = MagicMock()
        with patch.dict(sys.modules, self.setup_modules(task, False, yolo)), \
                patch.object(sys, "argv", ["train"]):
            with self.assertRaisesRegex(RuntimeError, "requires CUDA"):
                training.main()
        task.mark_failed.assert_called_once()
        yolo.assert_not_called()

    def test_server_parameters_reach_training_and_checkpoint_upload(self):
        task = MagicMock(id="remote-task")
        task.connect.side_effect = lambda params, **kwargs: dict(params, epochs=3, batch=4)
        yolo = MagicMock()
        modules = self.setup_modules(task, True, yolo)
        with tempfile.TemporaryDirectory() as directory:
            best = Path(directory) / "best.pt"
            best.write_bytes(b"checkpoint")
            yolo.return_value.trainer.best = str(best)
            yolo.return_value.trainer.metrics = {"metrics/mAP50(B)": 0.5}
            with patch.dict(sys.modules, modules), patch.object(sys, "argv", ["train"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                training.main()
        self.assertEqual(yolo.return_value.train.call_args.kwargs["epochs"], 3)
        self.assertEqual(yolo.return_value.train.call_args.kwargs["batch"], 4)
        self.assertEqual(yolo.return_value.train.call_args.kwargs["device"], "0")
        modules["clearml"].OutputModel.return_value.update_weights.assert_called_once_with(str(best))
        task.mark_failed.assert_not_called()
        task.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
