from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

from django.conf import settings
from django.core import mail
from django.test.utils import override_settings

from hc.logs.models import Record
from hc.test import BaseTestCase

# Runs outside the test run, where the console handler is not replaced: of these
# records only "Hello World", "Sending" and "Careful" should reach the console,
# each once, and nothing should reach stderr
SCRIPT = """
import logging
import django

django.setup()
server = logging.getLogger("django.server")
server.info('"GET / HTTP/1.1" 200 9')
server.warning('"GET /missing/ HTTP/1.1" 404 9')
server.error('"GET /broken/ HTTP/1.1" 500 9')
logging.getLogger("django.request").warning("Not Found: /missing/")
logging.getLogger("django").debug("debug line")
logging.getLogger("django").info("Hello %s", "World")
logging.getLogger("hc").debug("debug line")
logging.getLogger("hc").info("Sending")
logging.getLogger("concurrent.futures").info("info line")
logging.getLogger("concurrent.futures").warning("Careful")
"""


def run_script(log_format: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "LOG_FORMAT"}
    env["DJANGO_SETTINGS_MODULE"] = "hc.settings"
    # Keep the script away from any database file
    env["DB"] = "sqlite"
    env["DB_NAME"] = ":memory:"
    if log_format is not None:
        env["LOG_FORMAT"] = log_format
    return subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


class LoggingConfigTestCase(BaseTestCase):
    def test_hc_logs_info_to_console_and_warnings_to_db(self) -> None:
        self.assertEqual(
            settings.LOGGING["loggers"]["hc"],
            {"level": "INFO", "handlers": ["console", "db"], "propagate": False},
        )

        logger = logging.getLogger("hc")
        self.assertTrue(logger.isEnabledFor(logging.INFO))
        self.assertFalse(logger.isEnabledFor(logging.DEBUG))

        # Only problems should reach the database
        logging.getLogger("hc.test").info("Sent monthly report")
        self.assertFalse(Record.objects.exists())
        logging.getLogger("hc.test").warning("Careful")
        self.assertEqual(Record.objects.get().message, "Careful")

    def test_django_request_logs_errors_only(self) -> None:
        self.assertEqual(
            settings.LOGGING["loggers"]["django.request"],
            {"level": "ERROR", "handlers": ["console", "db", "mail_admins"], "propagate": False},
        )

    @override_settings(ADMINS=["admin@example.org"])
    def test_django_errors_reach_admins_unless_debug(self) -> None:
        logger = logging.getLogger("django.security.DisallowedHost")
        with override_settings(DEBUG=True):
            logger.error("Invalid HTTP_HOST header")
        self.assertEqual(len(mail.outbox), 0)

        logger.warning("Forbidden (CSRF cookie not set.)")
        self.assertEqual(len(mail.outbox), 0)

        logger.error("Invalid HTTP_HOST header")
        self.assertEqual([m.to for m in mail.outbox], [["admin@example.org"]])

    def test_django_server_is_silent(self) -> None:
        result = run_script()

        # runserver's request lines should reach neither stream at any status
        self.assertNotIn("HTTP/1.1", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_console_writes_text_by_default(self) -> None:
        result = run_script()

        ts = r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}"
        self.assertRegex(
            result.stdout,
            rf"\A{ts} INFO django Hello World\n{ts} INFO hc Sending\n{ts} WARNING concurrent.futures Careful\n\Z",
        )
        self.assertEqual(result.stderr, "")

    def test_console_writes_json(self) -> None:
        # The value should be read case-insensitively, without the whitespace
        for log_format in ("json", " JSON "):
            with self.subTest(log_format=log_format):
                result = run_script(log_format)

                docs = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual(
                    [(doc["level"], doc["logger"], doc["message"]) for doc in docs],
                    [
                        ("INFO", "django", "Hello World"),
                        ("INFO", "hc", "Sending"),
                        ("WARNING", "concurrent.futures", "Careful"),
                    ],
                )
                self.assertEqual(result.stderr, "")
