from collections.abc import Callable
from datetime import timedelta as td
from typing import Any
from unittest import skipUnless

from django.db import connection
from django.urls import reverse
from django.utils.timezone import now

from hc.api.models import Channel, Check, Flip, Ping
from hc.api.transports import Transport
from hc.test import BaseTestCase


def secondary_indexes(table: str) -> dict[str, list[str]]:
    """Map each index on the table that is neither unique nor the primary key to its columns."""
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return {name: c["columns"] for name, c in constraints.items() if c["index"] and not c["unique"] and not c["primary_key"]}


class IndexesTestCase(BaseTestCase):
    def test_api_ping_has_one_index_by_owner_and_n(self) -> None:
        self.assertEqual(secondary_indexes("api_ping"), {"api_ping_owner_n": ["owner_id", "n"]})

    def test_api_notification_is_indexed_by_owner_and_created(self) -> None:
        indexes = secondary_indexes("api_notification")
        self.assertEqual(indexes["api_notification_owner_created"], ["owner_id", "created"])
        self.assertEqual(sorted(indexes.values()), [["channel_id"], ["owner_id", "created"]])

    def test_no_foreign_key_index_repeats_a_composite_prefix(self) -> None:
        self.assertEqual(sorted(secondary_indexes("api_flip").values()), [["owner_id", "created"], ["processed"]])
        self.assertEqual(sorted(secondary_indexes("api_check").values()), [["alert_after"], ["project_id", "slug"]])


@skipUnless(connection.vendor == "sqlite", "reads SQLite's EXPLAIN QUERY PLAN")
class PingQueryPlansTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project, n_pings=3)
        for n, kind in ((1, "start"), (2, None), (3, None)):
            self.check.ping_set.create(n=n, kind=kind, created=now() - td(minutes=10 - n))

    def plans(self, fn: Callable[[], Any]) -> list[str]:
        """Run fn, return the plan of each statement it runs that reads api_ping."""
        statements: list[tuple[str, Any]] = []

        def capture(execute: Any, sql: str, params: Any, many: bool, context: Any) -> Any:
            statements.append((sql, params))
            return execute(sql, params, many, context)

        with connection.execute_wrapper(capture):
            fn()

        plans = []
        with connection.cursor() as cursor:
            for sql, params in statements:
                if 'FROM "api_ping"' in sql:
                    cursor.execute("EXPLAIN QUERY PLAN " + sql, params)
                    plans.append(" / ".join(row[-1] for row in cursor.fetchall()))
        return plans

    def assert_served_by_owner_n(self, fn: Callable[[], Any]) -> None:
        plans = self.plans(fn)
        self.assertTrue(plans)
        for plan in plans:
            self.assertIn("INDEX api_ping_owner_n", plan)
            self.assertNotIn("TEMP B-TREE", plan)

    def test_prune(self) -> None:
        self.assert_served_by_owner_n(self.check.prune)

    def test_last_ping(self) -> None:
        flip = Flip.objects.create(owner=self.check, created=now(), old_status="up", new_status="down")
        channel = Channel.objects.create(project=self.project, kind="webhook")
        self.assert_served_by_owner_n(lambda: Transport(channel).last_ping(flip))

    def test_duration(self) -> None:
        ping = Ping.objects.get(owner=self.check, n=2)
        self.assert_served_by_owner_n(lambda: ping.duration)

    def test_api_pings(self) -> None:
        url = reverse("hc-api-pings", args=[self.check.code])
        self.assert_served_by_owner_n(lambda: self.client.get(url, HTTP_X_API_KEY=self.api_key))
