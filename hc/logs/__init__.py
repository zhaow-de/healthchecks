import json
import logging
import socket
from datetime import UTC, datetime

from django.db import Error

FORMATTER = logging.Formatter()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            doc["exception"] = self.formatException(record.exc_info)
        return json.dumps(doc)


class Handler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Import Record now not earlier, to avoid AppRegistryNotReady exception
        from hc.logs.models import Record

        traceback = ""
        if record.exc_info:
            traceback = FORMATTER.formatException(record.exc_info)

        try:
            Record.objects.create(
                host=socket.gethostname(),
                name=record.name,
                level=record.levelno,
                message=record.getMessage(),
                traceback=traceback,
            )
        except Error:
            self.handleError(record)
