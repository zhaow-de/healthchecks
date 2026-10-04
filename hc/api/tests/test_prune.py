import math
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from datetime import timedelta as td
from io import StringIO
from itertools import count
from pathlib import Path
from unittest import skipUnless
from unittest.mock import call, patch

import time_machine
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext

from hc.api.management.commands import prune
from hc.api.models import Channel, Check, Flip, Notification, Ping, TokenBucket
from hc.test import BaseTestCase

CURRENT_TIME = datetime(2020, 1, 15, tzinfo=UTC)
DELETED_NOTHING = "Deleted api_ping 0, api_notification 0, api_flip 0, api_tokenbucket 0, django_session 0, django_admin_log 0"


@time_machine.travel(CURRENT_TIME, tick=False)
class PruneTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.channel = Channel.objects.create(project=self.project, kind="email")
        self.profile.ping_log_limit = 10
        self.profile.save()

    def run_prune(self) -> str:
        out = StringIO()
        with patch.object(prune, "sleep"):
            call_command("prune", "--skip-checks", stdout=out)
        return out.getvalue()

    def assert_summary(self, out: str, counts: str) -> None:
        if connection.vendor == "sqlite":
            # The test database is new, so INCREMENTAL, and the run frees every free page
            self.assertRegex(out, rf"\A{re.escape(counts)}; freed \d+ SQLite pages, 0 left free\n\Z")
        else:
            self.assertEqual(out, counts + "\n")

    def add_pings(self, check: Check, n_pings: int, oldest: datetime) -> None:
        check.n_pings = n_pings
        check.save()
        for n in range(1, n_pings + 1):
            Ping.objects.create(owner=check, n=n, created=oldest + td(minutes=n))

    def add_flip(self, check: Check, age: td, processed: bool = True) -> Flip:
        created = CURRENT_TIME - age
        return Flip.objects.create(
            owner=check,
            created=created,
            processed=created if processed else None,
            old_status="up",
            new_status="down",
        )

    def add_notification(self, check: Check | None, age: td) -> Notification:
        return Notification.objects.create(owner=check, channel=self.channel, check_status="down", created=CURRENT_TIME - age)

    def add_admin_log_entry(self, age: td) -> LogEntry:
        return LogEntry.objects.create(
            user=self.alice,
            content_type=ContentType.objects.get_for_model(Check),
            object_id="1",
            object_repr="Check",
            action_flag=ADDITION,
            action_time=CURRENT_TIME - age,
        )

    def test_it_prunes_every_check(self) -> None:
        # Over the limit of 10 by two pings
        busy = Check.objects.create(project=self.project)
        self.add_pings(busy, 12, oldest=CURRENT_TIME - td(hours=1))
        self.add_notification(busy, td(hours=2))
        new_notification = self.add_notification(busy, td(minutes=1))
        self.add_flip(busy, td(days=94))
        unprocessed_flip = self.add_flip(busy, td(days=94), processed=False)
        recent_flip = self.add_flip(busy, td(days=92))

        # Under its limit, and silent for 200 days: only its flips are old
        quiet = Check.objects.create(project=self.project)
        self.add_pings(quiet, 5, oldest=CURRENT_TIME - td(days=200))
        self.add_flip(quiet, td(days=201))

        out = self.run_prune()

        self.assert_summary(
            out, "Deleted api_ping 2, api_notification 1, api_flip 2, api_tokenbucket 0, django_session 0, django_admin_log 0"
        )
        self.assertEqual(sorted(busy.ping_set.values_list("n", flat=True)), list(range(3, 13)))
        self.assertEqual(quiet.ping_set.count(), 5)
        self.assertEqual(list(Notification.objects.all()), [new_notification])
        self.assertEqual(set(Flip.objects.all()), {unprocessed_flip, recent_flip})

    def test_it_skips_checks_deleted_while_running(self) -> None:
        first = Check.objects.create(project=self.project)
        second = Check.objects.create(project=self.project)

        def prune_check(check: Check) -> tuple[int, int, int]:
            # Another process deletes the second check meanwhile
            Check.objects.filter(id=second.id).delete()
            return 0, 0, 0

        with patch.object(Check, "prune", autospec=True, side_effect=prune_check) as mock_prune:
            out = self.run_prune()

        self.assertEqual(mock_prune.mock_calls, [call(first)])
        self.assert_summary(out, DELETED_NOTHING)

    def test_it_prunes_test_notifications_after_30_days(self) -> None:
        self.add_notification(None, td(days=30, seconds=1))
        recent = self.add_notification(None, td(days=29))

        out = self.run_prune()

        self.assert_summary(out, DELETED_NOTHING.replace("api_notification 0", "api_notification 1"))
        self.assertEqual(list(Notification.objects.all()), [recent])

    def test_it_keeps_a_checks_notifications_past_30_days(self) -> None:
        check = Check.objects.create(project=self.project)
        self.add_pings(check, 1, CURRENT_TIME - td(days=60))
        owned = self.add_notification(check, td(days=40))
        self.add_notification(None, td(days=40))

        out = self.run_prune()

        self.assert_summary(out, DELETED_NOTHING.replace("api_notification 0", "api_notification 1"))
        self.assertEqual(list(Notification.objects.all()), [owned])

    def test_it_prunes_token_buckets_idle_for_a_day(self) -> None:
        TokenBucket.objects.create(value="old", updated=CURRENT_TIME - td(days=1, seconds=1))
        TokenBucket.objects.create(value="recent", updated=CURRENT_TIME - td(hours=23))

        out = self.run_prune()

        self.assert_summary(out, DELETED_NOTHING.replace("api_tokenbucket 0", "api_tokenbucket 1"))
        self.assertEqual(list(TokenBucket.objects.values_list("value", flat=True)), ["recent"])

    def test_it_prunes_expired_sessions(self) -> None:
        Session.objects.create(session_key="expired", session_data="", expire_date=CURRENT_TIME - td(seconds=1))
        Session.objects.create(session_key="current", session_data="", expire_date=CURRENT_TIME + td(days=1))

        out = self.run_prune()

        self.assert_summary(out, DELETED_NOTHING.replace("django_session 0", "django_session 1"))
        self.assertEqual(list(Session.objects.values_list("session_key", flat=True)), ["current"])

    def test_it_prunes_admin_log_entries_after_365_days(self) -> None:
        self.add_admin_log_entry(td(days=365, seconds=1))
        recent = self.add_admin_log_entry(td(days=364))

        out = self.run_prune()

        self.assert_summary(out, DELETED_NOTHING.replace("django_admin_log 0", "django_admin_log 1"))
        self.assertEqual(list(LogEntry.objects.all()), [recent])

    def test_a_second_run_deletes_nothing(self) -> None:
        check = Check.objects.create(project=self.project)
        self.add_pings(check, 12, oldest=CURRENT_TIME - td(hours=1))
        self.add_notification(check, td(hours=2))
        self.add_flip(check, td(days=94))
        self.add_flip(check, td(days=94), processed=False)
        self.add_notification(None, td(days=31))
        TokenBucket.objects.create(value="old", updated=CURRENT_TIME - td(days=2))
        Session.objects.create(session_key="expired", session_data="", expire_date=CURRENT_TIME - td(days=1))
        self.add_admin_log_entry(td(days=400))

        first = self.run_prune()
        second = self.run_prune()

        self.assert_summary(
            first, "Deleted api_ping 2, api_notification 2, api_flip 1, api_tokenbucket 1, django_session 1, django_admin_log 1"
        )
        self.assert_summary(second, DELETED_NOTHING)

    def test_it_deletes_in_batches(self) -> None:
        for i in range(5):
            TokenBucket.objects.create(value=f"old-{i}", updated=CURRENT_TIME - td(days=2))

        with (
            patch.object(prune, "BATCH_SIZE", 2),
            patch.object(prune, "sleep") as sleep,
            CaptureQueriesContext(connection) as queries,
        ):
            deleted = prune.delete_stale_token_buckets()

        self.assertEqual(deleted, 5)
        self.assertFalse(TokenBucket.objects.exists())
        deletes = [q["sql"] for q in queries.captured_queries if q["sql"].startswith("DELETE")]
        self.assertEqual(len(deletes), 3)
        for sql in deletes:
            self.assertIn("LIMIT 2", sql)
        # A pause after each full batch, none after the last
        self.assertEqual(sleep.mock_calls, [call(prune.PAUSE)] * 2)

    def test_it_stops_at_the_time_limit(self) -> None:
        check = Check.objects.create(project=self.project)
        self.add_pings(check, 12, oldest=CURRENT_TIME - td(hours=1))
        TokenBucket.objects.create(value="a", updated=CURRENT_TIME - td(days=2))
        TokenBucket.objects.create(value="b", updated=CURRENT_TIME - td(days=2))

        # Every reading of the clock is past the limit set at the start
        clock = count(0, prune.TIME_LIMIT + 1)
        with patch.object(prune, "monotonic", side_effect=clock), patch.object(prune, "BATCH_SIZE", 1):
            out = self.run_prune()

        # No check pruned, one batch per table
        self.assertEqual(check.ping_set.count(), 12)
        self.assertEqual(TokenBucket.objects.count(), 1)
        self.assertTrue(out.startswith(DELETED_NOTHING.replace("api_tokenbucket 0", "api_tokenbucket 1")))
        self.assertTrue(out.endswith(f"; reached the {prune.TIME_LIMIT} s time limit\n"))

    @skipUnless(connection.vendor == "sqlite", "reads SQLite's auto_vacuum")
    def test_new_sqlite_databases_are_incremental(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA auto_vacuum")
            self.assertEqual(cursor.fetchone()[0], 2)


class ReclaimSqlitePagesTestCase(SimpleTestCase):
    def make_db(self, auto_vacuum: str) -> sqlite3.Cursor:
        """Create a file database with free pages, return a cursor on it."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "db.sqlite"

        # Autocommit, as Django runs outside transaction.atomic()
        db = sqlite3.connect(self.path, isolation_level=None)
        self.addCleanup(db.close)
        db.execute(f"PRAGMA auto_vacuum = {auto_vacuum}")
        db.execute("CREATE TABLE t (b BLOB)")
        db.execute("BEGIN")
        # One row per 4096-byte page
        db.executemany("INSERT INTO t VALUES (?)", [(bytes(4000),)] * 200)
        db.execute("COMMIT")
        db.execute("DELETE FROM t")
        return db.cursor()

    def test_it_frees_every_free_page(self) -> None:
        cursor = self.make_db("INCREMENTAL")
        free = prune.free_pages(cursor)
        self.assertGreaterEqual(free, 200)
        size = self.path.stat().st_size

        with patch.object(prune, "VACUUM_PAGES", 50), patch.object(prune, "sleep") as sleep:
            result = prune.reclaim_sqlite_pages(cursor, math.inf)

        self.assertEqual(result, f"freed {free} SQLite pages, 0 left free")
        self.assertEqual(prune.free_pages(cursor), 0)
        self.assertLessEqual(self.path.stat().st_size, size - free * 4096)
        # One pause after each 50-page chunk
        self.assertEqual(sleep.call_count, math.ceil(free / 50))

    def test_it_stops_at_the_deadline(self) -> None:
        cursor = self.make_db("INCREMENTAL")
        free = prune.free_pages(cursor)

        # Before the deadline for the first chunk, past it for the second
        with (
            patch.object(prune, "VACUUM_PAGES", 50),
            patch.object(prune, "sleep"),
            patch.object(prune, "monotonic", side_effect=[0, 10]),
        ):
            result = prune.reclaim_sqlite_pages(cursor, 5)

        self.assertEqual(result, f"freed 50 SQLite pages, {free - 50} left free")
        self.assertEqual(prune.free_pages(cursor), free - 50)

    def test_it_leaves_a_database_without_incremental_auto_vacuum(self) -> None:
        cursor = self.make_db("NONE")
        free = prune.free_pages(cursor)
        self.assertGreaterEqual(free, 200)

        with patch.object(prune, "sleep") as sleep:
            result = prune.reclaim_sqlite_pages(cursor, math.inf)

        self.assertEqual(result, "SQLite auto_vacuum is 0, not 2 (INCREMENTAL): no pages freed")
        self.assertEqual(prune.free_pages(cursor), free)
        sleep.assert_not_called()
