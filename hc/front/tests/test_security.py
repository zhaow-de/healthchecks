import os
import re
import time
from types import ModuleType
from typing import Any
from unittest.mock import patch

from django.conf import settings
from django.core import mail, signing
from django.core.mail import mail_admins
from django.template.utils import get_app_template_dirs
from django.test import SimpleTestCase
from django.test.utils import override_settings

from hc.api.models import Check
from hc.api.tests.test_database import settings_module
from hc.settings import site_root_settings
from hc.test import BaseTestCase

POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    f"connect-src 'self' {settings.SITE_ROOT}; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def without_env(name: str, local_settings: dict[str, Any] | None = None, **env: str) -> ModuleType:
    """hc/settings.py executed with env and local_settings, and without the variable name."""
    with patch.dict(os.environ):
        os.environ.pop(name, None)
        return settings_module(local_settings, **env)


class SecuritySettingsTestCase(SimpleTestCase):
    def test_cookies_are_secure_on_an_https_site_root(self) -> None:
        for site_root, secure in (("https://hc.example.org", True), ("http://localhost:8000", False)):
            with self.subTest(site_root=site_root):
                module = settings_module(SITE_ROOT=site_root)
                self.assertIs(module.SESSION_COOKIE_SECURE, secure)
                self.assertIs(module.CSRF_COOKIE_SECURE, secure)

    def test_csrf_trusts_the_origin_of_site_root(self) -> None:
        module = settings_module(SITE_ROOT="https://hc.example.org:8443/hc")
        self.assertEqual(module.CSRF_TRUSTED_ORIGINS, ["https://hc.example.org:8443"])

    def test_it_trusts_x_forwarded_proto_by_default(self) -> None:
        module = without_env("SECURE_PROXY_SSL_HEADER")
        self.assertEqual(module.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_an_empty_secure_proxy_ssl_header_leaves_django_default(self) -> None:
        module = settings_module(SECURE_PROXY_SSL_HEADER="")
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", vars(module))

    def test_the_policy_lets_the_console_ping_the_ping_endpoint(self) -> None:
        module = without_env("PING_ENDPOINT", SITE_ROOT="https://hc.example.org")
        self.assertEqual(module.SECURE_CSP["connect-src"], ["'self'", "https://hc.example.org"])

        module = settings_module(SITE_ROOT="https://hc.example.org", PING_ENDPOINT="https://ping.example.org/p/")
        self.assertEqual(module.SECURE_CSP["connect-src"], ["'self'", "https://ping.example.org"])

    def test_it_derives_the_site_root_settings(self) -> None:
        derived = site_root_settings("https://hc.example.org:8443/hc", "https://ping.example.org/p/", None)
        self.assertEqual(derived["PING_ENDPOINT"], "https://ping.example.org/p/")
        self.assertEqual(derived["LOGIN_URL"], "/hc/accounts/login/")
        self.assertEqual(derived["STATIC_URL"], "/hc/static/")
        self.assertEqual(derived["ALLOWED_HOSTS"], ["hc.example.org"])
        self.assertIs(derived["SESSION_COOKIE_SECURE"], True)
        self.assertIs(derived["CSRF_COOKIE_SECURE"], True)
        self.assertEqual(derived["CSRF_TRUSTED_ORIGINS"], ["https://hc.example.org:8443"])
        self.assertEqual(derived["SECURE_REDIRECT_EXEMPT"], [r"^hc/ping/", r"^hc/api/v3/status/?$"])
        self.assertEqual(derived["SECURE_CSP"]["connect-src"], ["'self'", "https://ping.example.org"])

        derived = site_root_settings("https://hc.example.org:8443/hc", None, "a.example.org,b.example.org")
        self.assertEqual(derived["PING_ENDPOINT"], "https://hc.example.org:8443/hc/ping/")
        self.assertEqual(derived["SECURE_CSP"]["connect-src"], ["'self'", "https://hc.example.org:8443"])
        self.assertEqual(derived["ALLOWED_HOSTS"], ["a.example.org", "b.example.org"])

    def test_a_site_root_in_local_settings_reaches_the_derived_settings(self) -> None:
        local = {"SITE_ROOT": "https://hc.example.org/hc/", "PING_ENDPOINT": "https://ping.example.org/p/"}
        module = settings_module(local, SITE_ROOT="http://localhost:8000", ALLOWED_HOSTS="")
        self.assertEqual(module.SITE_ROOT, "https://hc.example.org/hc")
        derived = site_root_settings("https://hc.example.org/hc", "https://ping.example.org/p/", None)
        self.assertEqual({name: getattr(module, name) for name in derived}, derived)

        # PING_ENDPOINT's default follows a SITE_ROOT set there too
        module = without_env("PING_ENDPOINT", local_settings={"SITE_ROOT": "https://hc.example.org"})
        self.assertEqual(module.PING_ENDPOINT, "https://hc.example.org/ping/")

    def test_a_derived_setting_in_local_settings_keeps_its_value(self) -> None:
        local = {"SITE_ROOT": "https://hc.example.org", "LOGIN_URL": "/login/", "SECURE_CSP": {}}
        module = settings_module(local)
        self.assertEqual(module.LOGIN_URL, "/login/")
        self.assertEqual(module.SECURE_CSP, {})
        self.assertIs(module.SESSION_COOKIE_SECURE, True)

    def test_hsts_is_off_unless_set(self) -> None:
        self.assertEqual(without_env("SECURE_HSTS_SECONDS").SECURE_HSTS_SECONDS, 0)
        module = settings_module(SECURE_HSTS_SECONDS="3600")
        self.assertEqual(module.SECURE_HSTS_SECONDS, 3600)

    def test_redirect_exemptions_follow_the_site_root_path(self) -> None:
        for site_root, prefix in (("https://hc.example.org", ""), ("https://example.org/hc", "hc/")):
            exempt = settings_module(SITE_ROOT=site_root).SECURE_REDIRECT_EXEMPT
            for path, expected in (
                ("ping/a0b1c2d3-0000-4000-8000-000000000000/fail", True),
                ("api/v3/status/", True),
                ("api/v3/status", True),
                ("api/v3/checks/", False),
                ("accounts/login/", False),
            ):
                with self.subTest(site_root=site_root, path=path):
                    matched = any(re.search(p, prefix + path) for p in exempt)
                    self.assertIs(matched, expected)

    def test_server_email_defaults_to_default_from_email(self) -> None:
        module = without_env("SERVER_EMAIL", DEFAULT_FROM_EMAIL="hc@example.org")
        self.assertEqual(module.SERVER_EMAIL, "hc@example.org")
        module = settings_module(SERVER_EMAIL="errors@example.org")
        self.assertEqual(module.SERVER_EMAIL, "errors@example.org")

    def test_a_default_from_email_in_local_settings_reaches_server_email(self) -> None:
        local = {"DEFAULT_FROM_EMAIL": "hc@example.org"}
        module = without_env("SERVER_EMAIL", local, DEFAULT_FROM_EMAIL="env@example.org")
        self.assertEqual(module.SERVER_EMAIL, "hc@example.org")

        module = without_env("SERVER_EMAIL", {**local, "SERVER_EMAIL": "errors@example.org"})
        self.assertEqual(module.SERVER_EMAIL, "errors@example.org")

    def test_a_ping_body_limit_above_the_upload_limit_raises_it(self) -> None:
        self.assertEqual(settings_module(PING_BODY_LIMIT="5000000").DATA_UPLOAD_MAX_MEMORY_SIZE, 5000000)
        self.assertNotIn("DATA_UPLOAD_MAX_MEMORY_SIZE", vars(settings_module(PING_BODY_LIMIT="2621440")))

        # A limit in local_settings.py raises it, or leaves Django's default
        module = settings_module({"PING_BODY_LIMIT": 5000000}, PING_BODY_LIMIT="10000")
        self.assertEqual(module.DATA_UPLOAD_MAX_MEMORY_SIZE, 5000000)
        module = settings_module({"PING_BODY_LIMIT": 2621440}, PING_BODY_LIMIT="5000000")
        self.assertNotIn("DATA_UPLOAD_MAX_MEMORY_SIZE", vars(module))

        module = settings_module({"PING_BODY_LIMIT": 5000000, "DATA_UPLOAD_MAX_MEMORY_SIZE": 6000000})
        self.assertEqual(module.DATA_UPLOAD_MAX_MEMORY_SIZE, 6000000)

    def test_gzip_comes_right_after_whitenoise(self) -> None:
        gzip = "django.middleware.gzip.GZipMiddleware"
        middleware = settings_module(USE_GZIP_MIDDLEWARE="True").MIDDLEWARE
        self.assertEqual(
            middleware[:3],
            ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", gzip],
        )
        self.assertNotIn(gzip, settings_module(USE_GZIP_MIDDLEWARE="False").MIDDLEWARE)


class InlineCodeTestCase(SimpleTestCase):
    def test_inline_scripts_and_styles_carry_the_nonce(self) -> None:
        # templates/, and the templates/ of each app under hc/: APP_DIRS renders pages from them
        hc_dir = settings.BASE_DIR / "hc"
        app_roots = [d for d in get_app_template_dirs("templates") if d.is_relative_to(hc_dir)]
        self.assertIn(hc_dir / "integrations" / "email" / "templates", app_roots)

        found: list[str] = []
        for root in [settings.BASE_DIR / "templates", *app_roots]:
            for path in sorted(root.rglob("*.html")):
                # Mail bodies, never served as pages
                if path.relative_to(root).parts[0] == "emails":
                    continue

                name = path.relative_to(settings.BASE_DIR)
                text = path.read_text()
                for tag in re.findall(r"<(?:script|style)\b[^>]*>", text):
                    # A type="data" block is data the browser does not run
                    if "src=" in tag or 'type="data"' in tag or "{% csp_nonce_attr %}" in tag:
                        continue
                    found.append(f"{name}: {tag}")

                found.extend(
                    f"{name}: {tag}" for tag in re.findall(r"<[a-zA-Z][^>]*>", text) if re.search(r"\s(style|on[a-z]+)=", tag)
                )

        self.assertEqual(found, [])


class ContentSecurityPolicyTestCase(BaseTestCase):
    def test_a_page_without_inline_code_gets_no_nonce(self) -> None:
        r = self.client.get("/accounts/login/")
        self.assertEqual(r.headers["Content-Security-Policy"], POLICY)

    def test_the_nonce_in_the_page_is_the_one_in_the_policy(self) -> None:
        # An aged signature makes the page submit its form by script
        with patch("django.core.signing.time") as mock_time:
            mock_time.time.return_value = time.time() - 301
            sig = signing.TimestampSigner(salt="reports").sign("alice")

        r = self.client.get(f"/accounts/unsubscribe_reports/{sig}/")
        policy = r.headers["Content-Security-Policy"]
        match = re.search(r"script-src 'self' 'nonce-([^']+)'", policy)
        assert match
        nonce = match.group(1)
        self.assertIn(f"style-src 'self' 'nonce-{nonce}'", policy)
        self.assertContains(r, f'<style nonce="{nonce}">')
        self.assertContains(r, f'<script nonce="{nonce}">')

    def test_the_admin_gets_its_nonce(self) -> None:
        self.alice.is_staff = self.alice.is_superuser = True
        self.alice.save()
        self.client.login(username="alice@example.org", password="password")

        r = self.client.get("/admin/api/flip/")
        match = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"])
        assert match
        self.assertContains(r, f'nonce="{match.group(1)}"')

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_the_redirect_to_https_leaves_pings_and_status(self) -> None:
        check = Check.objects.create(project=self.project)
        self.assertEqual(self.client.post(f"/ping/{check.code}/fail").status_code, 200)
        self.assertEqual(self.client.get("/api/v3/status/").status_code, 200)

        r = self.client.get("/accounts/login/")
        self.assertRedirects(r, "https://testserver/accounts/login/", 301, fetch_redirect_response=False)

    @override_settings(ADMINS=["admin@example.org"])
    def test_error_mails_leave_from_default_from_email(self) -> None:
        mail_admins("Subject", "Message")
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
