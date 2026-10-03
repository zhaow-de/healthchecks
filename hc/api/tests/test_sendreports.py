from __future__ import annotations

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from datetime import timedelta as td
from io import StringIO
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, call, patch

import time_machine
from django.core import mail
from django.core.management import call_command
from django.db.models import QuerySet
from django.utils.timezone import now

from hc.api.management.commands.sendreports import Command
from hc.api.models import Check, Flip
from hc.test import BaseTestCase

CURRENT_TIME = datetime(2020, 1, 13, 2, tzinfo=timezone.utc)
MOCK_SLEEP = Mock()


@contextmanager
def updated_concurrently(**fields: Any) -> Iterator[None]:
    """Make QuerySet.first() return its row, then change that row in the database.

    This is what another sendreports process does when it handles the same
    profile between our SELECT and our UPDATE.
    """
    first = QuerySet.first

    def first_then_update(qs: QuerySet[Any]) -> Any:
        obj = first(qs)
        if obj is not None:
            qs.model._default_manager.filter(pk=obj.pk).update(**fields)
        return obj

    with patch.object(QuerySet, "first", first_then_update):
        yield


@time_machine.travel(CURRENT_TIME)
@patch("hc.api.management.commands.sendreports.time.sleep", MOCK_SLEEP)
class SendReportsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        # Make alice eligible for a monthly report:
        self.profile.next_report_date = CURRENT_TIME - td(hours=1)
        # and for a nag
        self.profile.nag_period = td(hours=1)
        self.profile.next_nag_date = CURRENT_TIME - td(seconds=10)
        self.profile.save()

        # Disable charlie's monthly report so it doesn't interfere
        self.charlies_profile.reports = "off"
        self.charlies_profile.save()

        # And it needs at least one check that has been pinged.
        self.check = Check(project=self.project, last_ping=now())
        self.check.created = datetime(2019, 10, 1, tzinfo=timezone.utc)
        self.check.name = "Foo"
        self.check.status = "down"
        self.check.save()

        self.flip = Flip(owner=self.check)
        self.flip.created = datetime(2019, 12, 31, 23, tzinfo=timezone.utc)
        self.flip.old_status = "new"
        self.flip.new_status = "down"
        self.flip.save()

    def test_it_sends_monthly_report(self) -> None:
        cmd = Command(stdout=Mock())
        found = cmd.handle_one_report()
        self.assertTrue(found)

        self.profile.refresh_from_db()
        assert self.profile.next_report_date
        self.assertEqual(self.profile.next_report_date.date(), date(2020, 2, 1))
        self.assertEqual(self.profile.next_report_date.day, 1)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.subject, "Monthly Report")

    def test_it_obeys_next_report_date(self) -> None:
        self.profile.next_report_date = CURRENT_TIME + td(days=1)
        self.profile.save()

        found = Command().handle_one_report()
        self.assertFalse(found)

    def test_it_fills_blank_next_monthly_report_date(self) -> None:
        self.profile.next_report_date = None
        self.profile.save()

        found = Command().handle_one_report()
        self.assertTrue(found)

        self.profile.refresh_from_db()
        assert self.profile.next_report_date
        self.assertEqual(self.profile.next_report_date.date(), date(2020, 2, 1))
        self.assertEqual(len(mail.outbox), 0)

    def test_it_fills_blank_next_weekly_report_date(self) -> None:
        self.profile.reports = "weekly"
        self.profile.next_report_date = None
        self.profile.save()

        found = Command().handle_one_report()
        self.assertTrue(found)

        self.profile.refresh_from_db()
        assert self.profile.next_report_date
        self.assertEqual(self.profile.next_report_date.date(), date(2020, 1, 20))
        self.assertEqual(len(mail.outbox), 0)

    def test_it_obeys_reports_off(self) -> None:
        self.profile.reports = "off"
        self.profile.save()

        found = Command().handle_one_report()
        self.assertFalse(found)

    def test_it_requires_pinged_checks(self) -> None:
        self.check.delete()

        found = Command().handle_one_report()
        self.assertTrue(found)

        # No email should have been sent:
        self.assertEqual(len(mail.outbox), 0)

    def test_it_sends_nag(self) -> None:
        cmd = Command(stdout=Mock())
        found = cmd.handle_one_nag()
        self.assertTrue(found)

        self.profile.refresh_from_db()
        assert self.profile.next_nag_date
        self.assertTrue(self.profile.next_nag_date > CURRENT_TIME)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.subject, "Reminder: 1 check still down")

    def test_it_obeys_next_nag_date(self) -> None:
        self.profile.next_nag_date = CURRENT_TIME + td(days=1)
        self.profile.save()

        # If next_nag_date is in future, a nag should not get sent.
        found = Command().handle_one_nag()
        self.assertFalse(found)

    def test_it_obeys_nag_period(self) -> None:
        self.profile.nag_period = td()
        self.profile.save()

        # If nag_period is 0 ("disabled"), a nag should not get sent.
        found = Command().handle_one_nag()
        self.assertFalse(found)

    def test_nags_require_down_checks(self) -> None:
        self.check.status = "up"
        self.check.save()

        found = Command().handle_one_nag()
        self.assertTrue(found)

        # No email should have been sent:
        self.assertEqual(len(mail.outbox), 0)

        # next_nag_date should now be unset
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.next_nag_date)

    def test_it_skips_report_sent_by_another_process(self) -> None:
        other_date = CURRENT_TIME + td(days=19)
        with updated_concurrently(next_report_date=other_date):
            found = Command(stdout=Mock()).handle_one_report()

        # It should continue right away to look for the next profile
        self.assertTrue(found)
        self.assertEqual(len(mail.outbox), 0)
        # The other process's schedule should stay intact
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.next_report_date, other_date)

    def test_it_skips_nag_sent_by_another_process(self) -> None:
        other_date = CURRENT_TIME + td(minutes=59)
        with updated_concurrently(next_nag_date=other_date):
            found = Command(stdout=Mock()).handle_one_nag()

        # It should continue right away to look for the next profile
        self.assertTrue(found)
        self.assertEqual(len(mail.outbox), 0)
        # The other process's schedule should stay intact
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.next_nag_date, other_date)

    @patch("hc.api.management.commands.sendreports.close_old_connections")
    @patch("hc.api.management.commands.sendreports.connection")
    @patch("hc.api.management.commands.sendreports.signal.signal")
    def test_handle_sends_due_reports_and_nags_once(self, set_handler: Mock, connection: Mock, close_old_connections: Mock) -> None:
        connection.in_atomic_block = False

        cmd = Command()
        out = StringIO()
        call_command(cmd, stdout=out)

        self.assertEqual(
            out.getvalue(),
            "sendreports is now running\nSent monthly report to alice@example.org\nSent nag to alice@example.org\nDone.\n",
        )
        self.assertEqual([m.subject for m in mail.outbox], ["Monthly Report", "Reminder: 1 check still down"])

        # Outside of a transaction it should drop timed-out db connections
        close_old_connections.assert_called_once_with()
        self.assertEqual(
            set_handler.mock_calls,
            [call(signal.SIGTERM, cmd.on_signal), call(signal.SIGINT, cmd.on_signal)],
        )

    @patch("hc.api.management.commands.sendreports.signal.signal")
    def test_handle_loops_until_signalled(self, set_handler: Mock) -> None:
        cmd = Command()
        out = StringIO()

        def sleep(secs: float) -> None:
            # Deliver SIGTERM during the wait between rounds
            if secs == 1:
                cmd.on_signal(signal.SIGTERM, None)

        with patch("hc.api.management.commands.sendreports.time.sleep", side_effect=sleep) as mock_sleep:
            call_command(cmd, "--loop", stdout=out)

        # Two 3-second pauses after sending, then the wait loop should stop
        # at its first 1-second step once the signal arrives
        self.assertEqual(mock_sleep.mock_calls, [call(3), call(3), call(1)])
        self.assertEqual(len(mail.outbox), 2)

        desc = signal.strsignal(signal.SIGTERM)
        self.assertTrue(out.getvalue().endswith(f"{desc}, finishing...\nDone.\n"))

    @patch("hc.api.management.commands.sendreports.signal.signal")
    def test_handle_names_the_postgres_connection(self, set_handler: Mock) -> None:
        databases = {"default": {"OPTIONS": {"application_name": "hc"}}}
        with patch("hc.api.management.commands.sendreports.settings", SimpleNamespace(DATABASES=databases)):
            call_command(Command(), stdout=StringIO())

        self.assertEqual(databases["default"]["OPTIONS"]["application_name"], "sendreports")
