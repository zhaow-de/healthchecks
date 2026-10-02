from __future__ import annotations

import json
from unittest.mock import Mock, patch

from django.core import mail
from django.test.utils import override_settings
from django.utils.timezone import now

from hc.api.models import Channel, Check, Flip, Notification
from hc.test import BaseTestCase


@override_settings(TWILIO_ACCOUNT="test", TWILIO_AUTH="dummy", TWILIO_FROM="+123")
class NotifyCallTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.check = Check(project=self.project)
        self.check.name = "foo"
        # Transport classes should use flip.new_status,
        # so the status "paused" should not appear anywhere
        self.check.status = "paused"
        self.check.last_ping = now()
        self.check.save()

        self.channel = Channel(project=self.project)
        self.channel.kind = "call"
        self.channel.value = json.dumps({"label": "foo", "value": "+1234567890"})
        self.channel.save()
        self.channel.checks.add(self.check)

        self.flip = Flip(owner=self.check)
        self.flip.created = now()
        self.flip.old_status = "new"
        self.flip.new_status = "down"

    @patch("hc.api.transports.curl.request", autospec=True)
    def test_call(self, mock_post: Mock) -> None:
        mock_post.return_value.status_code = 200

        self.channel.notify(self.flip)

        payload = mock_post.call_args.kwargs["data"]
        self.assertEqual(payload["To"], "+1234567890")
        self.assertIn("""The check "foo" is down.</Say>""", payload["Twiml"])

        n = Notification.objects.get()
        callback_path = f"/api/v3/notifications/{n.code}/status"
        self.assertTrue(payload["StatusCallback"].endswith(callback_path))

    @patch("hc.api.transports.curl.request", autospec=True)
    def test_it_escapes_check_name(self, mock_post: Mock) -> None:
        self.check.name = "Foo & Bar"
        self.check.save()

        mock_post.return_value.status_code = 200
        self.channel.notify(self.flip)

        payload = mock_post.call_args.kwargs["data"]
        # The Twiml field contains XML so & should be escaped to &amp;
        self.assertIn("""The check "Foo &amp; Bar" is down.</Say>""", payload["Twiml"])

    @override_settings(TWILIO_ACCOUNT=None)
    def test_it_requires_twilio_configuration(self) -> None:
        self.channel.notify(self.flip)
        n = Notification.objects.get()
        self.assertEqual(n.error, "Call notifications are not enabled")

    @patch("hc.api.transports.curl.request", autospec=True)
    def test_it_has_no_monthly_quota(self, mock_post: Mock) -> None:
        mock_post.return_value.status_code = 200

        for _ in range(3):
            self.channel.notify(self.flip)

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(Notification.objects.filter(error="").count(), 3)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(TWILIO_FROM="+000")
    @patch("hc.integrations.call.transport.logger.debug", autospec=True)
    @patch("hc.api.transports.curl.request", autospec=True)
    def test_it_disables_channel_on_21211(self, mock_post: Mock, debug: Mock) -> None:
        # Twilio's error 21211 is "Invalid 'To' Phone Number"
        mock_post.return_value.status_code = 400
        mock_post.return_value.content = b"""{"code": 21211}"""

        self.channel.notify(self.flip)

        # Make sure the HTTP request was made only once (no retries):
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.disabled)

        n = Notification.objects.get()
        self.assertEqual(n.error, "Invalid phone number")

        # It should give up after the first try
        self.assertEqual(mock_post.call_count, 1)

        # It should not log this event
        self.assertFalse(debug.called)
