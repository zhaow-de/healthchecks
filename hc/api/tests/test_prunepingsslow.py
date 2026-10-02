from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, call, patch

from django.conf import settings
from django.core.management import call_command
from django.test.utils import override_settings

from hc.api.management.commands.prunepingsslow import Command
from hc.api.models import Check, Ping
from hc.test import BaseTestCase


class PrunePingsSlowTestCase(BaseTestCase):
    @patch("hc.api.models.remove_objects", autospec=True)
    def test_it_works(self, remove_objects: Mock) -> None:
        check = Check.objects.create(project=self.project, n_pings=101)
        Ping.objects.create(owner=check, n=1)
        Command(stdout=Mock()).handle()

        # The ping should have been deleted
        self.assertFalse(Ping.objects.exists())

    def create_checks(self, n: int) -> list[Check]:
        checks = [Check.objects.create(project=self.project, n_pings=101) for _ in range(n)]
        # The command walks the checks in the order of their codes
        return sorted(checks, key=lambda check: str(check.code))

    @override_settings(S3_TIMEOUT=15)
    def test_it_skips_checks_deleted_while_running(self) -> None:
        first, second = self.create_checks(2)

        def prune(check: Check, wait: bool) -> None:
            # Another process deletes the second check meanwhile
            Check.objects.filter(id=second.id).delete()

        out = StringIO()
        with patch.object(Check, "prune", autospec=True, side_effect=prune) as mock_prune:
            call_command("prunepingsslow", stdout=out)

        self.assertEqual(mock_prune.mock_calls, [call(first, wait=True)])
        self.assertEqual(out.getvalue(), f"Pruning: {first.code}\nDone!\n")
        # Deletes in object storage are slow, the command raises the timeout
        self.assertEqual(settings.S3_TIMEOUT, 60)

    def test_it_logs_prune_errors_and_continues(self) -> None:
        first, second = self.create_checks(2)

        out = StringIO()
        logger_name = "hc.api.management.commands.prunepingsslow"
        with (
            patch.object(Check, "prune", autospec=True, side_effect=[ValueError("boom"), None]) as mock_prune,
            self.assertLogs(logger_name, "ERROR") as logs,
            override_settings(S3_TIMEOUT=15),
        ):
            call_command("prunepingsslow", stdout=out)

        # The failure on the first check should not stop the second
        self.assertEqual(mock_prune.mock_calls, [call(first, wait=True), call(second, wait=True)])
        self.assertEqual(out.getvalue(), f"Pruning: {first.code}\nPruning: {second.code}\nDone!\n")

        [record] = logs.records
        self.assertEqual(record.getMessage(), "Exception in Check.prune()")
        assert record.exc_info
        self.assertIsInstance(record.exc_info[1], ValueError)
