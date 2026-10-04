import json
import logging
import os
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test.utils import override_settings

from hc.api.tests.test_database import settings_module
from hc.test import BaseTestCase

# Runs outside the test run, where the console handler is not replaced
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
logging.getLogger("hc").warning("Retrying")
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
    def test_hc_logs_info_to_console_alone(self) -> None:
        self.assertEqual(
            settings.LOGGING["loggers"]["hc"],
            {"level": "INFO", "handlers": ["console"], "propagate": False},
        )

        logger = logging.getLogger("hc")
        self.assertTrue(logger.isEnabledFor(logging.INFO))
        self.assertFalse(logger.isEnabledFor(logging.DEBUG))

    def test_django_request_logs_errors_only(self) -> None:
        self.assertEqual(
            settings.LOGGING["loggers"]["django.request"],
            {"level": "ERROR", "handlers": ["console", "mail_admins"], "propagate": False},
        )

    @override_settings(ADMINS=["admin@example.org"])
    def test_django_errors_reach_admins_unless_debug(self) -> None:
        logger = logging.getLogger("django.security.SuspiciousOperation")
        with override_settings(DEBUG=True):
            logger.error("Suspicious operation")
        self.assertEqual(len(mail.outbox), 0)

        logger.warning("Suspicious operation")
        self.assertEqual(len(mail.outbox), 0)

        logger.error("Suspicious operation")
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
            rf"\A{ts} INFO django Hello World\n{ts} INFO hc Sending\n{ts} WARNING hc Retrying\n"
            rf"{ts} WARNING concurrent.futures Careful\n\Z",
        )
        self.assertEqual(result.stderr, "")

    def test_a_log_format_in_local_settings_reaches_the_console_handler(self) -> None:
        # As outside a test run: a test run's overrides at the end of hc/settings.py replace the handler
        with patch.object(sys, "argv", ["manage.py"]), patch.dict(sys.modules):
            sys.modules.pop("pytest", None)
            module = settings_module({"LOG_FORMAT": " JSON "}, LOG_FORMAT="text")
            kept = settings_module({"LOG_FORMAT": "json", "LOGGING": {"version": 1}})
        self.assertEqual(module.LOGGING["handlers"]["console"]["formatter"], "json")
        self.assertEqual(kept.LOGGING, {"version": 1})

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
                        ("WARNING", "hc", "Retrying"),
                        ("WARNING", "concurrent.futures", "Careful"),
                    ],
                )
                self.assertEqual(result.stderr, "")
