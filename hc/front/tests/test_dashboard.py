from __future__ import annotations

from django.test.utils import override_settings

from hc.test import BaseTestCase


class DashboardTestCase(BaseTestCase):
    @override_settings(SITE_NAME="Mychecks")
    def test_it_works_without_login(self) -> None:
        r = self.client.get("/tv/")
        self.assertContains(r, "<title>Mychecks</title>", status_code=200)
        self.assertContains(r, '<div id="panel"></div>')
        self.assertContains(r, 'httpRequest.open("GET", "/api/v3/checks/");')
