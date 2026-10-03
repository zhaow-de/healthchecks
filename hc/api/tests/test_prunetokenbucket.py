from __future__ import annotations

from datetime import datetime, timezone
from datetime import timedelta as td
from io import StringIO

import time_machine
from django.core.management import call_command

from hc.api.models import TokenBucket
from hc.test import BaseTestCase

CURRENT_TIME = datetime(2020, 1, 13, 2, tzinfo=timezone.utc)


@time_machine.travel(CURRENT_TIME, tick=False)
class PruneTokenBucketTestCase(BaseTestCase):
    def test_it_removes_entries_older_than_a_day(self) -> None:
        TokenBucket.objects.create(value="old", updated=CURRENT_TIME - td(days=1, seconds=1))
        TokenBucket.objects.create(value="older", updated=CURRENT_TIME - td(days=30))
        TokenBucket.objects.create(value="recent", updated=CURRENT_TIME - td(hours=23))

        out = StringIO()
        call_command("prunetokenbucket", stdout=out)

        self.assertEqual(out.getvalue(), "Done! Pruned 2 token bucket entries\n")
        self.assertEqual(list(TokenBucket.objects.values_list("value", flat=True)), ["recent"])

    def test_it_handles_empty_table(self) -> None:
        out = StringIO()
        call_command("prunetokenbucket", stdout=out)

        self.assertEqual(out.getvalue(), "Done! Pruned 0 token bucket entries\n")

    def test_it_removes_every_entry_with_all(self) -> None:
        TokenBucket.objects.create(value="old", updated=CURRENT_TIME - td(days=30))
        TokenBucket.objects.create(value="pw-recent", updated=CURRENT_TIME)

        out = StringIO()
        call_command("prunetokenbucket", "--all", stdout=out)

        self.assertEqual(out.getvalue(), "Done! Pruned 2 token bucket entries\n")
        self.assertFalse(TokenBucket.objects.exists())
