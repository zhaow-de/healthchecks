from __future__ import annotations

import json
import re
from datetime import timedelta as td
from io import StringIO
from unittest.mock import Mock, patch

from django.core import mail
from django.test.utils import override_settings
from django.utils.timezone import now

from hc.accounts.management.commands.senddeletionscheduled import Command
from hc.accounts.models import Member, Project
from hc.api.models import Channel, Check, Flip, Notification
from hc.test import BaseTestCase

MOCK_SLEEP = Mock()


def counts(result: str) -> list[int]:
    """Extract integer values from command's return value."""
    return [int(s) for s in re.findall(r"\d+", result)]


@override_settings(SITE_NAME="Mychecks")
@patch("hc.api.management.commands.sendreports.time.sleep", MOCK_SLEEP)
class SendDeletionScheduledTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.channel = Channel(project=self.project, kind="email")
        self.channel.value = "alerts@example.org"
        self.channel.email_verified = True
        self.channel.save()

    def test_it_sends_notice(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=31)
        self.profile.save()

        Check.objects.create(project=self.project)
        Check.objects.create(project=self.project)

        cmd = Command(stdout=Mock())
        result = cmd.handle()
        self.assertEqual(counts(result), [1])

        email = mail.outbox[0]
        self.assertEqual(email.subject, "Account Deletion Warning")
        self.assertEqual(email.to[0], "alice@example.org")

        self.assertEmailContainsText("Owner: alice@example.org")
        self.assertEmailContainsText("Number of checks in the account: 2")

        self.assertEmailContainsHtml("Owner: <strong>alice@example.org</strong>")
        self.assertEmailContainsHtml("Number of checks in the account: <strong>2</strong>")

    def test_it_sends_notice_to_team_members(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=31)
        self.profile.save()

        self.bob.last_login = now()
        self.bob.save()

        cmd = Command(stdout=Mock())
        result = cmd.handle()
        self.assertEqual(counts(result), [1])

        self.assertEqual(mail.outbox[0].to, ["alice@example.org", "bob@example.org"])

    def test_it_skips_profiles_with_deletion_scheduled_date_not_set(self) -> None:
        cmd = Command(stdout=Mock())
        result = cmd.handle()
        self.assertEqual(counts(result), [0])
        self.assertEqual(len(mail.outbox), 0)

    def test_it_skips_profiles_with_deletion_scheduled_date_in_past(self) -> None:
        self.profile.deletion_scheduled_date = now() - td(minutes=1)
        self.profile.save()

        cmd = Command(stdout=Mock())
        result = cmd.handle()
        self.assertEqual(counts(result), [0])
        self.assertEqual(len(mail.outbox), 0)

    def test_it_avoids_duplicate_recipients(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=31)
        self.profile.save()

        self.bob.last_login = now()
        self.bob.save()

        second_project = Project.objects.create(owner=self.alice)
        Member.objects.create(user=self.bob, project=second_project, role=Member.Role.REGULAR)

        cmd = Command(stdout=Mock())
        cmd.handle()
        # Bob should be listed as a recipient a single time, despite two memberships:
        self.assertEqual(mail.outbox[0].to, ["alice@example.org", "bob@example.org"])

    def test_it_notifies_channel(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=5)
        self.profile.save()

        cmd = Command(stdout=Mock())
        cmd.handle()

        self.assertEqual(mail.outbox[0].subject, "Account Deletion Warning")
        s = "DOWN | Mychecks Account Deletion"
        self.assertTrue(mail.outbox[1].subject.startswith(s))

    def test_it_does_not_notify_channels_if_more_than_14_days_left(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=15, minutes=1)
        self.profile.save()

        cmd = Command(stdout=Mock())
        cmd.handle()

        self.assertEqual(len(mail.outbox), 1)

    def test_it_skips_email_channels_of_team_members(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=5)
        self.profile.save()

        self.channel.value = "alice@example.org"
        self.channel.save()

        cmd = Command(stdout=Mock())
        cmd.handle()

        self.assertEqual(len(mail.outbox), 1)

    def test_it_reports_channel_errors(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=5)
        self.profile.save()

        self.channel.email_verified = False
        self.channel.save()

        stdout = StringIO()
        Command(stdout=stdout).handle()

        self.assertIn("   Error sending notification: Email not verified", stdout.getvalue())
        # Only the deletion warning goes out, the unverified channel gets nothing
        self.assertEqual([m.subject for m in mail.outbox], ["Account Deletion Warning"])
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.last_error, "Email not verified")

    def test_it_retries_channels_that_ignore_down_events(self) -> None:
        self.profile.deletion_scheduled_date = now() + td(days=5)
        self.profile.save()

        self.channel.value = json.dumps({"value": "alerts@example.org", "up": True, "down": False})
        self.channel.save()

        statuses: list[str] = []
        real_notify = Channel.notify

        def spy(channel: Channel, flip: Flip, is_test: bool = False) -> str:
            # Read the status at call time: the command mutates the same dummy
            # check between the two calls, so call_args_list would show "up" twice.
            statuses.append(flip.owner.status)
            return real_notify(channel, flip, is_test=is_test)

        stdout = StringIO()
        with patch.object(Channel, "notify", autospec=True, side_effect=spy):
            Command(stdout=stdout).handle()

        # The first attempt is a no-op, so the command retries with the dummy
        # check's status set to "up"...
        self.assertEqual(statuses, ["down", "up"])
        # ...but Channel.notify() decides on the flip's new_status, which stays
        # "down": the retry is a no-op too and the up-only channel gets nothing.
        self.assertIn("   Error sending notification: no-op", stdout.getvalue())
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(Notification.objects.exists())
