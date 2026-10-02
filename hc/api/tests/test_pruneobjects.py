from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch
from uuid import uuid4

from django.core.management import call_command
from django.test.utils import override_settings
from minio.deleteobjects import DeleteObject

from hc.api.models import Check
from hc.test import BaseTestCase


def obj(name: str) -> SimpleNamespace:
    return SimpleNamespace(object_name=name)


@override_settings(S3_BUCKET="test-bucket")
@patch("hc.api.management.commands.pruneobjects.client")
class PruneObjectsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.gone = str(uuid4())

    def run_command(self) -> tuple[str, str]:
        """Run pruneobjects, return what it printed and the command's output."""
        printed, out = StringIO(), StringIO()
        with redirect_stdout(printed):
            call_command("pruneobjects", stdout=out)
        return printed.getvalue(), out.getvalue()

    def test_it_removes_objects_of_deleted_checks(self, client: Mock) -> None:
        prefixes = [obj(f"{self.check.code}/"), obj(f"{self.gone}/"), obj("not-a-check/")]
        bodies = [obj(f"{self.gone}/zj-0"), obj(f"{self.gone}/zi-1")]
        c = client.return_value
        c.list_objects.side_effect = lambda bucket, prefix=None: bodies if prefix else prefixes
        c.remove_objects.return_value = []

        printed, out = self.run_command()

        # Only the prefix of the deleted check should be listed and removed,
        # the existing check's and the non-UUID prefixes left alone
        self.assertEqual(c.list_objects.mock_calls, [call("test-bucket"), call("test-bucket", f"{self.gone}/")])
        c.remove_objects.assert_called_once_with(
            "test-bucket",
            [DeleteObject(f"{self.gone}/zj-0"), DeleteObject(f"{self.gone}/zi-1")],
        )
        self.assertEqual(printed, f"Staged for deletion: 1\nDeleting {self.gone}/\n")
        self.assertEqual(out, "Done!\n")

    def test_it_prints_removal_errors(self, client: Mock) -> None:
        c = client.return_value
        c.list_objects.side_effect = lambda bucket, prefix=None: [obj(f"{self.gone}/zj-0")] if prefix else [obj(f"{self.gone}/")]
        c.remove_objects.return_value = iter(["AccessDenied"])

        printed, out = self.run_command()

        self.assertEqual(
            printed,
            f"Staged for deletion: 1\nDeleting {self.gone}/\nremove_objects error:  AccessDenied\n",
        )
        self.assertEqual(out, "Done!\n")

    def test_it_skips_empty_prefixes(self, client: Mock) -> None:
        c = client.return_value
        c.list_objects.side_effect = lambda bucket, prefix=None: [] if prefix else [obj(f"{self.gone}/")]

        printed, out = self.run_command()

        c.remove_objects.assert_not_called()
        self.assertEqual(printed, f"Staged for deletion: 1\nDeleting {self.gone}/\n")
        self.assertEqual(out, "Done!\n")

    @override_settings(S3_BUCKET=None)
    def test_it_requires_object_storage(self, client: Mock) -> None:
        printed, out = self.run_command()

        client.assert_not_called()
        self.assertEqual(out, "Object storage is not configured\n")
        self.assertEqual(printed, "")
