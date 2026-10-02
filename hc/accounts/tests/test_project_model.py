from __future__ import annotations

from hc.api.models import Channel, Check
from hc.test import BaseTestCase


class ProjectModelTestCase(BaseTestCase):
    def test_it_handles_zero_broken_channels(self) -> None:
        Channel.objects.create(kind="webhook", last_error="", project=self.project)

        self.assertFalse(self.project.have_channel_issues())

    def test_it_handles_one_broken_channel(self) -> None:
        Channel.objects.create(kind="webhook", last_error="x", project=self.project)

        self.assertTrue(self.project.have_channel_issues())

    def test_it_handles_no_channels(self) -> None:
        # It's an issue if the project has no channels at all:
        self.assertTrue(self.project.have_channel_issues())

    def test_team_emails_work(self) -> None:
        self.assertEqual(self.project.team_emails(), ["alice@example.org", "bob@example.org"])

    def test_get_n_down_counts_down_checks(self) -> None:
        self.assertEqual(self.project.get_n_down(), 0)

        Check.objects.create(project=self.project, status="down")
        Check.objects.create(project=self.project, status="down")
        Check.objects.create(project=self.project, status="new")
        # A check in another project does not count
        Check.objects.create(project=self.charlies_project, status="down")

        self.assertEqual(self.project.get_n_down(), 2)

    def test_dashboard_url_requires_readonly_key(self) -> None:
        self.assertIsNone(self.project.dashboard_url())

    def test_dashboard_url_works(self) -> None:
        self.project.api_key_readonly = "R" * 32
        self.assertEqual(self.project.dashboard_url(), f"/tv/#{'R' * 32}=Alices%20Project")

    def test_get_absolute_url_works(self) -> None:
        self.assertEqual(self.project.get_absolute_url(), f"/projects/{self.project.code}/checks/")
