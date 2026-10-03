from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from types import TracebackType

from hc.logs import JsonFormatter
from hc.test import BaseTestCase

ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


class JsonFormatterTestCase(BaseTestCase):
    def make_record(self, msg: str, exc_info: ExcInfo | None = None) -> logging.LogRecord:
        record = logging.LogRecord("hc.test", logging.WARNING, __file__, 1, msg, ("World",), exc_info)
        record.created = datetime(2020, 1, 13, 2, 3, 4, 500000, tzinfo=UTC).timestamp()
        return record

    def test_it_writes_one_json_object(self) -> None:
        line = JsonFormatter().format(self.make_record("Hello %s\nand goodbye"))

        # A multi-line message should still make one line
        self.assertNotIn("\n", line)
        self.assertEqual(
            json.loads(line),
            {
                "time": "2020-01-13T02:03:04.500000+00:00",
                "level": "WARNING",
                "logger": "hc.test",
                "message": "Hello World\nand goodbye",
            },
        )

    def test_it_includes_exception(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            exc_type, exc, tb = sys.exc_info()
            assert exc_type and exc
            exc_info: ExcInfo = (exc_type, exc, tb)

        doc = json.loads(JsonFormatter().format(self.make_record("Hello %s", exc_info)))

        self.assertEqual(doc["message"], "Hello World")
        self.assertTrue(doc["exception"].startswith("Traceback (most recent call last):"))
        self.assertTrue(doc["exception"].endswith("ValueError: boom"))
