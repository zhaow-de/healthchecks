from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.utils.timezone import now

from hc.accounts.models import Project
from hc.api.models import Channel, Check, Flip


# Needs to subclass from TransactionTestCase not BaseTestCase,
# otherwise test_it_handles_deleted_channel will not work properly.
class NotifyTestCase(TransactionTestCase):
    def _setup_data(self, kind: str, value: str, status: str = "down") -> None:
        self.alice = User.objects.create(username="alice")
        self.project = Project.objects.create(owner=self.alice)
        self.check = Check.objects.create(project=self.project)

        self.channel = Channel(project=self.project)
        self.channel.kind = kind
        self.channel.value = value
        self.channel.email_verified = True
        self.channel.save()
        self.channel.checks.add(self.check)

        self.flip = Flip(owner=self.check)
        self.flip.created = now()
        self.flip.old_status = "new"
        self.flip.new_status = status

    def test_unexpected_channel_kind_records_an_error(self) -> None:
        self._setup_data("invalid", "dummy data")

        with self.assertLogs("hc.api.models", "ERROR") as logs:
            e = self.channel.notify(self.flip)

        self.assertEqual(e, "Unexpected error")
        self.assertIn("NotImplementedError: Unknown channel kind: invalid", logs.output[0])
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.last_error, "Unexpected error")
        self.assertFalse(self.channel.disabled)

    def test_an_unparsable_value_records_an_error(self) -> None:
        self._setup_data("webhook", "{}")

        with self.assertLogs("hc.api.models", "ERROR"):
            e = self.channel.notify(self.flip)

        self.assertEqual(e, "Unexpected error")
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.last_error, "Unexpected error")

    @patch("hc.api.transports.curl.request", autospec=True)
    def test_a_failed_dispatch_is_logged_as_an_error(self, mock_request: Mock) -> None:
        url = "https://hooks.slack.com/services/T0/B0/secret-token"
        self._setup_data("slack", url)
        self.check.name = "Nightly\nbackup"
        self.check.save()
        mock_request.return_value.status_code = 404

        with self.assertLogs("hc.api.models", "ERROR") as logs:
            e = self.channel.notify(self.flip)

        self.assertEqual(e, "Received status code 404")
        (record,) = logs.records
        self.assertEqual(record.levelname, "ERROR")
        self.assertEqual(
            record.getMessage(),
            f"Notification failed: check 'Nightly\\nbackup', slack channel {str(self.channel.code)[:8]}: Received status code 404",
        )
        self.assertNotIn("secret-token", logs.output[0])
        self.assertNotIn(str(self.check.code), logs.output[0])

    @patch("hc.api.transports.curl.request", autospec=True)
    def test_a_failed_test_notification_is_not_logged(self, mock_request: Mock) -> None:
        self._setup_data("slack", "https://hooks.slack.com/services/T0/B0/secret-token")
        mock_request.return_value.status_code = 500

        with self.assertNoLogs("hc.api.models", "ERROR"):
            e = self.channel.notify(self.flip, is_test=True)

        self.assertEqual(e, "Received status code 500")

    @patch("hc.api.transports.curl.request", autospec=True)
    def test_a_group_logs_its_failed_member_alone(self, mock_request: Mock) -> None:
        self._setup_data("slack", "https://hooks.slack.com/services/T0/B0/secret-token")
        member = self.channel
        group = Channel.objects.create(project=self.project, kind="group", value=str(member.code))
        group.checks.add(self.check)
        mock_request.return_value.status_code = 500

        with self.assertLogs("hc.api.models", "ERROR") as logs:
            e = group.notify(self.flip)

        self.assertEqual(e, "1 out of 1 notifications failed")
        (record,) = logs.records
        self.assertIn(f"slack channel {str(member.code)[:8]}: Received status code 500", record.getMessage())

    def test_it_handles_deleted_channel(self) -> None:
        self._setup_data("email", "foo@example.org")

        # Change channel's id to a non-existent value.
        # notify() creates a Notification object, this will cause an IntegrityError.
        # We are testing if IntegrityError is handled.
        self.channel.id = -1
        e = self.channel.notify(self.flip)
        self.assertEqual(e, "Channel or check does not exist any more")
