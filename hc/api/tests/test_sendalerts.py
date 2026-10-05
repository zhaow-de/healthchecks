import signal
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from datetime import timedelta as td
from io import StringIO
from threading import BoundedSemaphore, Event
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import time_machine
from django.core import mail
from django.core.management import call_command
from django.utils.timezone import now

from hc.api.management.commands.sendalerts import Command, notify
from hc.api.models import Channel, Check, Flip, Notification
from hc.api.transports import TransportError
from hc.test import BaseTestCase, updated_concurrently

CURRENT_TIME = datetime(2020, 1, 13, 2, tzinfo=UTC)


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

    @patch("hc.api.management.commands.sendalerts.notify")
    def test_it_processes_flip(self, mock_notify: Mock) -> None:
        check = Check(project=self.project, status="up")
        check.last_ping = now()
        check.alert_after = check.last_ping + td(days=1, hours=1)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "down"
        flip.new_status = "up"
        flip.save()

        mock_notify.return_value = "all is well"
        cmd = Command(stdout=Mock())
        with self.assertLogs("hc", level="INFO") as logs:
            result = cmd.process_one_flip()
            # The worker logs the notification after process_one_flip returns
            cmd.executor.shutdown(wait=True)

        # If it finds work, it should return True
        self.assertTrue(result)

        # It should call `notify` and log what it returns
        mock_notify.assert_called_once()
        self.assertEqual(logs.output, ["INFO:hc:all is well"])

        # It should set the processed date
        flip.refresh_from_db()
        self.assertTrue(flip.processed)

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

    def test_it_does_not_clobber_check_status(self) -> None:
        check = Check(project=self.project, status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        channel = Channel.objects.create(project=self.project, kind="webhook")
        channel.checks.add(check)

        with patch("hc.api.models.Channel.transport") as mock_transport:
            mock_transport.is_noop.return_value = False
            notify(flip)

            args = mock_transport.notify.call_args.args
            # Before sending a notification, we used to set flip.owner.status value
            # to "IF_YOU_SEE_THIS_WE_HAVE_A_BUG". The idea was to use it as 0xDEADBEEF:
            # if it surfaces anywhere in notification contents we know we have a bug.
            # Problem is, webhooks have a $JSON placeholder, which calls
            # Check.get_status(), which reads Check.status. So we *must not*
            # clobber flip.owner.status.
            self.assertEqual(args[0].owner.status, "down")

    def test_it_logs_a_successful_notification(self) -> None:
        check = Check(project=self.project, name="Backups", status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        channel = Channel.objects.create(project=self.project, kind="webhook")
        channel.checks.add(check)

        with patch("hc.api.models.Channel.transport") as mock_transport:
            mock_transport.is_noop.return_value = False
            log = notify(flip)

        assert log is not None
        self.assertEqual(log.splitlines()[0], "'Backups' goes down")
        self.assertNotIn(str(check.code), log)
        self.assertIn(f"{str(channel.code)[:8]} (webhook) OK in", log)

    def test_it_logs_a_failed_notification(self) -> None:
        check = Check(project=self.project, slug="nightly-backup", status="down")
        check.last_ping = now() - td(days=2)
        check.save()

        flip = Flip(owner=check, created=check.last_ping)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        channel = Channel.objects.create(project=self.project, kind="webhook")
        channel.checks.add(check)

        with patch("hc.api.models.Channel.transport") as mock_transport:
            mock_transport.is_noop.return_value = False
            mock_transport.notify.side_effect = TransportError("Test error message")
            log = notify(flip)

        assert log is not None
        self.assertEqual(log.splitlines()[0], "'nightly-backup' goes down")
        self.assertIn(f"{str(channel.code)[:8]} (webhook) Error in", log)
        self.assertIn("Test error message", log)

    def test_a_raising_channel_does_not_stop_the_others(self) -> None:
        check = Check.objects.create(project=self.project, status="down")
        flip = Flip.objects.create(owner=check, created=now(), old_status="up", new_status="down")
        for _ in range(2):
            Channel.objects.create(project=self.project, kind="webhook").checks.add(check)

        with (
            patch("hc.api.models.Channel.transport") as mock_transport,
            self.assertLogs("hc.api.models", "ERROR") as logs,
        ):
            mock_transport.is_noop.return_value = False
            mock_transport.notify.side_effect = [RuntimeError("boom"), None]
            log = notify(flip)

        assert log is not None
        self.assertIn(") Error in", log)
        self.assertIn(") OK in", log)

        # The error is recorded, and the channel stays enabled
        errors = sorted(Notification.objects.values_list("error", flat=True))
        self.assertEqual(errors, ["", "Unexpected error"])
        failed = Channel.objects.get(last_error="Unexpected error")
        self.assertFalse(failed.disabled)
        self.assertEqual(
            logs.records[0].getMessage(),
            f"Notification failed: check '', webhook channel {str(failed.code)[:8]}: Unexpected error",
        )

    def test_a_channel_without_a_transport_does_not_stop_the_others(self) -> None:
        check = Check.objects.create(project=self.project, status="down")
        flip = Flip.objects.create(owner=check, created=now(), old_status="up", new_status="down")
        broken = Channel.objects.create(project=self.project, kind="unknown")
        broken.checks.add(check)
        email = Channel.objects.create(project=self.project, kind="email", value="bob@example.org", email_verified=True)
        email.checks.add(check)

        with self.assertLogs("hc.api.models", "ERROR") as logs:
            log = notify(flip)

        assert log is not None
        self.assertIn(f"{str(broken.code)[:8]} (unknown) Error in", log)
        self.assertIn(f"{str(email.code)[:8]} (email) OK in", log)
        self.assertEqual(
            logs.records[0].getMessage(),
            f"Notification failed: check '', unknown channel {str(broken.code)[:8]}: Unexpected error",
        )
        self.assertEqual(len(mail.outbox), 1)

        broken.refresh_from_db()
        self.assertEqual(broken.last_error, "Unexpected error")
        self.assertFalse(broken.disabled)

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

    def test_it_logs_notify_exceptions(self) -> None:
        cmd = Command(stdout=Mock())
        cmd.seats = BoundedSemaphore(1)
        cmd.seats.acquire()

        future: Future[str | None] = Future()
        future.set_exception(ValueError("boom"))

        # The callback does not re-raise: concurrent.futures would log it again
        with self.assertLogs("hc", "ERROR") as logs:
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

    @patch("hc.api.management.commands.sendalerts.notify")
    def test_it_skips_flip_claimed_by_another_process(self, mock_notify: Mock) -> None:
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

        with (
            patch.object(Check, "get_status", side_effect=ValueError("bad schedule")),
            self.assertRaisesRegex(ValueError, "bad schedule"),
        ):
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

    def run_until_idle(self, *args: str, asleep: Event | None = None) -> list[str]:
        """Run the sendalerts command, deliver SIGTERM when it first goes to sleep.

        Set `asleep` once the signal is delivered, and return the command's log
        records as "LEVEL:logger:message" lines.
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
            self.assertLogs("hc", level="INFO") as logs,
        ):
            call_command(cmd, *args, stdout=out)

        mock_sleep.assert_called_once_with(2)
        self.assertEqual(
            set_handler.mock_calls,
            [call(signal.SIGTERM, cmd.on_signal), call(signal.SIGINT, cmd.on_signal)],
        )
        # Everything should go to the log, nothing straight to stdout
        self.assertEqual(out.getvalue(), "")
        return logs.output

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
        self.assertEqual(output[0], "INFO:hc:sendalerts is now running")
        # The worker may log before or after the main loop logs that it is finishing
        self.assertCountEqual(output[1:], [f"INFO:hc:{desc}, finishing...", "INFO:hc:check goes down"])

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
        desc = signal.strsignal(signal.SIGTERM)
        self.assertEqual(output, ["INFO:hc:sendalerts is now running", f"INFO:hc:{desc}, finishing..."])

    def test_on_signal_only_sets_the_shutdown_flag(self) -> None:
        cmd = Command()
        with self.assertNoLogs("hc"):
            cmd.on_signal(signal.SIGTERM, None)

        self.assertTrue(cmd.shutdown)
        self.assertEqual(cmd.signum, signal.SIGTERM)
