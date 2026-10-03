from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import TestCase
from django.test.utils import override_settings


class ServeDocTestCase(TestCase):
    def test_it_serves_introduction(self) -> None:
        r = self.client.get("/docs/")
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, "<strong>keeps silent</strong>")

    def test_it_serves_subpage(self) -> None:
        r = self.client.get("/docs/reliability_tips/")
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, "Pinging Reliability Tips")

    def test_it_handles_bad_url(self) -> None:
        r = self.client.get("/docs/does_not_exist/")
        self.assertEqual(r.status_code, 404)

    @patch("hc.front.views.settings.BASE_DIR")
    def test_it_rejects_bad_characters(self, mock_base_dir: Mock) -> None:
        self.client.get("/docs/NAUGHTY/")
        # URL dispatcher's slug filter lets the uppercase letters through,
        # but the view should still reject them, before any filesystem
        # operations
        self.assertEqual(len(mock_base_dir.mock_calls), 0)

    @override_settings(SITE_ROOT="http://example.org")
    def test_it_does_not_replace_placeholders_in_self_hosted_docs(self) -> None:
        r = self.client.get("/docs/self_hosted_configuration/")
        self.assertContains(r, '<a href="#SITE_ROOT">SITE_ROOT</a>', status_code=200)

    @override_settings(PING_BODY_LIMIT=1234)
    def test_it_formats_ping_body_limit_in_bytes(self) -> None:
        r = self.client.get("/docs/attaching_logs/")
        self.assertContains(r, "will log the first 1234 bytes", status_code=200)
        self.assertContains(r, "Handling More Than 1234 bytes of Logs")

    @override_settings(PING_BODY_LIMIT=20000)
    def test_it_formats_ping_body_limit_in_kilobytes(self) -> None:
        r = self.client.get("/docs/attaching_logs/")
        self.assertContains(r, "will log the first 20000 bytes", status_code=200)
        self.assertContains(r, "Handling More Than 20 kB of Logs")

    @override_settings(PING_BODY_LIMIT=None)
    def test_it_gives_request_size_cap_when_body_limit_is_none(self) -> None:
        r = self.client.get("/docs/attaching_logs/")
        self.assertContains(r, "will log the first 2621440 bytes", status_code=200)
        self.assertContains(r, "Handling More Than 2621440 bytes of Logs")
