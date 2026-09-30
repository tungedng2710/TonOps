import json
import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from apiserver.apierrors import APIError
from apiserver.bll.project import assistant
from apiserver.database.model.auth import Role
from apiserver.services import project_ai


class ProjectAiTests(unittest.TestCase):
    def setUp(self):
        self.identity = SimpleNamespace(user="viewer", role=Role.user)
        self.project = SimpleNamespace(id="project", name="Vision", description="", user="owner", visibility="private")
        self.project_query = MagicMock()
        self.project_query.first.return_value = self.project

    def test_private_project_is_rejected_before_snapshot_or_llm(self):
        with patch("apiserver.bll.project.access.iam_enabled", return_value=True), patch.object(
            assistant.Project, "objects", return_value=self.project_query
        ), patch.object(assistant, "build_snapshot") as snapshot, patch.object(assistant, "complete") as llm:
            with self.assertRaises(APIError):
                assistant.ask_project("project", "company", self.identity, "Show metrics")
            snapshot.assert_not_called()
            llm.assert_not_called()

    def test_project_lookup_is_scoped_to_company(self):
        self.project_query.first.return_value = None
        with patch.object(assistant.Project, "objects", return_value=self.project_query) as lookup:
            with self.assertRaises(APIError):
                assistant.get_project("foreign-project", "company", self.identity)
            lookup.assert_called_once_with(id="foreign-project", company="company")

    def test_report_save_rechecks_owner_for_user_and_admin(self):
        self.project.visibility = "public"
        for role in (Role.user, Role.admin):
            call = SimpleNamespace(identity=SimpleNamespace(user="viewer", role=role),
                                   data={"project": "project", "title": "Report", "content": "Draft"})
            with self.subTest(role=role), patch("apiserver.bll.project.access.iam_enabled", return_value=True), patch.object(
                project_ai, "get_project", return_value=self.project
            ), patch.object(project_ai, "_ensure_reports_project") as create:
                with self.assertRaises(APIError):
                    project_ai.save_report(call, "company", None)
                create.assert_not_called()

    def test_owner_can_save_markdown_into_existing_report_format(self):
        call = SimpleNamespace(identity=SimpleNamespace(user="owner", role=Role.user),
                               data={"project": "project", "title": "  Vision report  ", "content": "# Vision\nMetrics"})
        task = MagicMock(id="report")
        with patch("apiserver.bll.project.access.iam_enabled", return_value=True), patch.object(
            project_ai, "get_project", return_value=self.project
        ), patch.object(project_ai, "require_project_path_write"), patch.object(
            project_ai, "_ensure_reports_project", return_value="report-project"
        ), patch.object(project_ai.TaskBLL, "create", return_value=task) as create:
            result = project_ai.save_report(call, "company", None)
            fields = create.call_args.args[2]
            self.assertEqual(fields["report"], call.data["content"])
            self.assertEqual(fields["name"], "Vision report")
            self.assertEqual(fields["type"], "report")
            self.assertEqual(result, {"id": "report", "project_id": "report-project"})
            task.save.assert_called_once()

    def test_summary_keeps_metric_names_and_omits_sensitive_parameters(self):
        task = SimpleNamespace(project="project", to_proper_dict=lambda: {
            "id": "task", "name": "Training", "started": datetime(2026, 9, 30),
            "last_metrics": {"hash": {"variant-hash": {"metric": "Validation", "variant": "mAP", "value": .75, "min_value": float("nan")}}},
            "hyperparams": {"Args": {
                "batch": {"section": "Args", "name": "batch", "value": "16"},
                "key": {"section": "Args", "name": "API_TOKEN", "value": "never-send-this"}}}})
        summary = assistant.summarize_task(task, {"project": "Vision"})
        self.assertEqual(summary["metrics"][0]["metric"], "Validation")
        self.assertEqual(summary["metrics"][0]["value"], .75)
        self.assertIsNone(summary["metrics"][0]["min_value"])
        self.assertEqual(summary["parameters"], [{"name": "Args/batch", "value": "16"}])
        self.assertNotIn("never-send-this", json.dumps(summary))

    def test_large_snapshot_stays_bounded_and_reports_omissions(self):
        scope = MagicMock()
        scope.only.return_value = [self.project]
        tasks = MagicMock()
        tasks.only.return_value.order_by.return_value.__getitem__.return_value = [object()] * 50
        summary = {"id": "task", "name": "X" * 15000, "project_id": "project"}
        with patch.object(assistant.Project, "objects", return_value=scope), patch.object(
            assistant.Task, "objects", return_value=tasks
        ), patch.object(assistant.Task, "aggregate", return_value=[{"_id": "completed", "count": 200}]), patch.object(
            assistant, "summarize_task", return_value=summary
        ), patch("apiserver.bll.project.access.iam_enabled", return_value=True):
            snapshot = assistant.build_snapshot(self.project, "company", self.identity)
        self.assertLessEqual(len(json.dumps(snapshot, ensure_ascii=False)), assistant.MAX_CONTEXT_CHARS)
        self.assertEqual(snapshot["total_tasks"], 200)
        self.assertEqual(snapshot["omitted_tasks"], 200 - len(snapshot["tasks"]))

    def test_unconfigured_ai_does_not_call_provider(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(assistant.requests, "post") as post:
            with self.assertRaises(APIError):
                assistant.complete({}, "Show metrics")
            post.assert_not_called()

    def test_provider_uses_config_and_returns_only_final_answer(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"choices": [{"finish_reason": "stop", "message": {
            "content": "Metric is 0.75", "reasoning": "private provider reasoning"}}]}
        with patch.dict(os.environ, {"LLM_BASE_URL": "http://llm/v1/", "LLM_API_KEY": "private-key", "LLM_MODEL": "glm53-flash"}), patch.object(
            assistant.requests, "post", return_value=response
        ) as post:
            answer = assistant.complete({"tasks": []}, "Show metrics")
            self.assertEqual(answer, "Metric is 0.75")
            self.assertEqual(post.call_args.args[0], "http://llm/v1/chat/completions")
            self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer private-key")
            self.assertNotIn("private-key", json.dumps(post.call_args.kwargs["json"]))

    def test_failures_do_not_expose_upstream_credentials_or_reasoning(self):
        for failure in (requests.Timeout("private-key"), requests.ConnectionError("private-key")):
            with patch.dict(os.environ, {"LLM_BASE_URL": "http://llm/v1", "LLM_API_KEY": "private-key"}), patch.object(
                assistant.requests, "post", side_effect=failure
            ), self.assertRaises(APIError) as result:
                assistant.complete({}, "Show metrics")

            self.assertNotIn("private-key", str(result.exception))
        for choice in ({"finish_reason": "length", "message": {"content": "partial"}},
                       {"finish_reason": "stop", "message": {"content": None, "reasoning": "private"}}):
            response = MagicMock(status_code=200)
            response.json.return_value = {"choices": [choice]}
            with patch.dict(os.environ, {"LLM_BASE_URL": "http://llm/v1", "LLM_API_KEY": "private-key"}), patch.object(
                assistant.requests, "post", return_value=response
            ), self.assertRaises(APIError):
                assistant.complete({}, "Show metrics")

    def test_report_retains_metrics_that_only_exist_in_summary(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"choices": [{"finish_reason": "stop", "message": {"content": "Report"}}]}
        snapshot = {"tasks": [{"metrics": [{"metric": "Summary", "variant": "Summary/accuracy", "value": .75}]}]}
        with patch.dict(os.environ, {"LLM_BASE_URL": "http://llm/v1", "LLM_API_KEY": "private-key"}), patch.object(
            assistant.requests, "post", return_value=response
        ) as post:
            assistant.complete(snapshot, "Generate a report", report=True)
        context = post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertIn("Summary/accuracy", context)
        self.assertIn("0.75", context)


if __name__ == "__main__":
    unittest.main()
