from __future__ import annotations

import importlib

from django.test.utils import override_settings
from django.urls import clear_url_caches

import hc.urls
from hc.test import BaseTestCase


class AddPrometheusTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = f"/projects/{self.project.code}/add_prometheus/"

    def test_instructions_work(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Prometheus")
        self.assertContains(r, f"metrics_path: /projects/{self.project.code}/metrics/<strong>")

    def test_it_checks_project_access(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    @override_settings(PROMETHEUS_ENABLED=False)
    def test_it_handles_disabled_integration(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def _reload_urlconf(self) -> None:
        importlib.reload(hc.urls)
        clear_url_caches()

    @override_settings(SITE_ROOT="http://testserver/hc")
    def test_metrics_path_carries_site_root_path(self) -> None:
        # hc.urls reads SITE_ROOT at import time; the cleanup reloads it again
        # after override_settings has restored the original SITE_ROOT
        self.addCleanup(self._reload_urlconf)
        self._reload_urlconf()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(f"/hc/projects/{self.project.code}/add_prometheus/")
        self.assertContains(r, f"metrics_path: /hc/projects/{self.project.code}/metrics/<strong>")
