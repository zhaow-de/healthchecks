from hc.test import BaseTestCase


class LogoutTestCase(BaseTestCase):
    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        r = self.client.post("/accounts/logout/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_it_rejects_get(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        r = self.client.get("/accounts/logout/")
        self.assertEqual(r.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
