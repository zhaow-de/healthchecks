from django.contrib.auth.models import User

from hc.accounts.models import Profile
from hc.test import BaseTestCase


class ProfileMiddlewareTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ned = User(username="ned", email="ned@example.org")
        self.ned.set_password("password")
        self.ned.save()
        self.client.login(username="ned@example.org", password="password")

    def test_it_creates_a_missing_profile_for_a_view_that_reads_it(self) -> None:
        r = self.client.get("/accounts/profile/")
        self.assertEqual(r.status_code, 200)

        self.assertTrue(Profile.objects.filter(user=self.ned).exists())

    def test_it_loads_no_profile_for_a_view_that_does_not_read_it(self) -> None:
        r = self.client.get("/docs/")
        self.assertEqual(r.status_code, 200)

        self.assertFalse(Profile.objects.filter(user=self.ned).exists())
