import logging
from datetime import timedelta as td
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test.utils import override_settings
from django.utils.timezone import now

from hc.logs.models import Record
from hc.test import BaseTestCase


@override_settings(
    ADMINS=["admin@example.org"],
    EMAIL_SUBJECT_PREFIX="[hc] ",
    SITE_ROOT="http://example.com",
)
class SendLogsTestCase(BaseTestCase):
    def add_record(self, age: td) -> None:
        Record.objects.create(
            created=now() - age,
            name="hc.api",
            level=logging.ERROR,
            message="Something went wrong",
            traceback="",
        )

    def run_command(self) -> str:
        stdout = StringIO()
        call_command("sendlogs", stdout=stdout)
        return stdout.getvalue()

    def test_it_does_nothing_without_records(self) -> None:
        self.assertEqual(self.run_command(), "Done, no new log records.\n")
        self.assertEqual(len(mail.outbox), 0)

    def test_it_ignores_records_older_than_24_hours(self) -> None:
        self.add_record(td(hours=25))

        self.assertEqual(self.run_command(), "Done, no new log records.\n")
        self.assertEqual(len(mail.outbox), 0)

    def test_it_notifies_admins_about_one_record(self) -> None:
        self.add_record(td(hours=1))
        self.add_record(td(hours=25))

        self.assertEqual(self.run_command(), "Done, 1 new log record.\n")

        email = mail.outbox[0]
        self.assertEqual(email.to, ["admin@example.org"])
        self.assertEqual(email.subject, "[hc] 1 new log record in the last 24 hours")
        self.assertEqual(email.body, "1 new log record in the last 24 hours")

        html, mimetype = email.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("1 new log record in the last 24 hours.<br />", html)
        self.assertIn('<a href="http://example.com/admin/logs/record/">Show log records</a>', html)

    def test_it_pluralizes(self) -> None:
        self.add_record(td(hours=1))
        self.add_record(td(hours=23))

        self.assertEqual(self.run_command(), "Done, 2 new log records.\n")
        self.assertEqual(mail.outbox[0].subject, "[hc] 2 new log records in the last 24 hours")

    @override_settings(ADMINS=[])
    def test_it_sends_nothing_without_admins(self) -> None:
        self.add_record(td(hours=1))

        self.assertEqual(self.run_command(), "Done, 1 new log record.\n")
        self.assertEqual(len(mail.outbox), 0)
