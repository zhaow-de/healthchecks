from datetime import UTC, datetime
from datetime import timedelta as td
from unittest.mock import patch

import time_machine
from cronsim import CronSim
from django.db import IntegrityError, connection
from django.db.models import Q, QuerySet
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from hc.accounts.models import Project
from hc.api.models import MAX_DURATION, Channel, Check, Flip, Notification, Ping
from hc.test import BaseTestCase

CURRENT_TIME = datetime(2020, 1, 15, tzinfo=UTC)


class CheckModelTestCase(BaseTestCase):
    def test_it_strips_tags(self) -> None:
        check = Check()

        check.tags = " foo  bar "
        self.assertEqual(check.tags_list(), ["foo", "bar"])

        check.tags = " "
        self.assertEqual(check.tags_list(), [])

    def test_filter_any_ignores_the_email_filters(self) -> None:
        check = Check(filter_subject=True, filter_body=True)
        self.assertFalse(check.filter_any())

        check.filter_http_body = True
        self.assertTrue(check.filter_any())

    def test_get_status_handles_new_check(self) -> None:
        check = Check()
        self.assertEqual(check.get_status(), "new")

    def test_status_works_with_grace_period(self) -> None:
        check = Check()
        check.status = "up"
        check.last_ping = now() - td(days=1, minutes=30)

        self.assertEqual(check.get_status(), "grace")

    def test_get_status_handles_paused_check(self) -> None:
        check = Check()
        check.status = "paused"
        check.last_ping = now() - td(days=1, minutes=30)
        self.assertEqual(check.get_status(), "paused")

    def test_status_works_with_cron_syntax(self) -> None:
        # Expect ping every midnight, default grace is 1 hour
        check = Check()
        check.kind = "cron"
        check.schedule = "0 0 * * *"
        check.status = "up"
        check.last_ping = datetime(2000, 1, 1, tzinfo=UTC)

        with time_machine.travel("2000-01-01 23:59+00:00"):
            self.assertEqual(check.get_status(), "up")

        with time_machine.travel("2000-01-02 00:00+00:00"):
            self.assertEqual(check.get_status(), "grace")

        with time_machine.travel("2000-01-02 01:00+00:00"):
            self.assertEqual(check.get_status(), "down")

    def test_status_works_with_oncalendar_syntax(self) -> None:
        # Expect ping every midnight, default grace is 1 hour
        check = Check()
        check.kind = "oncalendar"
        check.schedule = "00:00"
        check.status = "up"
        check.last_ping = datetime(2000, 1, 1, tzinfo=UTC)

        with time_machine.travel("2000-01-01 23:59+00:00"):
            self.assertEqual(check.get_status(), "up")

        with time_machine.travel("2000-01-02 00:00+00:00"):
            self.assertEqual(check.get_status(), "grace")

        with time_machine.travel("2000-01-02 01:00+00:00"):
            self.assertEqual(check.get_status(), "down")

    def test_status_handles_stopiteration(self) -> None:
        # Expect ping every midnight, default grace is 1 hour
        check = Check()
        check.kind = "oncalendar"
        check.schedule = "2019-01-01"
        check.status = "up"
        check.last_ping = datetime(2020, 1, 1, tzinfo=UTC)

        with time_machine.travel(check.last_ping + td(hours=1)):
            self.assertEqual(check.get_status(), "up")

    def test_status_works_with_timezone(self) -> None:
        # Expect ping every day at 10am, default grace is 1 hour
        check = Check()
        check.kind = "cron"
        check.schedule = "0 10 * * *"
        check.status = "up"
        check.last_ping = datetime(2000, 1, 1, tzinfo=UTC)
        check.tz = "Australia/Brisbane"  # UTC+10

        with time_machine.travel("2000-01-01 23:59+00:00"):
            # 09:59am
            self.assertEqual(check.get_status(), "up")

        with time_machine.travel("2000-01-02 00:00+00:00"):
            # 10:00am
            self.assertEqual(check.get_status(), "grace")

        with time_machine.travel("2000-01-02 01:00+00:00"):
            # 11:00am
            self.assertEqual(check.get_status(), "down")

    def test_get_status_handles_past_grace(self) -> None:
        check = Check()
        check.status = "up"
        check.last_ping = now() - td(days=2)

        self.assertEqual(check.get_status(), "down")

    def test_get_status_obeys_down_status(self) -> None:
        check = Check()
        check.status = "down"
        check.last_ping = now() - td(minutes=1)

        self.assertEqual(check.get_status(), "down")

    def test_get_status_handles_down_then_started_and_expired(self) -> None:
        check = Check(status="down")
        # Last ping was 2 days ago
        check.last_ping = now() - td(days=2)
        # Last start was 2 hours ago - the check is past its grace time
        check.last_start = now() - td(hours=2)

        self.assertEqual(check.get_status(), "down")

    def test_get_status_handles_up_then_started(self) -> None:
        check = Check(status="up")
        # Last ping was 2 hours ago, so is still up
        check.last_ping = now() - td(hours=2)
        # Last start was 5 minutes ago
        check.last_start = now() - td(minutes=5)

        # A started check still is considered "up":
        self.assertEqual(check.get_status(), "up")

    def test_get_status_handles_up_then_started_and_expired(self) -> None:
        check = Check(status="up")
        # Last ping was 3 hours ago, so is still up
        check.last_ping = now() - td(hours=3)
        # Last start was 2 hours ago - the check is past its grace time
        check.last_start = now() - td(hours=2)

        self.assertEqual(check.get_status(), "down")

    def test_get_status_handles_paused_then_started_and_expired(self) -> None:
        check = Check(status="paused")
        # Last start was 2 hours ago - the check is past its grace time
        check.last_start = now() - td(hours=2)

        self.assertEqual(check.get_status(), "down")

    def test_get_status_handles_started_and_mia(self) -> None:
        check = Check()
        check.last_start = now() - td(hours=2)

        self.assertEqual(check.get_status(), "down")

    def test_next_ping_with_cron_syntax(self) -> None:
        dt = datetime(2000, 1, 1, tzinfo=UTC)
        # Expect ping every round hour
        check = Check(project=self.project)
        check.kind = "cron"
        check.schedule = "0 * * * *"
        check.status = "up"
        check.last_ping = dt
        # Need to save it for M2M relations to work:
        check.save()

        d = check.to_dict()
        self.assertEqual(d["next_ping"], "2000-01-01T01:00:00+00:00")

    @time_machine.travel(datetime(2000, 1, 1, 0, 30, tzinfo=UTC))
    def test_to_dict_iterates_a_cron_schedule_once(self) -> None:
        check = Check(project=self.project, kind="cron", schedule="0 * * * *", status="up")
        check.last_ping = datetime(2000, 1, 1, tzinfo=UTC)

        with patch("hc.api.models.CronSim", wraps=CronSim) as cronsim:
            d = check.to_dict(readonly=True)

        self.assertEqual(cronsim.call_count, 1)
        self.assertEqual(d["status"], "up")
        self.assertEqual(d["next_ping"], "2000-01-01T01:00:00+00:00")

    def test_to_dict_takes_the_channel_codes_it_is_given(self) -> None:
        check = Check.objects.create(project=self.project)
        c1, c2 = Channel.objects.create(project=self.project), Channel.objects.create(project=self.project)
        check.channel_set.add(c1, c2)
        expected = ",".join(sorted([str(c1.code), str(c2.code)]))

        self.assertEqual(check.to_dict()["channels"], expected)
        with self.assertNumQueries(0):
            self.assertEqual(check.to_dict(channel_codes=[c2.code, c1.code])["channels"], expected)
            self.assertEqual(check.to_dict(channel_codes=[])["channels"], "")

    @time_machine.travel(CURRENT_TIME)
    def test_downtimes_handles_no_flips(self) -> None:
        check = Check(project=self.project)
        check.created = datetime(2019, 1, 1, tzinfo=UTC)
        check.save()

        jan, dec, nov = check.downtimes(3, "UTC")

        # Jan. 2020
        self.assertEqual(jan.boundary.strftime("%m-%Y"), "01-2020")
        self.assertEqual(jan.tz, "UTC")
        self.assertFalse(jan.no_data)
        self.assertEqual(jan.duration, td())
        self.assertEqual(jan.count, 0)

        # Dec. 2019
        self.assertEqual(dec.boundary.strftime("%m-%Y"), "12-2019")
        self.assertEqual(jan.tz, "UTC")
        self.assertFalse(jan.no_data)
        self.assertEqual(dec.duration, td())
        self.assertEqual(dec.count, 0)

        # Nov. 2019
        self.assertEqual(nov.boundary.strftime("%m-%Y"), "11-2019")
        self.assertEqual(jan.tz, "UTC")
        self.assertFalse(jan.no_data)
        self.assertEqual(nov.duration, td())
        self.assertEqual(nov.count, 0)

    @time_machine.travel(CURRENT_TIME, tick=False)
    def test_downtimes_handles_currently_down_check(self) -> None:
        check = Check(project=self.project, status="down")
        check.created = datetime(2019, 1, 1, tzinfo=UTC)
        check.save()

        records = check.downtimes(10, "UTC")
        self.assertEqual(len(records), 10)

        self.assertEqual(records[0].count, 1)
        self.assertEqual(records[0].monthly_uptime(), (31 - 14) / 31)

        for r in records[1:]:
            self.assertEqual(r.count, 1)
            self.assertEqual(r.monthly_uptime(), 0.0)

    @time_machine.travel(CURRENT_TIME)
    def test_monthly_uptime_pct_handles_dst(self) -> None:
        check = Check(project=self.project, status="down")
        check.created = datetime(2019, 1, 1, tzinfo=UTC)
        check.save()

        records = check.downtimes(10, "Europe/Riga")
        self.assertEqual(len(records), 10)

        for r in records[1:]:
            self.assertEqual(r.count, 1)
            self.assertEqual(r.monthly_uptime(), 0.0)

    @time_machine.travel(CURRENT_TIME, tick=False)
    def test_downtimes_handles_flip_one_day_ago(self) -> None:
        check = Check.objects.create(project=self.project, status="down")
        check.created = datetime(2019, 1, 1, tzinfo=UTC)

        flip = Flip(owner=check)
        flip.created = datetime(2020, 1, 14, tzinfo=UTC)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        records = check.downtimes(10, "UTC")
        self.assertEqual(len(records), 10)
        for r in records:
            assert isinstance(r.duration, td)
            if r.boundary.month == 1:
                self.assertEqual(r.duration.total_seconds(), 86400)
                self.assertEqual(r.count, 1)
            else:
                self.assertEqual(r.duration.total_seconds(), 0)
                self.assertEqual(r.count, 0)

    @time_machine.travel(CURRENT_TIME, tick=False)
    def test_downtimes_handles_flip_two_months_ago(self) -> None:
        check = Check.objects.create(project=self.project, status="down")
        check.created = datetime(2019, 1, 1, tzinfo=UTC)

        flip = Flip(owner=check)
        flip.created = datetime(2019, 11, 15, tzinfo=UTC)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        r = check.downtimes(3, "UTC")
        self.assertEqual(len(r), 3)
        jan, dec, nov = r

        self.assertEqual(jan.boundary.isoformat(), "2020-01-01T00:00:00+00:00")
        self.assertFalse(jan.no_data)
        self.assertEqual(jan.duration, td(days=14))
        self.assertEqual(jan.monthly_uptime(), (31 - 14) / 31)
        self.assertEqual(jan.count, 1)

        self.assertEqual(dec.boundary.isoformat(), "2019-12-01T00:00:00+00:00")
        self.assertFalse(dec.no_data)
        self.assertEqual(dec.duration, td(days=31))
        self.assertEqual(dec.monthly_uptime(), 0.0)
        self.assertEqual(dec.count, 1)

        self.assertEqual(nov.boundary.isoformat(), "2019-11-01T00:00:00+00:00")
        self.assertFalse(nov.no_data)
        self.assertEqual(nov.duration, td(days=16))
        self.assertEqual(nov.monthly_uptime(), 14 / 30)
        self.assertEqual(nov.count, 1)

    @time_machine.travel(CURRENT_TIME, tick=False)
    def test_downtimes_handles_non_utc_timezone(self) -> None:
        check = Check.objects.create(project=self.project, status="down")
        check.created = datetime(2019, 1, 1, tzinfo=UTC)

        flip = Flip(owner=check)
        flip.created = datetime(2019, 12, 31, 23, tzinfo=UTC)
        flip.old_status = "up"
        flip.new_status = "down"
        flip.save()

        r = check.downtimes(2, "Europe/Riga")
        self.assertEqual(len(r), 2)

        jan, dec = r

        self.assertEqual(jan.boundary.isoformat(), "2020-01-01T00:00:00+02:00")
        self.assertEqual(jan.tz, "Europe/Riga")
        self.assertFalse(jan.no_data)
        self.assertEqual(jan.duration, td(days=14, hours=1))
        total_hours = 31 * 24
        up_hours = total_hours - 14 * 24 - 1
        self.assertEqual(jan.monthly_uptime(), up_hours / total_hours)
        self.assertEqual(jan.count, 1)

        self.assertEqual(dec.boundary.isoformat(), "2019-12-01T00:00:00+02:00")
        self.assertEqual(dec.tz, "Europe/Riga")
        self.assertFalse(dec.no_data)
        self.assertEqual(dec.duration, td())
        self.assertEqual(dec.count, 0)

    @time_machine.travel(CURRENT_TIME)
    def test_downtimes_handles_months_when_check_did_not_exist(self) -> None:
        check = Check(project=self.project)
        check.created = datetime(2020, 1, 1, 9, tzinfo=UTC)
        check.save()

        jan, dec, nov = check.downtimes(3, "UTC")

        # Jan. 2020
        self.assertFalse(jan.no_data)

        # Dec. 2019
        self.assertTrue(dec.no_data)

        # Nov. 2019
        self.assertTrue(nov.no_data)

    @time_machine.travel(CURRENT_TIME)
    def test_it_prunes(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=101)
        Ping.objects.create(owner=check, created=CURRENT_TIME, n=101)
        Ping.objects.create(owner=check, created=CURRENT_TIME, n=1)

        f = Flip(owner=check)
        # older than the earliest ping, and also older than 93 days
        f.created = CURRENT_TIME - td(days=93, seconds=1)
        f.processed = f.created
        f.old_status = "new"
        f.new_status = "down"
        f.save()

        n = Notification(owner=check)
        n.channel = Channel.objects.create(project=self.project, kind="email")
        n.check_status = "down"
        n.created = CURRENT_TIME - td(minutes=10)
        n.save()

        # One ping, one notification, one flip
        self.assertEqual(check.prune(), (1, 1, 1))

        self.assertTrue(Ping.objects.filter(n=101).exists())
        self.assertFalse(Ping.objects.filter(n=1).exists())

        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(Flip.objects.count(), 0)

    @time_machine.travel(CURRENT_TIME)
    def test_it_does_not_prune_flips_less_than_93_days_old(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=101)
        Ping.objects.create(owner=check, n=101)

        f = Flip(owner=check)
        # older than the earliest ping, but not older than 93 days
        f.created = CURRENT_TIME - td(days=92)
        f.processed = f.created
        f.old_status = "new"
        f.new_status = "down"
        f.save()

        check.prune()

        self.assertEqual(Flip.objects.count(), 1)

    @time_machine.travel(CURRENT_TIME)
    def test_it_does_not_prune_unprocessed_flips(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=101)
        Ping.objects.create(owner=check, n=101)
        # older than the earliest ping and than 93 days, but its alerts are not sent yet
        Flip.objects.create(owner=check, created=CURRENT_TIME - td(days=100), old_status="up", new_status="down")

        self.assertEqual(check.prune(), (0, 0, 0))
        self.assertEqual(Flip.objects.count(), 1)

    @time_machine.travel(CURRENT_TIME)
    def test_it_does_not_prune_flips_newer_than_the_earliest_ping(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=101)
        Ping.objects.create(owner=check, n=101)
        Ping.objects.create(owner=check, n=100, created=CURRENT_TIME - td(days=100))

        f = Flip(owner=check)
        # older than 93 days, but not older than the earliest ping
        f.created = CURRENT_TIME - td(days=94)
        f.processed = f.created
        f.old_status = "new"
        f.new_status = "down"
        f.save()

        check.prune()

        self.assertEqual(Flip.objects.count(), 1)

    @time_machine.travel(CURRENT_TIME)
    def test_it_measures_from_the_oldest_retained_ping(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=3)
        for n, days in ((1, 60), (2, 30), (3, 1)):
            Ping.objects.create(owner=check, n=n, created=CURRENT_TIME - td(days=days))
        channel = Channel.objects.create(project=self.project, kind="email")
        # newer than the oldest retained ping, older than the newest
        Notification.objects.create(owner=check, channel=channel, check_status="down", created=CURRENT_TIME - td(days=40))

        self.assertEqual(check.prune(), (0, 0, 0))
        self.assertEqual(Notification.objects.count(), 1)

    def test_prune_reads_only_the_oldest_pings_date(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=1)
        Ping.objects.create(owner=check, n=1, body_raw=b"x" * 1000)

        with CaptureQueriesContext(connection) as ctx:
            check.prune()

        (select,) = [q["sql"] for q in ctx.captured_queries if q["sql"].startswith("SELECT") and 'FROM "api_ping"' in q["sql"]]
        self.assertNotIn("body_raw", select)
        self.assertIn('"api_ping"."created"', select)

    @time_machine.travel(CURRENT_TIME)
    def test_it_keeps_flips_and_notifications_when_no_ping_is_retained(self) -> None:
        check = Check.objects.create(project=self.project, n_pings=101)
        Ping.objects.create(owner=check, n=1)
        Flip.objects.create(owner=check, created=CURRENT_TIME - td(days=100), old_status="new", new_status="down")
        channel = Channel.objects.create(project=self.project, kind="email")
        Notification.objects.create(owner=check, channel=channel, check_status="down", created=CURRENT_TIME - td(days=1))

        self.assertEqual(check.prune(), (1, 0, 0))

        self.assertFalse(Ping.objects.exists())
        self.assertEqual(Flip.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_get_grace_start_returns_utc(self) -> None:
        check = Check(project=self.project)
        check.kind = "cron"
        check.schedule = "15 * * * *"
        check.tz = "Europe/Riga"
        check.last_ping = datetime(2023, 10, 29, 0, 55, tzinfo=UTC)
        check.status = "up"

        gs = check.get_grace_start()
        assert gs
        self.assertEqual(gs.tzinfo, UTC)

    @time_machine.travel("2023-10-29T01:05:00")
    def test_get_status_handles_autumn_dst_transition(self) -> None:
        check = Check(project=self.project)
        check.kind = "cron"
        check.schedule = "15 * * * *"
        check.grace = td(minutes=5)
        check.tz = "Europe/Riga"
        check.last_ping = datetime(2023, 10, 29, 0, 55, tzinfo=UTC)
        check.status = "up"

        # The next expected run time is at 2023-10-29 01:15 UTC, so the check
        # should still be up for 10 minutes:
        self.assertEqual(check.get_status(), "up")

    def test_rename_and_delete_handles_already_deleted_checks(self) -> None:
        check = Check.objects.create(project=self.project)
        same_check = Check.objects.get(id=check.id)
        check.delete()

        # rename_and_delete should handle an already deleted check gracefully:
        same_check.rename_and_delete()

    def test_rename_and_delete_retries_once_after_integrity_error(self) -> None:
        check = Check.objects.create(project=self.project)

        real_delete = QuerySet.delete
        calls: list[QuerySet[Check]] = []

        def flaky_delete(qs: QuerySet[Check]) -> tuple[int, dict[str, int]]:
            calls.append(qs)
            if len(calls) == 1:
                # Simulate a concurrent ping inserted between rename and delete
                raise IntegrityError("FOREIGN KEY constraint failed")
            return real_delete(qs)

        with patch.object(QuerySet, "delete", autospec=True, side_effect=flaky_delete):
            check.rename_and_delete()

        self.assertEqual(len(calls), 2)
        self.assertFalse(Check.objects.filter(id=check.id).exists())

    def test_str_uses_name_then_code(self) -> None:
        check = Check.objects.create(project=self.project, name="Backups")
        self.assertEqual(str(check), f"Backups ({check.id})")

        unnamed = Check.objects.create(project=self.project)
        self.assertEqual(str(unnamed), f"{unnamed.code} ({unnamed.id})")

    def test_get_absolute_url_is_relative(self) -> None:
        check = Check.objects.create(project=self.project)
        self.assertEqual(check.get_absolute_url(), f"/checks/{check.code}/details/")

    def test_clamped_last_duration_returns_short_durations(self) -> None:
        check = Check(project=self.project)
        self.assertIsNone(check.clamped_last_duration())

        check.last_duration = td(minutes=5)
        self.assertEqual(check.clamped_last_duration(), td(minutes=5))

        check.last_duration = MAX_DURATION
        self.assertIsNone(check.clamped_last_duration())

    def test_to_dict_includes_last_duration(self) -> None:
        check = Check.objects.create(project=self.project, last_duration=td(seconds=61, microseconds=500))
        self.assertEqual(check.to_dict()["last_duration"], 61)

        check.last_duration = None
        self.assertNotIn("last_duration", check.to_dict())

    def test_pause_writes_nothing_if_a_step_fails(self) -> None:
        check = Check.objects.create(project=self.project, status="up", last_ping=now())

        with (
            patch.object(Project, "update_next_nag_dates", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            check.pause()

        check.refresh_from_db()
        self.assertEqual(check.status, "up")
        self.assertFalse(Flip.objects.exists())

    def test_pause_and_resume_read_the_row_they_lock(self) -> None:
        check = Check.objects.create(project=self.project, status="up", last_ping=now())
        # sendalerts marks it down after this instance was read
        Check.objects.filter(id=check.id).update(status="down")

        check.pause()
        flip = Flip.objects.get()
        self.assertEqual(flip.old_status, "down")

        stale = Check.objects.get(id=check.id)
        Check.objects.filter(id=check.id).update(status="up")
        # The row is not paused any longer, whatever the instance says
        self.assertFalse(stale.resume())
        self.assertEqual(Flip.objects.count(), 1)

    def test_every_hundredth_ping_prunes_old_pings(self) -> None:
        self.profile.ping_log_limit = 10
        self.profile.save()

        check = Check.objects.create(project=self.project, n_pings=99)
        Ping.objects.create(owner=check, n=1, created=CURRENT_TIME)
        Ping.objects.create(owner=check, n=95, created=CURRENT_TIME)

        Check.ping(Q(id=check.id), "1.2.3.4", "http", "get", "", b"", "success", None)

        # Ping #100 triggers pruning: with the limit of 10, only n > 90 is kept
        self.assertEqual(sorted(check.ping_set.values_list("n", flat=True)), [95, 100])

    def test_other_pings_do_not_prune(self) -> None:
        self.profile.ping_log_limit = 10
        self.profile.save()

        check = Check.objects.create(project=self.project, n_pings=98)
        Ping.objects.create(owner=check, n=1, created=CURRENT_TIME)

        Check.ping(Q(id=check.id), "1.2.3.4", "http", "get", "", b"", "success", None)

        self.assertEqual(sorted(check.ping_set.values_list("n", flat=True)), [1, 99])

    def test_str_shows_the_name_and_the_id(self) -> None:
        check = Check.objects.create(project=self.project, name="Foo")
        self.assertEqual(str(check), f"Foo ({check.id})")

    def test_str_handles_an_unsaved_check(self) -> None:
        check = Check(name="Foo")
        self.assertEqual(str(check), "Foo (None)")

    def test_notification_str_shows_the_code_and_the_status(self) -> None:
        check = Check.objects.create(project=self.project)
        channel = Channel.objects.create(project=self.project, kind="email")
        n = Notification.objects.create(owner=check, channel=channel, check_status="down")
        self.assertEqual(str(n), f"Notification {n.code} (down)")
