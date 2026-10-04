from django.contrib.auth.models import User

from hc.api.models import Check
from hc.test import BaseTestCase


class CloseAccountTestCase(BaseTestCase):
    def test_it_requires_sudo_mode(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        r = self.client.get("/accounts/close/")
        self.assertContains(r, "We have sent a confirmation code")

    def test_it_shows_confirmation_form(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.set_sudo_flag()

        r = self.client.get("/accounts/close/")
        self.assertContains(r, "Close Account?")
        self.assertContains(r, "1 project")
        self.assertContains(r, "0 checks")

    def test_it_works(self) -> None:
        Check.objects.create(project=self.project, tags="foo a-B_1  baz@")

        self.client.login(username="alice@example.org", password="password")
        self.set_sudo_flag()

        payload = {"confirmation": "alice@example.org"}
        r = self.client.post("/accounts/close/", payload, follow=True)
        self.assertRedirects(r, "/accounts/login/?account-closed=1")
        self.assertContains(r, "Account closed.")

        # Alice should be gone
        alices = User.objects.filter(username="alice")
        self.assertFalse(alices.exists())

        # Check should be gone
        self.assertFalse(Check.objects.exists())

    def test_it_requires_confirmation(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.set_sudo_flag()

        payload = {"confirmation": "incorrect"}
        r = self.client.post("/accounts/close/", payload)
        self.assertContains(r, "Close Account?")
        self.assertContains(r, "has-error")

        # Alice should be still present
        self.alice.refresh_from_db()
        self.profile.refresh_from_db()
