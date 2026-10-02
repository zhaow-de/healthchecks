from __future__ import annotations

from hc.test import BaseTestCase


class AppearanceTestCase(BaseTestCase):
    url = "/accounts/profile/appearance/"

    def test_it_shows_form(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        r = self.client.get(self.url)
        self.assertContains(r, 'id="theme-dark"', status_code=200)

    def test_it_requires_login(self) -> None:
        r = self.client.get(self.url)
        self.assertRedirects(r, f"/accounts/login/?next={self.url}")

    def test_it_saves_theme(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        for theme in ("dark", "system", ""):
            r = self.client.post(self.url, {"theme": theme})
            self.assertEqual(r.status_code, 200)

            self.profile.refresh_from_db()
            self.assertEqual(self.profile.theme, theme)

    def test_it_ignores_unknown_theme(self) -> None:
        self.profile.theme = "dark"
        self.profile.save()

        self.client.login(username="alice@example.org", password="password")

        r = self.client.post(self.url, {"theme": "surprise"})
        self.assertEqual(r.status_code, 200)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.theme, "dark")
