from __future__ import annotations

from hc.accounts.models import Project
from hc.api.models import Channel, Check
from hc.test import BaseTestCase


class TransferTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.other = Project.objects.create(owner=self.alice, name="Alices Other Project")
        self.check = Check.objects.create(project=self.other)
        self.url = f"/checks/{self.check.code}/transfer/"

    def test_it_serves_form(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Transfer to Another Project")
        self.assertContains(r, f'<option value="{self.project.code}">')
        self.assertContains(r, "<option disabled>Alices Other Project (current project)</option>")
        self.assertNotContains(r, str(self.charlies_project.code))

    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        payload = {"project": self.project.code}
        r = self.client.post(self.url, payload, follow=True)
        self.assertRedirects(r, f"/checks/{self.check.code}/details/")
        self.assertContains(r, "Check transferred successfully")

        check = Check.objects.get()
        self.assertEqual(check.project, self.project)

    def test_post_has_no_check_limit(self) -> None:
        Check.objects.bulk_create([Check(project=self.project) for _ in range(25)])

        self.client.login(username="alice@example.org", password="password")
        payload = {"project": self.project.code}
        r = self.client.post(self.url, payload)
        self.assertRedirects(r, f"/checks/{self.check.code}/details/")

        self.check.refresh_from_db()
        self.assertEqual(self.check.project, self.project)

    def test_it_reassigns_channels(self) -> None:
        alices_mail = Channel.objects.create(kind="email", project=self.project)

        other_mail = Channel.objects.create(kind="email", project=self.other)

        self.check.channel_set.add(other_mail)

        self.client.login(username="alice@example.org", password="password")
        payload = {"project": self.project.code}
        self.client.post(self.url, payload)

        # alices_mail should be the only assigned channel:
        self.assertEqual(self.check.channel_set.get(), alices_mail)

    def test_it_checks_check_ownership(self) -> None:
        self.client.login(username="charlie@example.org", password="password")

        # Charlie tries to transfer Alice's check into his project
        payload = {"project": self.charlies_project.code}
        r = self.client.post(self.url, payload)
        self.assertEqual(r.status_code, 404)

        self.check.refresh_from_db()
        self.assertEqual(self.check.project, self.other)

    def test_it_checks_project_access(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        # Alice tries to transfer her check into Charlie's project
        payload = {"project": self.charlies_project.code}
        r = self.client.post(self.url, payload)
        self.assertEqual(r.status_code, 404)

        self.check.refresh_from_db()
        self.assertEqual(self.check.project, self.other)

    def test_it_handles_bad_project_uuid(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        payload = {"project": "not-uuid"}
        r = self.client.post(self.url, payload)
        self.assertEqual(r.status_code, 400)
