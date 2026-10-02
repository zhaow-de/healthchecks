from __future__ import annotations

from django.utils.timezone import now

from hc.api.models import Check
from hc.test import BaseTestCase


class IndexTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.c1 = Check.objects.create(project=self.project)
        self.c2 = Check.objects.create(project=self.project)
        self.c3 = Check.objects.create(project=self.project)

    def test_it_shows_projects(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/")

        self.assertContains(r, "Alices Project")
        self.assertContains(r, "3 checks")
        self.assertContains(r, "status ic-up")
        self.assertContains(r, "favicon.svg")

    def test_it_shows_overall_down_status(self) -> None:
        self.c1.status = "down"
        self.c1.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/")
        self.assertContains(r, "status ic-down")
        self.assertContains(r, "favicon_down.svg")

    def test_it_shows_started_spinner(self) -> None:
        self.c1.last_start = now()
        self.c1.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/")
        self.assertContains(r, 'class="spinner started"')

    def test_refresh_returns_project_statuses(self) -> None:
        self.c1.status = "down"
        self.c1.save()
        self.c2.last_start = now()
        self.c2.save()
        # Alice is not a member of Bob's project, so its check must not be summarized
        Check.objects.create(project=self.bobs_project, status="down")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/?refresh=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {str(self.project.code): {"status": "down", "started": True}})
