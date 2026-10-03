from __future__ import annotations

from datetime import timedelta as td

from django.utils.timezone import now

from hc.api.models import Check, Ping
from hc.test import BaseTestCase


class LogTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.profile.tz = "Europe/Riga"
        self.profile.save()

        self.check = Check(project=self.project)
        self.check.created = "2000-01-01T00:00:00+00:00"
        self.check.kind = "cron"
        self.check.tz = "Europe/Berlin"
        self.check.save()

        self.ping = Ping.objects.create(owner=self.check, n=1)
        self.ping.body_raw = b"hello world"

        # The log starts at the oldest ping: backdate it so the pings the tests add later fall inside it:
        self.ping.created = "2000-01-01T00:00:00+00:00"
        self.ping.save()

        self.url = f"/checks/{self.check.code}/log/"

    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "hello world")
        # It should offer both the profile's tz and the check's tz
        # in the timezone switcher:
        self.assertContains(r, "Europe/Riga")
        self.assertContains(r, "Europe/Berlin")

    def test_it_handles_bad_uuid(self) -> None:
        url = "/checks/not-uuid/log/"

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_it_handles_missing_uuid(self) -> None:
        # Valid UUID but there is no check for it:
        url = "/checks/6837d6ec-fc08-4da5-a67f-08a9ed1ccf62/log/"

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_it_checks_ownership(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_shows_ignored_nonzero_exitstatus(self) -> None:
        self.ping.kind = "ign"
        self.ping.exitstatus = 123
        self.ping.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Ignored", status_code=200)

    def test_it_handles_log_event(self) -> None:
        self.ping.kind = "log"
        self.ping.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "label-log", status_code=200)

    def test_it_does_not_show_duration_for_log_event(self) -> None:
        h = td(hours=1)
        Ping.objects.create(owner=self.check, n=2, kind="start", created=now() - h)
        Ping.objects.create(owner=self.check, n=3, kind="log", created=now() - h * 2)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "label-log", status_code=200)
        self.assertNotContains(r, "ic-timer", status_code=200)

    def test_it_does_not_show_duration_for_ign_event(self) -> None:
        h = td(hours=1)
        Ping.objects.create(owner=self.check, n=2, kind="start", created=now() - h)
        Ping.objects.create(owner=self.check, n=3, kind="ign", created=now() - h * 2)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "label-ign", status_code=200)
        self.assertNotContains(r, "ic-timer", status_code=200)
