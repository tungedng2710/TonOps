"""Check the model quality gate and restoration after a deployment fails."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CICD = ROOT / "examples/vehicle_detection_yolo12/cicd"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, CICD / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = load("ci_example", "ci.py")
with patch.dict(sys.modules, {"httpx": types.ModuleType("httpx")}):
    deployment = load("deployment_example", "deploy.py")


class QualityGateTests(unittest.TestCase):
    def test_good_metrics_pass_and_boundary_is_inclusive(self):
        self.assertEqual(ci.validate_metrics({"metrics/mAP50(B)": 0.5}, 0.5), 0.5)

    def test_low_invalid_or_missing_metrics_cannot_be_deployed(self):
        for metrics in ({"metrics/mAP50(B)": 0.001}, {"metrics/mAP50(B)": float("nan")},
                        {"metrics/mAP50(B)": float("inf")}, {"metrics/mAP50(B)": 1.1},
                        {"loss": 0.2}, {}):
            with self.subTest(metrics=metrics), self.assertRaises((ValueError, KeyError)):
                ci.validate_metrics(metrics, 0.01)

    def test_invalid_threshold_is_rejected(self):
        for threshold in (-0.1, 1.1, float("nan")):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                ci.validate_metrics({"metrics/mAP50(B)": 0.5}, threshold)


class DeploymentTests(unittest.TestCase):
    def test_smoke_failure_restores_previous_image_and_fails_pipeline(self):
        calls = []
        with patch.object(deployment.subprocess, "check_output", side_effect=["container-id\n", "demo:old\n"]), \
                patch.object(deployment.subprocess, "run", side_effect=lambda command, **kw: calls.append((command, dict(kw.get("env", {}))))), \
                patch.object(deployment, "smoke", side_effect=RuntimeError("bad prediction")):
            with self.assertRaisesRegex(RuntimeError, "bad prediction"):
                deployment.deploy("demo:new", "new", 7865)
        up_calls = [env for command, env in calls if "up" in command]
        self.assertEqual([env["YOLO12_IMAGE"] for env in up_calls], ["demo:new", "demo:old"])

    def test_failed_first_deployment_removes_only_the_demo_stack(self):
        calls = []
        with patch.object(deployment.subprocess, "check_output", return_value=""), \
                patch.object(deployment.subprocess, "run", side_effect=lambda command, **kw: calls.append(command)), \
                patch.object(deployment, "smoke", side_effect=RuntimeError("unhealthy")):
            with self.assertRaisesRegex(RuntimeError, "unhealthy"):
                deployment.deploy("demo:new", "new", 7865)
        self.assertEqual(calls[-1], deployment.COMPOSE + ["down"])

    def test_success_preserves_the_new_deployment(self):
        with patch.object(deployment.subprocess, "check_output", return_value=""), \
                patch.object(deployment.subprocess, "run") as command, patch.object(deployment, "smoke") as smoke:
            deployment.deploy("demo:new", "new", 7865)
        self.assertEqual(command.call_count, 1)
        smoke.assert_called_once_with("http://127.0.0.1:7865", "new", CICD / "build/sample.jpg")


if __name__ == "__main__":
    unittest.main()
