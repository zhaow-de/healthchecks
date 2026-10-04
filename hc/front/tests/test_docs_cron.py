from django.test.utils import override_settings

from hc.test import BaseTestCase


class DocsCronTestCase(BaseTestCase):
    @override_settings(SITE_NAME="Mychecks")
    def test_it_works(self) -> None:
        r = self.client.get("/docs/cron/")
        self.assertContains(r, "<h1>Cron Expression Syntax Cheatsheet</h1>", status_code=200)
        self.assertContains(r, "Cron Expression Syntax Cheatsheet - Mychecks")
