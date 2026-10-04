from __future__ import annotations

from django.urls import reverse

from hc.api.models import Channel, Check, Flip, Notification, Ping
from hc.test import BaseTestCase


class ApiAdminTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Backup & Restore")

        self.alice.is_staff = True
        self.alice.is_superuser = True
        self.alice.save()
        self.client.login(username="alice@example.org", password="password")

    def test_it_shows_checks(self) -> None:
        r = self.client.get(reverse("admin:api_check_changelist"))
        # The name, escaped
        self.assertContains(r, "Backup &amp; Restore")
        self.assertContains(r, '<td class="field-project nowrap">Alices Project</td>', html=True)

    def test_it_shows_pings(self) -> None:
        Ping.objects.create(owner=self.check, scheme="https", method="POST", kind="fail")

        r = self.client.get(reverse("admin:api_ping_changelist"))
        self.assertContains(r, '<td class="field-method">POST</td>', html=True)
        self.assertContains(r, '<td class="field-kind">fail</td>', html=True)

    def test_it_shows_channels(self) -> None:
        Channel.objects.create(project=self.project, kind="webhook", name="<Hook>", last_error="Timed out")

        r = self.client.get(reverse("admin:api_channel_changelist"))
        self.assertContains(r, "&lt;Hook&gt;")
        self.assertContains(r, '<td class="field-last_error">Timed out</td>', html=True)

    def test_it_shows_notifications(self) -> None:
        channel = Channel.objects.create(project=self.project, kind="webhook", name="Hook")
        Notification.objects.create(owner=self.check, channel=channel, check_status="down", error="Received status code 500")

        r = self.client.get(reverse("admin:api_notification_changelist"))
        self.assertContains(r, '<td class="field-channel nowrap">Hook</td>', html=True)
        self.assertContains(r, '<td class="field-error">Received status code 500</td>', html=True)

    def test_it_shows_flips(self) -> None:
        self.check.create_flip("down")

        r = self.client.get(reverse("admin:api_flip_changelist"))
        self.assertContains(r, '<td class="field-new_status">Down</td>', html=True)
        self.assertEqual(Flip.objects.count(), 1)
