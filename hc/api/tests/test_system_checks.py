from django.core import checks
from django.test.utils import override_settings

from hc.api.apps import secret_key_check, settings_check
from hc.test import BaseTestCase

# 50 characters, the shortest key Django's rule accepts
STRONG_KEY = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN"


class SystemChecksCase(BaseTestCase):
    @override_settings(SITE_ROOT="example.com")
    def test_it_validates_site_root_syntax(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.W001"])

    @override_settings(SITE_ROOT="http://surprise.example.com")
    def test_it_checks_site_root_host_is_present_in_allowed_hosts(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.E002"])

    @override_settings(MAILERS={})
    def test_it_warns_about_missing_smtp_credentials(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.W002"])

    @override_settings(SECURE_PROXY_SSL_HEADER="abc")
    def test_it_checks_secure_proxy_ssl_header_tupleness(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.W005"])

    @override_settings(TIME_ZONE="Europe/Riga")
    def test_it_checks_time_zone_is_utc(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.E003"])

    def test_it_checks_trusted_proxy_hops(self) -> None:
        for value in (-1, None):
            with self.subTest(value=value), override_settings(TRUSTED_PROXY_HOPS=value):
                ids = [item.id for item in settings_check(None, None)]
                self.assertEqual(ids, ["hc.api.E005"])

        for value in (0, 1, 2):
            with self.subTest(value=value), override_settings(TRUSTED_PROXY_HOPS=value):
                self.assertEqual(settings_check(None, None), [])

    @override_settings(DEBUG=False)
    def test_it_refuses_a_weak_secret_key(self) -> None:
        for key in ("---", STRONG_KEY[:-1], "abcd" * 20, "django-insecure-" + STRONG_KEY):
            with self.subTest(key=key), override_settings(SECRET_KEY=key):
                ids = [item.id for item in secret_key_check(None, None)]
                self.assertEqual(ids, ["hc.api.E004"])

    @override_settings(DEBUG=False, SECRET_KEY=STRONG_KEY)
    def test_it_accepts_a_strong_secret_key(self) -> None:
        self.assertEqual(secret_key_check(None, None), [])

    @override_settings(DEBUG=True, SECRET_KEY="---")
    def test_it_allows_a_weak_secret_key_in_debug_mode(self) -> None:
        self.assertEqual(secret_key_check(None, None), [])

    @override_settings(DEBUG=False, SECRET_KEY="---")
    def test_it_registers_the_secret_key_check(self) -> None:
        errors = [item for item in checks.run_checks() if item.is_serious()]
        self.assertEqual([item.id for item in errors], ["hc.api.E004"])
