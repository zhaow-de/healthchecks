from __future__ import annotations

import importlib

from django.test.utils import override_settings
from django.urls import clear_url_caches, reverse

import hc.urls
from hc.test import BaseTestCase


class SiteRootPrefixTestCase(BaseTestCase):
    def _reload_urlconf(self) -> None:
        importlib.reload(hc.urls)
        clear_url_caches()

    @override_settings(SITE_ROOT="http://testserver/hc")
    def test_it_prefixes_routes_with_site_root_path(self) -> None:
        # hc.urls reads SITE_ROOT at import time; the cleanup reloads it again
        # after override_settings has restored the original SITE_ROOT
        self.addCleanup(self._reload_urlconf)
        self._reload_urlconf()

        self.assertEqual(hc.urls.prefix, "hc/")
        self.assertEqual(reverse("hc-docs"), "/hc/docs/")

        r = self.client.get("/hc/docs/")
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/docs/")
        self.assertEqual(r.status_code, 404)
