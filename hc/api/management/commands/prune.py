import math
from datetime import timedelta as td
from time import monotonic, sleep
from typing import Any

from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import QuerySet
from django.utils.timezone import now

from hc.api.models import Check, Notification, TokenBucket

# Test notifications have no check, so Check.prune never reaches them
TEST_NOTIFICATION_RETENTION = td(days=30)
# Every bucket refills within 24 hours and a missing row acts as a full
# bucket, so deleting a bucket idle for longer changes no decision
TOKEN_BUCKET_RETENTION = td(days=1)
ADMIN_LOG_RETENTION = td(days=365)

BATCH_SIZE = 1000
VACUUM_PAGES = 500
# Between two write batches, in seconds. SQLite's busy handler retries up to
# 100 ms apart, so a shorter pause hands the lock back to the next batch
# ahead of a ping that is waiting for it.
PAUSE = 0.25
# In seconds. docker/uwsgi.ini kills a run at 1800; past this limit each
# step stops after its current batch and leaves the rest to the next run.
TIME_LIMIT = 900


def delete_in_batches(qs: QuerySet[Any], deadline: float = math.inf) -> int:
    """Delete the rows qs selects, BATCH_SIZE at a time, and return how many.

    Outside transaction.atomic(), each batch is its own transaction. qs has
    to select by a cutoff that new rows do not meet, or the loop may not end.
    """
    deleted = 0
    while True:
        n, _ = qs.filter(pk__in=qs.values("pk")[:BATCH_SIZE]).delete()
        deleted += n
        if n < BATCH_SIZE or monotonic() > deadline:
            return deleted
        sleep(PAUSE)


def delete_stale_token_buckets(deadline: float = math.inf) -> int:
    return delete_in_batches(TokenBucket.objects.filter(updated__lt=now() - TOKEN_BUCKET_RETENTION), deadline)


def free_pages(cursor: Any) -> int:
    cursor.execute("PRAGMA freelist_count")
    return cursor.fetchone()[0]


def reclaim_sqlite_pages(cursor: Any, deadline: float) -> str:
    """Give SQLite's free pages back to the file system, VACUUM_PAGES at a time.

    Run it outside a transaction: each PRAGMA is then its own short write.
    Return the part of the summary line that says what it did.
    """
    cursor.execute("PRAGMA auto_vacuum")
    (mode,) = cursor.fetchone()
    if mode != 2:
        return f"SQLite auto_vacuum is {mode}, not 2 (INCREMENTAL): no pages freed"

    freed = 0
    while (left := free_pages(cursor)) and monotonic() < deadline:
        cursor.execute(f"PRAGMA incremental_vacuum({VACUUM_PAGES})")
        # The PRAGMA frees one page per row it returns: without fetchall()
        # it would free one page
        freed += len(cursor.fetchall())
        sleep(PAUSE)
    return f"freed {freed} SQLite pages, {left} left free"


def checkpoint_wal(cursor: Any) -> str | None:
    """Copy the -wal into the database file, so the file shrinks by the pages
    reclaim_sqlite_pages freed: until a checkpoint, they stay in it.

    PASSIVE does not wait for other connections: frames a reader still needs stay
    in the -wal for a later checkpoint. Return the part of the summary line that
    says what it did, or None outside WAL mode.
    """
    cursor.execute("PRAGMA journal_mode")
    if cursor.fetchone()[0] != "wal":
        return None

    cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
    _, frames, checkpointed = cursor.fetchone()
    return f"checkpointed {checkpointed} of {frames} WAL frames"


class Command(BaseCommand):
    help = "Delete what every table keeps past its retention, then give SQLite's free pages back."

    def handle(self, **options: Any) -> str:
        deadline = monotonic() + TIME_LIMIT
        started = now()

        pings = notifications = flips = 0
        for check_id in list(Check.objects.order_by("id").values_list("id", flat=True)):
            if monotonic() > deadline:
                break
            check = Check.objects.filter(id=check_id).select_related("project__owner").first()
            if check is None:
                # Deleted since the list was read
                continue
            n_pings, n_notifications, n_flips = check.prune()
            pings += n_pings
            notifications += n_notifications
            flips += n_flips

        test_notifications = Notification.objects.filter(owner=None, created__lt=started - TEST_NOTIFICATION_RETENTION)
        notifications += delete_in_batches(test_notifications, deadline)
        token_buckets = delete_stale_token_buckets(deadline)
        sessions = delete_in_batches(Session.objects.filter(expire_date__lt=started), deadline)
        admin_log = LogEntry.objects.filter(action_time__lt=started - ADMIN_LOG_RETENTION)
        admin_log_entries = delete_in_batches(admin_log, deadline)

        summary = (
            f"Deleted api_ping {pings}, api_notification {notifications}, api_flip {flips}, "
            f"api_tokenbucket {token_buckets}, django_session {sessions}, django_admin_log {admin_log_entries}"
        )
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                summary += "; " + reclaim_sqlite_pages(cursor, deadline)
                cursor.execute("PRAGMA optimize")
                cursor.fetchall()
                if checkpoint := checkpoint_wal(cursor):
                    summary += "; " + checkpoint
        if monotonic() > deadline:
            summary += f"; reached the {TIME_LIMIT} s time limit"
        return summary
