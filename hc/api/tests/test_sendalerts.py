from __future__ import annotations

import signal
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from datetime import timedelta as td
from io import StringIO
from threading import BoundedSemaphore, Event
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, call, patch

import time_machine
from django.core.management import call_command
from django.db.models import QuerySet
from django.utils.timezone import now

from hc.api.management.commands.sendalerts import Command, notify
from hc.api.models import Channel, Check, Flip
from hc.api.transports import TransportError
from hc.test import BaseTestCase

CURRENT_TIME = datetime(2020, 1, 13, 2, tzinfo=timezone.utc)


@contextmanager
def updated_concurrently(**fields: Any) -> Iterator[None]:
    """Make QuerySet.first() return its row, then change that row in the database.

    This is what another sendalerts process does when it claims the same row
    between our SELECT and our UPDATE.
    """
    first = QuerySet.first

    def first_then_update(qs: QuerySet[Any]) -> Any:
        obj = first(qs)
        if obj is not None:
            qs.model._default_manager.filter(pk=obj.pk).update(**fields)
        return obj

    with patch.object(QuerySet, "first", first_then_update):
        yield


class SendAlertsTestCase(BaseTestCase):
    def test_it_handles_grace_period(self) -> None:
        check = Check(project=self.project, status="up")
        # 1 day 30 minutes after ping the check is in grace period:
        check.last_ping = now() - td(days=1, minutes=30)
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        Command().handle_going_down()

        check.refresh_from_db()
        self.assertEqual(check.status, "up")
        self.assertEqual(Flip.objects.count(), 0)

    def test_it_creates_a_flip_when_check_goes_down(self) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = now() - td(days=2)
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        result = Command().handle_going_down()

        # If it finds work, it should return True
        self.assertTrue(result)

        # It should create a flip object
        flip = Flip.objects.get()
        self.assertEqual(flip.owner_id, check.id)
        self.assertEqual(flip.created, check.alert_after)
        self.assertEqual(flip.new_status, "down")
        self.assertEqual(flip.reason, "timeout")

        # It should change stored status to "down", and clear out alert_after
        check.refresh_from_db()
        self.assertEqual(check.status, "down")
        self.assertEqual(check.alert_after, None)

    @patch("hc.api.management.commands.sendalerts.statsd")
    @patch("hc.api.management.commands.sendalerts.notify")
    def test_it_processes_flip(self, mock_notify: Mock, statsd: Mock) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = now()
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "down"
        flip.new_status = "up"
        flip.save()

        mock_notify.return_value = "all is well"
        result = Command(stdout=Mock()).process_one_flip()

        # If it finds work, it should return True
        self.assertTrue(result)

        # It should call `notify`
        mock_notify.assert_called_once()

        # It should set the processed date
        flip.refresh_from_db()
        self.assertTrue(flip.processed)

        # It should increase a statsd counter
        statsd.incr.assert_called_once()

    @patch("hc.api.management.commands.sendalerts.notify")
    def test_it_updates_alert_after(self, mock_notify: Mock) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = now() - td(hours=1)
        check.alert_after = check.last_ping
        check.save()

        result = Command().handle_going_down()

        # If it finds work, it should return True
        self.assertTrue(result)

        # alert_after should have been increased
        expected_aa = check.last_ping + td(days=1, hours=1)
        check.refresh_from_db()
        self.assertEqual(check.alert_after, expected_aa)

        # a flip should have not been created
        self.assertEqual(Flip.objects.count(), 0)

    def test_it_sets_next_nag_date(self) -> None:
        self.profile.nag_period = td(hours=1)
        self.profile.save()

        check = Check(project=self.project, status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        notify(flip)

        # next_nag_gate should now be set for the project's owner
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.next_nag_date)

    def test_it_clears_next_nag_date(self) -> None:
        self.profile.nag_period = td(hours=1)
        self.profile.next_nag_date = now() - td(minutes=30)
        self.profile.save()

        charlies_nag_date = now() - td(minutes=30)
        self.charlies_profile.nag_period = td(hours=1)
        self.charlies_profile.next_nag_date = charlies_nag_date
        self.charlies_profile.save()

        check = Check(project=self.project, status="up")
        check.last_ping = now()
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "down"
        flip.new_status = "up"
        flip.save()

        notify(flip)

        # next_nag_gate should now be cleared out for the project's owner
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.next_nag_date)

        # Charlie has no access to the project, so his next_nag_date is left alone
        self.charlies_profile.refresh_from_db()
        self.assertEqual(self.charlies_profile.next_nag_date, charlies_nag_date)

    def test_it_does_not_touch_already_set_next_nag_dates(self) -> None:
        original_nag_date = now() - td(minutes=30)
        self.profile.nag_period = td(hours=1)
        self.profile.next_nag_date = original_nag_date
        self.profile.save()

        check = Check(project=self.project, status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        notify(flip)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.next_nag_date, original_nag_date)

    @patch("hc.api.management.commands.sendalerts.statsd")
    def test_it_does_not_clobber_check_status(self, statsd: Mock) -> None:
        check = Check(project=self.project, status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        channel = Channel.objects.create(project=self.project, kind="webhook")
        channel.checks.add(check)

        with patch("hc.api.models.Channel.transport") as Webhook:
            Webhook.is_noop.return_value = False
            notify(flip)

            args = Webhook.notify.call_args.args
            # Before sending a notification, we used to set flip.owner.status value
            # to "IF_YOU_SEE_THIS_WE_HAVE_A_BUG". The idea was to use it as 0xDEADBEEF:
            # if it surfaces anywhere in notification contents we know we have a bug.
            # Problem is, webhooks have a $JSON placeholder, which calls
            # Check.get_status(), which reads Check.status. So we *must not*
            # clobber flip.owner.status.
            self.assertEqual(args[0].owner.status, "down")

    @patch("hc.api.management.commands.sendalerts.statsd")
    def test_it_increases_statsd_success_counter(self, statsd: Mock) -> None:
        check = Check(project=self.project, status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        channel = Channel.objects.create(project=self.project, kind="webhook")
        channel.checks.add(check)

        with patch("hc.api.models.Channel.transport") as Webhook:
            Webhook.is_noop.return_value = False
            notify(flip)

        self.assertEqual(statsd.incr.mock_calls, [call("hc.notifications.webhook.success")])

    @patch("hc.api.management.commands.sendalerts.statsd")
    def test_it_increases_statsd_fail_counter(self, statsd: Mock) -> None:
        check = Check(project=self.project, status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        channel = Channel.objects.create(project=self.project, kind="webhook")
        channel.checks.add(check)

        with patch("hc.api.models.Channel.transport") as Webhook:
            Webhook.is_noop.return_value = False
            # Rig Webhook.notify() to raise a TransportError.
            # This should cause sendalerts to increase a statsd "fail" counter.
            Webhook.notify.side_effect = TransportError("Test error message")
            notify(flip)

        self.assertEqual(statsd.incr.mock_calls, [call("hc.notifications.webhook.fail")])

    @patch("hc.api.management.commands.sendalerts.close_old_connections")
    @patch("hc.api.management.commands.sendalerts.connection")
    def test_notify_refreshes_stale_db_connection(self, connection: Mock, close_old_connections: Mock) -> None:
        # Outside of a transaction (as in a sendalerts worker thread)
        # notify() must drop timed-out connections before querying the db
        connection.in_atomic_block = False

        check = Check.objects.create(project=self.project, status="down")
        flip = Flip.objects.create(owner=check, created=now(), old_status="up", new_status="down")

        # There are no channels, so there is nothing to log
        self.assertIsNone(notify(flip))
        close_old_connections.assert_called_once_with()

    def test_it_reraises_and_logs_notify_exceptions(self) -> None:
        cmd = Command(stdout=Mock())
        cmd.seats = BoundedSemaphore(1)
        cmd.seats.acquire()

        future: Future[str | None] = Future()
        future.set_exception(ValueError("boom"))

        with self.assertLogs("hc", "ERROR") as logs:
            with self.assertRaisesRegex(ValueError, "boom"):
                cmd.on_notify_done(future)

        [record] = logs.records
        self.assertEqual(record.getMessage(), "Exception in notify")
        assert record.exc_info
        self.assertIs(record.exc_info[1], future.exception())
        # The worker seat should have been given back
        self.assertTrue(cmd.seats.acquire(blocking=False))

    @patch("hc.api.management.commands.sendalerts.notify")
    def test_it_waits_while_all_workers_are_busy(self, mock_notify: Mock) -> None:
        check = Check.objects.create(project=self.project, status="up")
        flip = Flip.objects.create(owner=check, created=now(), old_status="down", new_status="up")

        cmd = Command(stdout=Mock())
        cmd.seats = Mock()
        cmd.seats.acquire.return_value = False

        self.assertFalse(cmd.process_one_flip())
        cmd.seats.acquire.assert_called_once_with(timeout=1)

        # The flip should be left for later
        flip.refresh_from_db()
        self.assertIsNone(flip.processed)
        mock_notify.assert_not_called()

    def test_it_returns_false_when_there_are_no_flips(self) -> None:
        cmd = Command(stdout=Mock())
        cmd.seats = BoundedSemaphore(1)

        self.assertFalse(cmd.process_one_flip())
        # The worker seat should have been given back
        self.assertTrue(cmd.seats.acquire(blocking=False))

    @patch("hc.api.management.commands.sendalerts.statsd")
    @patch("hc.api.management.commands.sendalerts.notify")
    def test_it_skips_flip_claimed_by_another_process(self, mock_notify: Mock, statsd: Mock) -> None:
        check = Check.objects.create(project=self.project, status="up")
        Flip.objects.create(owner=check, created=now(), old_status="down", new_status="up")

        cmd = Command(stdout=Mock())
        cmd.seats = BoundedSemaphore(1)

        claimed_at = now() - td(seconds=5)
        with updated_concurrently(processed=claimed_at):
            result = cmd.process_one_flip()

        # It should continue right away to look for the next flip
        self.assertTrue(result)
        mock_notify.assert_not_called()
        statsd.incr.assert_not_called()
        # The other process's claim should stay intact
        self.assertEqual(Flip.objects.get().processed, claimed_at)
        # The worker seat should have been given back
        self.assertTrue(cmd.seats.acquire(blocking=False))

    @time_machine.travel(CURRENT_TIME, tick=False)
    def test_it_postpones_check_whose_status_calculation_fails(self) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = CURRENT_TIME - td(days=2)
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        with patch.object(Check, "get_status", side_effect=ValueError("bad schedule")):
            with self.assertRaisesRegex(ValueError, "bad schedule"):
                Command().handle_going_down()

        check.refresh_from_db()
        self.assertEqual(check.alert_after, CURRENT_TIME + td(hours=1))
        self.assertEqual(check.status, "up")
        self.assertFalse(Flip.objects.exists())

    def test_it_skips_check_flipped_by_another_process(self) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = now() - td(days=2)
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        with updated_concurrently(status="down"):
            result = Command().handle_going_down()

        # It should continue right away to look for the next check
        self.assertTrue(result)
        # The other process created the flip, this one should not
        self.assertFalse(Flip.objects.exists())
        check.refresh_from_db()
        self.assertEqual(check.status, "down")
        self.assertEqual(check.alert_after, check.last_ping + td(days=1, hours=1))

    def run_until_idle(self, *args: str, asleep: Event | None = None) -> str:
        """Run the sendalerts command, deliver SIGTERM when it first goes to sleep.

        Set `asleep` once the signal is delivered, and return the command's output.
        """
        cmd = Command()
        out = StringIO()

        def sleep(secs: float) -> None:
            cmd.on_signal(signal.SIGTERM, None)
            if asleep:
                asleep.set()

        with (
            patch("hc.api.management.commands.sendalerts.signal.signal") as set_handler,
            patch("hc.api.management.commands.sendalerts.time.sleep", side_effect=sleep) as mock_sleep,
        ):
            call_command(cmd, *args, stdout=out)

        mock_sleep.assert_called_once_with(2)
        self.assertEqual(
            set_handler.mock_calls,
            [call(signal.SIGTERM, cmd.on_signal), call(signal.SIGINT, cmd.on_signal)],
        )
        return out.getvalue()

    @patch("hc.api.management.commands.sendalerts.notify")
    def test_handle_processes_checks_going_down(self, mock_notify: Mock) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = now() - td(days=2)
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        asleep = Event()

        def notify_after_sleep(flip: Flip) -> str:
            # Finish only after the main loop has gone to sleep, so the
            # notification log can only appear if the command waits for its workers
            asleep.wait(timeout=5)
            return "check goes down"

        mock_notify.side_effect = notify_after_sleep
        # A second worker seat lets the main loop find there is no more work
        # without waiting for the busy worker
        output = self.run_until_idle("--num-workers", "2", asleep=asleep)

        # It should create a flip and hand it over to a worker
        flip = Flip.objects.get()
        self.assertEqual(flip.owner_id, check.id)
        self.assertIsNotNone(flip.processed)
        mock_notify.assert_called_once_with(flip)

        check.refresh_from_db()
        self.assertEqual(check.status, "down")

        desc = signal.strsignal(signal.SIGTERM)
        self.assertEqual(
            output,
            f"sendalerts is now running\n{desc}, finishing...\ncheck goes down\nDone.\n",
        )

    def test_handle_sizes_the_worker_pool(self) -> None:
        with (
            patch("hc.api.management.commands.sendalerts.BoundedSemaphore", wraps=BoundedSemaphore) as seats,
            patch("hc.api.management.commands.sendalerts.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as executor,
        ):
            self.run_until_idle("--num-workers", "3")

        # Command() sizes both for 10 workers, handle() should resize them
        self.assertEqual(seats.call_args, call(3))
        self.assertEqual(executor.call_args, call(max_workers=3))

    def test_handle_names_the_postgres_connection(self) -> None:
        databases = {"default": {"OPTIONS": {"application_name": "hc"}}}
        with patch("hc.api.management.commands.sendalerts.settings", SimpleNamespace(DATABASES=databases)):
            output = self.run_until_idle()

        self.assertEqual(databases["default"]["OPTIONS"]["application_name"], "sendalerts")
        self.assertNotIn("WARNING", output)
