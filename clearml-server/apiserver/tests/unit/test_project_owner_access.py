import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apiserver.apierrors import APIError
from apiserver.bll.project.access import authorize_entity_call, can_write
from apiserver.database.model.auth import Role
from apiserver.services.projects import authorize_file


class ProjectOwnerAccessTest(unittest.TestCase):
    def test_only_owner_can_write_project_with_local_iam(self):
        project = SimpleNamespace(id="project", user="owner")
        with patch("apiserver.bll.project.access.iam_enabled", return_value=True):
            self.assertTrue(can_write(project, SimpleNamespace(user="owner", role=Role.user)))
            self.assertFalse(can_write(project, SimpleNamespace(user="other", role=Role.user)))
            self.assertFalse(can_write(project, SimpleNamespace(user="other", role=Role.admin)))
            self.assertTrue(can_write(project, SimpleNamespace(user="service", role=Role.system)))

    def test_project_delete_rejects_non_owner_before_content_checks(self):
        project = SimpleNamespace(id="project", user="owner")
        with patch("apiserver.bll.project.access.iam_enabled", return_value=True), patch(
            "apiserver.bll.project.access.Project.objects", return_value=[project]
        ):
            for role in (Role.user, Role.admin):
                call = SimpleNamespace(
                    identity=SimpleNamespace(user="other", role=role),
                    data={"project": "project"},
                )
                with self.subTest(role=role), self.assertRaises(APIError):
                    authorize_entity_call(call, "projects.delete", "company")

    def test_administrator_cannot_write_another_owners_artifact(self):
        project = SimpleNamespace(id="project", user="owner", visibility="public")
        task = SimpleNamespace(project="project", user="owner")
        task_query = MagicMock()
        task_query.only.return_value = [task]
        project_query = MagicMock()
        project_query.first.return_value = project
        model_query = MagicMock()
        model_query.only.return_value = []
        call = SimpleNamespace(
            identity=SimpleNamespace(user="other", role=Role.admin),
            data={
                "path": "task.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/artifact.bin",
                "host": "fileserver",
                "mode": "write",
            },
        )
        with patch("apiserver.services.projects.iam_enabled", return_value=True), patch(
            "apiserver.bll.project.access.iam_enabled", return_value=True
        ), patch("apiserver.services.projects.Task.objects", return_value=task_query), patch(
            "apiserver.services.projects.Project.objects", return_value=project_query
        ), patch("apiserver.services.projects.Model.objects", return_value=model_query):
            self.assertEqual({"allowed": False}, authorize_file(call, "company", None))
