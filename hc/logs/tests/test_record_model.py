from __future__ import annotations

from hc.logs.models import Record
from hc.test import BaseTestCase


class RecordModelTestCase(BaseTestCase):
    def test_str_returns_short_message(self) -> None:
        record = Record(message="x" * 99)
        self.assertEqual(str(record), "x" * 99)

    def test_str_truncates_long_message(self) -> None:
        record = Record(message="x" * 100)
        self.assertEqual(str(record), "x" * 100 + "...")

        record = Record(message="0123456789" * 15)
        self.assertEqual(str(record), "0123456789" * 10 + "...")
