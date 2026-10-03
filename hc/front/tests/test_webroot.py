from __future__ import annotations

from django.test import TestCase


class WebrootTestCase(TestCase):
    def test_it_serves_the_favicon(self) -> None:
        r = self.client.get("/favicon.ico")
        self.assertEqual(r.status_code, 200)
        self.assertIn(r["Content-Type"], ("image/x-icon", "image/vnd.microsoft.icon"))

    def test_it_serves_the_apple_touch_icons(self) -> None:
        for path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r["Content-Type"], "image/png")

    def test_it_asks_every_crawler_to_stay_away(self) -> None:
        r = self.client.get("/robots.txt")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/plain"))
        body = b"".join(r.streaming_content).decode()
        self.assertEqual(body, "User-agent: *\nDisallow: /\n")
