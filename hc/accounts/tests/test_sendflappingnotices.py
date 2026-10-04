from __future__ import annotations

from unittest.mock import Mock, patch

from django.core import mail
from django.test.utils import override_settings
from django.utils.timezone import now

from hc.accounts.management.commands.sendflappingnotices import Command
from hc.api.models import Check, Flip
from hc.test import BaseTestCase

MOCK_SLEEP = Mock()


@patch("hc.accounts.management.commands.sendflappingnotices.time.sleep", MOCK_SLEEP)
@patch("hc.accounts.management.commands.sendflappingnotices.FLIP_THRESHOLD", 3)
class SendFlappingNoticesTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        c = Check.objects.create(project=self.project, name="Foo")
        nao = now()
        for _ in range(4):
            Flip.objects.create(owner=c, created=nao, old_status="new", new_status="up")

    def test_it_sends_notice(self) -> None:
        cmd = Command(stdout=Mock())
        cmd.handle()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, """The Check "Foo" Is Flapping""")
        self.assertEqual(mail.outbox[0].to, ["alice@example.org"])

    @override_settings(SUPPORT_EMAIL="support@example.org")
    def test_it_names_support_email(self) -> None:
        Command(stdout=Mock()).handle()
        self.assertEmailContains("to us at support@example.org.")

    @override_settings(SUPPORT_EMAIL=None)
    def test_it_handles_missing_support_email(self) -> None:
        Command(stdout=Mock()).handle()
        self.assertEmailNotContains("reach out")
        self.assertEmailNotContains("None")

    @override_settings(MAILERS={})
    def test_it_sends_nothing_without_smtp(self) -> None:
        result = Command(stdout=Mock()).handle()
        self.assertEqual(result, "No SMTP configuration, no notices sent\n")
        self.assertEqual(len(mail.outbox), 0)
