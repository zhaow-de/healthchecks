from __future__ import annotations

from datetime import timedelta as td

from django.utils.timezone import now

from hc.api.models import Check
from hc.test import BaseTestCase


class ProjectsMenuTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.url = "/projects/menu/"

    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, "Alices Project")
        self.assertContains(r, "status ic-up")

    def test_it_requires_logged_in_user(self) -> None:
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_it_shows_down_status(self) -> None:
        Check.objects.create(project=self.project, status="up", last_ping=now() - td(days=1, minutes=30))
        Check.objects.create(project=self.project, status="down")
        Check.objects.create(project=self.project, status="up", last_ping=now())

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "status ic-down", status_code=200)
        self.assertNotContains(r, "status ic-up")

    def test_it_shows_grace_status(self) -> None:
        Check.objects.create(project=self.project, status="up", last_ping=now())
        Check.objects.create(project=self.project, status="up", last_ping=now() - td(days=1, minutes=30))

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "status ic-grace", status_code=200)
        self.assertNotContains(r, "status ic-up")
