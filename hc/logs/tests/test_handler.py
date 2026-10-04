import logging
import socket
import sys
from types import TracebackType
from unittest.mock import patch

from django.db import DatabaseError

from hc.logs import Handler
from hc.logs.models import Record
from hc.test import BaseTestCase

type ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


class HandlerTestCase(BaseTestCase):
    def make_record(self, exc_info: ExcInfo | None = None) -> logging.LogRecord:
        return logging.LogRecord("hc.test", logging.WARNING, __file__, 1, "Hello %s", ("World",), exc_info)

    def test_it_saves_record(self) -> None:
        Handler().emit(self.make_record())

        record = Record.objects.get(name="hc.test")
        self.assertEqual(record.host, socket.gethostname())
        self.assertEqual(record.level, logging.WARNING)
        self.assertEqual(record.message, "Hello World")
        self.assertEqual(record.traceback, "")

    def test_it_saves_traceback(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            exc_type, exc, tb = sys.exc_info()
            assert exc_type and exc
            exc_info: ExcInfo = (exc_type, exc, tb)

        Handler().emit(self.make_record(exc_info))

        record = Record.objects.get(name="hc.test")
        self.assertTrue(record.traceback.startswith("Traceback (most recent call last):"))
        self.assertTrue(record.traceback.endswith("ValueError: boom"))

    def test_it_reports_database_error_through_handle_error(self) -> None:
        handler, record = Handler(), self.make_record()
        with (
            patch.object(Record.objects, "create", side_effect=DatabaseError("database is locked")),
            patch.object(handler, "handleError") as handle_error,
        ):
            handler.emit(record)

        handle_error.assert_called_once_with(record)
        self.assertFalse(Record.objects.filter(name="hc.test").exists())
