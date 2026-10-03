from __future__ import annotations

from hc.api.models import Channel, Check
from hc.test import BaseTestCase


class ChannelChecksTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.channel = Channel(project=self.project, kind="email")
        self.channel.value = "alice@example.org"
        self.channel.save()

        self.check = Check.objects.create(project=self.project, name="Database Backups")

    def test_it_works(self) -> None:
        url = f"/integrations/{self.channel.code}/checks/"

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(url)
        self.assertContains(r, "Database Backups")
        self.assertContains(r, "Assign Checks to Integration", status_code=200)

    def test_it_checks_owner(self) -> None:
        # The channel does not belong to charlie, so this should come back
        # with 404 Not Found:
        url = f"/integrations/{self.channel.code}/checks/"
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_missing_channel(self) -> None:
        # Valid UUID but there is no channel for it:
        url = "/integrations/6837d6ec-fc08-4da5-a67f-08a9ed1ccf62/checks/"

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_it_handles_no_checks(self) -> None:
        self.check.delete()

        url = f"/integrations/{self.channel.code}/checks/"

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(url)
        self.assertContains(r, "there are currently no checks", status_code=200)

    def test_it_denies_a_superuser_outsider(self) -> None:
        self.charlie.is_superuser = True
        self.charlie.save()

        url = f"/integrations/{self.channel.code}/checks/"
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
