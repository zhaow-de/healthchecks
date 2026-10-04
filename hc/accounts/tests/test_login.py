import time
from unittest.mock import patch
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib.auth.hashers import get_hasher
from django.contrib.auth.models import User
from django.core import mail, signing
from django.http import HttpResponse
from django.test.utils import override_settings

from hc.accounts import device
from hc.accounts.models import Credential, Project
from hc.api.models import Check, TokenBucket
from hc.test import BaseTestCase


class LoginTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.checks_url = f"/projects/{self.project.code}/checks/"
        self.good = {"action": "login", "email": "alice@example.org", "password": "password"}
        self.bad = {**self.good, "password": "wrong password"}

    def device_cookie(self) -> str:
        """Log in with the password and return the device cookie it set."""
        r = self.client.post("/accounts/login/", self.good)
        self.assertRedirects(r, self.checks_url)
        value = r.cookies[device.COOKIE_NAME].value
        # Client.logout() also drops the cookies
        self.client.logout()
        return value

    def post_counting_hashes(self, form: dict[str, str]) -> tuple[HttpResponse, int]:
        """POST the login form and count the password hasher's runs."""
        hasher = get_hasher()
        with patch.object(hasher, "encode", wraps=hasher.encode) as encode:
            r = self.client.post("/accounts/login/", form)
        return r, encode.call_count

    def drain_password_bucket(self) -> None:
        for _ in range(20):
            self.client.post("/accounts/login/", self.bad)

    def test_it_shows_form(self) -> None:
        r = self.client.get("/accounts/login/")
        self.assertContains(r, "magic-link-form")
        # It should not show validation errors yet
        self.assertNotContains(r, "This field is required")

    def test_lost_password_dialog_points_to_login_link(self) -> None:
        r = self.client.get("/accounts/login/")
        self.assertContains(r, "Log in using the <strong>Email Me a Link</strong> method.")
        self.assertNotContains(r, "changepassword")

    @override_settings(MAILERS={})
    def test_it_handles_no_smtp(self) -> None:
        r = self.client.get("/accounts/login/")
        self.assertNotContains(r, "magic-link-form")
        # The lost password dialog points to the shell, not to the missing login link
        self.assertNotContains(r, "Email Me a Link")
        self.assertContains(r, "<code>./manage.py changepassword</code>")

    def test_it_redirects_authenticated_get(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        r = self.client.get("/accounts/login/")
        self.assertRedirects(r, self.checks_url)

    @override_settings(SITE_ROOT="http://testserver", SESSION_COOKIE_SECURE=False)
    def test_it_sends_link(self) -> None:
        form = {"identity": "alice@example.org"}

        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login_link_sent/")

        self.assertEqual(r.cookies["auto-login"].value, "1")
        self.assertTrue(r.cookies["auto-login"]["httponly"])
        self.assertEqual(r.cookies["auto-login"]["samesite"], "Lax")
        self.assertFalse(r.cookies["auto-login"]["secure"])

        # And email should have been sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f"Log in to {settings.SITE_NAME}")
        self.assertEmailContainsHtml("http://testserver/static/img/logo.png")
        self.assertEmailContains("http://testserver/accounts/check_token/alice/")
        self.assertEmailNotContains("Need help getting started")

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_it_sets_secure_autologin_cookie(self) -> None:
        form = {"identity": "alice@example.org"}
        r = self.client.post("/accounts/login/", form)
        self.assertTrue(r.cookies["auto-login"]["secure"])

    def test_it_sends_link_with_next(self) -> None:
        form = {"identity": "alice@example.org"}

        r = self.client.post("/accounts/login/?next=" + self.channels_url, form)
        self.assertRedirects(r, "/accounts/login_link_sent/")

        # The check_token link should have a ?next= query parameter:
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        quoted_channels_url = quote_plus(self.channels_url)
        self.assertTrue(f"/?next={quoted_channels_url}" in body)

    def test_it_handles_unknown_email(self) -> None:
        form = {"identity": "surprise@example.org"}

        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login_link_sent/")
        # It should send the same response and cookies as in normal login
        self.assertEqual(r.cookies["auto-login"].value, "1")

        # There should be no sent emails.
        self.assertEqual(len(mail.outbox), 0)

    def test_link_request_hashes_once_for_any_email(self) -> None:
        for email in ("alice@example.org", "surprise@example.org"):
            r, hashes = self.post_counting_hashes({"identity": email})
            self.assertRedirects(r, "/accounts/login_link_sent/")
            self.assertEqual(hashes, 1, email)

    @override_settings(MAILERS={})
    def test_link_request_without_smtp_answers_any_email_alike(self) -> None:
        for email in ("alice@example.org", "surprise@example.org"):
            r, hashes = self.post_counting_hashes({"identity": email})
            self.assertRedirects(r, "/accounts/login_link_sent/")
            self.assertEqual(r.cookies["auto-login"].value, "1")
            self.assertEqual(hashes, 0, email)

        self.assertEqual(len(mail.outbox), 0)

    @override_settings(SECRET_KEY="test-secret")
    def test_it_rate_limits_emails(self) -> None:
        # d60d... is the SHA-1 of alice@example.org followed by test-secret
        obj = TokenBucket(value="em-d60db3b2343e713a4de3e92d4eb417e4f05f06ab")
        obj.tokens = 0
        obj.save()

        form = {"identity": "alice@example.org"}

        r = self.client.post("/accounts/login/", form)
        self.assertContains(r, "Too many attempts")

        # No email should have been sent
        self.assertEqual(len(mail.outbox), 0)

    def test_it_rate_limits_client_ips(self) -> None:
        obj = TokenBucket(value="auth-ip-127.0.0.1")
        obj.tokens = 0
        obj.save()

        form = {"identity": "alice@example.org"}

        r = self.client.post("/accounts/login/", form)
        self.assertContains(r, "Too many attempts")

        # No email should have been sent
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limiter_uses_x_forwarded_for(self) -> None:
        obj = TokenBucket(value="auth-ip-127.0.0.2")
        obj.tokens = 0
        obj.save()

        form = {"identity": "alice@example.org"}
        xff = "127.0.0.2:1234,127.0.0.3"
        r = self.client.post("/accounts/login/", form, HTTP_X_FORWARDED_FOR=xff)
        self.assertContains(r, "Too many attempts")

        # No email should have been sent
        self.assertEqual(len(mail.outbox), 0)

    def test_it_pops_bad_link_from_session(self) -> None:
        self.client.session["bad_link"] = True
        self.client.get("/accounts/login/")
        assert "bad_link" not in self.client.session

    def test_it_ignores_case(self) -> None:
        form = {"identity": "ALICE@EXAMPLE.ORG"}

        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login_link_sent/")

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.token)

    def test_it_handles_password(self) -> None:
        form = {"action": "login", "email": "alice@example.org", "password": "password"}

        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, self.checks_url)

    @override_settings(SECRET_KEY="test-secret")
    def test_it_rate_limits_password_attempts(self) -> None:
        # d60d... is the SHA-1 of alice@example.org followed by test-secret
        obj = TokenBucket(value="pw-d60db3b2343e713a4de3e92d4eb417e4f05f06ab")
        obj.tokens = 0
        obj.save()

        form = {"action": "login", "email": "alice@example.org", "password": "password"}

        r = self.client.post("/accounts/login/", form)
        self.assertContains(r, "Too many attempts")

    def test_it_handles_password_login_with_redirect(self) -> None:
        check = Check.objects.create(project=self.project)
        form = {"action": "login", "email": "alice@example.org", "password": "password"}
        samples = [self.channels_url, f"/checks/{check.code}/details/"]
        for s in samples:
            r = self.client.post(f"/accounts/login/?next={s}", form)
            self.assertRedirects(r, s)

    def test_it_handles_bad_next_parameter(self) -> None:
        form = {"action": "login", "email": "alice@example.org", "password": "password"}

        samples = [
            "/evil/",
            f"https://example.org/projects/{self.project.code}/checks/",
        ]

        for sample in samples:
            r = self.client.post("/accounts/login/?next=" + sample, form)
            self.assertRedirects(r, self.checks_url)

    def test_it_handles_wrong_password(self) -> None:
        form = {
            "action": "login",
            "email": "alice@example.org",
            "password": "wrong password",
        }

        r = self.client.post("/accounts/login/", form)
        self.assertContains(r, "Incorrect email or password")

    def test_wrong_password_hashes_once_for_any_email(self) -> None:
        for email in ("alice@example.org", "surprise@example.org"):
            r, hashes = self.post_counting_hashes({**self.bad, "email": email})
            self.assertContains(r, "Incorrect email or password")
            self.assertEqual(hashes, 1, email)

    def test_it_offers_no_sign_up(self) -> None:
        r = self.client.get("/accounts/login/")
        self.assertContains(r, "magic-link-form")
        self.assertNotContains(r, "signup-modal")
        self.assertNotContains(r, "Create Your Account")
        self.assertNotContains(r, "Sign Up")
        self.assertNotContains(r, "js/signup.js")

        r = self.client.get("/accounts/signup/csrf/")
        self.assertEqual(r.status_code, 404)

        r = self.client.post("/accounts/signup/", {"identity": "eve@example.org", "tz": "UTC"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(User.objects.filter(email="eve@example.org").exists())

    def test_it_redirects_to_webauthn_form(self) -> None:
        Credential.objects.create(user=self.alice, name="Alices Key")

        form = {"action": "login", "email": "alice@example.org", "password": "password"}
        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login/two_factor/", fetch_redirect_response=False)

        # It should not log the user in yet
        self.assertNotIn("_auth_user_id", self.client.session)

        # Instead, it should set 2fa_user in the session
        user_id, _email, _valid_until = self.client.session["2fa_user"]
        self.assertEqual(user_id, self.alice.id)

    def test_redirect_to_webauthn_form_preserves_next(self) -> None:
        Credential.objects.create(user=self.alice, name="Alices Key")

        form = {"action": "login", "email": "alice@example.org", "password": "password"}
        r = self.client.post(f"/accounts/login/?next={self.channels_url}", form)
        self.assertRedirects(
            r,
            f"/accounts/login/two_factor/?next={self.channels_url}",
            fetch_redirect_response=False,
        )

    def test_it_redirects_to_totp_form(self) -> None:
        self.profile.totp = "0" * 32
        self.profile.save()

        form = {"action": "login", "email": "alice@example.org", "password": "password"}
        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login/two_factor/totp/")
        self.assertNotIn(device.COOKIE_NAME, r.cookies)

        # It should not log the user in yet
        self.assertNotIn("_auth_user_id", self.client.session)

        # Instead, it should set 2fa_user in the session
        user_id, _email, _valid_until = self.client.session["2fa_user"]
        self.assertEqual(user_id, self.alice.id)

    def test_redirect_to_totp_form_preserves_next(self) -> None:
        self.profile.totp = "0" * 32
        self.profile.save()

        form = {"action": "login", "email": "alice@example.org", "password": "password"}
        r = self.client.post(f"/accounts/login/?next={self.channels_url}", form)
        self.assertRedirects(r, f"/accounts/login/two_factor/totp/?next={self.channels_url}")

    def test_it_handles_missing_profile(self) -> None:
        self.profile.delete()

        form = {"action": "login", "email": "alice@example.org", "password": "password"}

        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, self.checks_url)

    def test_it_redirects_to_index_if_user_has_several_projects(self) -> None:
        Project.objects.create(owner=self.alice, name="Second Project")
        form = {"action": "login", "email": "alice@example.org", "password": "password"}

        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/")

    @override_settings(SESSION_COOKIE_SECURE=False)
    def test_password_login_sets_device_cookie(self) -> None:
        r = self.client.post("/accounts/login/", self.good)
        self.assertRedirects(r, self.checks_url)

        cookie = r.cookies[device.COOKIE_NAME]
        payload = signing.loads(cookie.value, salt=device.SALT)
        self.assertEqual(payload["u"], self.alice.id)
        self.assertEqual(len(payload["n"]), 32)
        self.assertEqual(cookie["max-age"], 365 * 24 * 3600)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertFalse(cookie["secure"])

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_it_sets_secure_device_cookie(self) -> None:
        r = self.client.post("/accounts/login/", self.good)
        self.assertTrue(r.cookies[device.COOKIE_NAME]["secure"])

    def test_it_keeps_the_nonce_of_a_valid_device_cookie(self) -> None:
        first = self.device_cookie()

        self.client.cookies[device.COOKIE_NAME] = first
        r = self.client.post("/accounts/login/", self.good)
        second = r.cookies[device.COOKIE_NAME].value

        nonces = [signing.loads(v, salt=device.SALT)["n"] for v in (first, second)]
        self.assertEqual(nonces[0], nonces[1])

    def test_it_does_not_set_device_cookie_on_wrong_password(self) -> None:
        r = self.client.post("/accounts/login/", self.bad)
        self.assertNotIn(device.COOKIE_NAME, r.cookies)

    def test_wrong_passwords_lock_out_untrusted_browsers(self) -> None:
        self.drain_password_bucket()

        r = self.client.post("/accounts/login/", self.good)
        self.assertContains(r, "Too many attempts")

    def test_device_cookie_survives_drained_password_bucket(self) -> None:
        cookie = self.device_cookie()
        self.drain_password_bucket()

        self.client.cookies[device.COOKIE_NAME] = cookie
        r = self.client.post("/accounts/login/", self.good)
        self.assertRedirects(r, self.checks_url)

    def test_it_charges_trusted_device_its_own_password_bucket(self) -> None:
        cookie = self.device_cookie()
        n = signing.loads(cookie, salt=device.SALT)["n"]

        self.client.cookies[device.COOKIE_NAME] = cookie
        self.client.post("/accounts/login/", self.bad)

        obj = TokenBucket.objects.get(value__endswith=f"-{n}")
        self.assertTrue(obj.value.startswith("pw-"))
        self.assertLess(len(obj.value), 80)

    def test_tampered_device_cookie_is_untrusted(self) -> None:
        cookie = self.device_cookie()
        self.drain_password_bucket()

        # Swap in another nonce and keep the original signature
        _, timestamp, signature = cookie.rsplit(":", 2)
        forged = signing.dumps({"u": self.alice.id, "n": "b" * 32}, salt=device.SALT)
        payload = forged.rsplit(":", 2)[0]
        self.client.cookies[device.COOKIE_NAME] = f"{payload}:{timestamp}:{signature}"
        r = self.client.post("/accounts/login/", self.good)
        self.assertContains(r, "Too many attempts")

    def test_device_cookie_expires_after_a_year(self) -> None:
        self.drain_password_bucket()

        payload = {"u": self.alice.id, "n": "a" * 32}
        for days, trusted in ((364, True), (366, False)):
            issued = time.time() - days * 86400
            with patch("django.core.signing.time.time", return_value=issued):
                cookie = signing.dumps(payload, salt=device.SALT)

            self.client.cookies[device.COOKIE_NAME] = cookie
            r = self.client.post("/accounts/login/", self.good)
            if trusted:
                self.assertRedirects(r, self.checks_url)
                self.client.logout()
            else:
                self.assertContains(r, "Too many attempts")

    def test_device_cookie_of_another_user_is_untrusted(self) -> None:
        self.drain_password_bucket()

        payload = {"u": self.charlie.id, "n": "a" * 32}
        self.client.cookies[device.COOKIE_NAME] = signing.dumps(payload, salt=device.SALT)
        r = self.client.post("/accounts/login/", self.good)
        self.assertContains(r, "Too many attempts")

    @override_settings(SECRET_KEY="test-secret")
    def test_device_cookie_survives_drained_email_bucket(self) -> None:
        cookie = self.device_cookie()
        # d60d... is the SHA-1 of alice@example.org followed by test-secret
        TokenBucket.objects.create(value="em-d60db3b2343e713a4de3e92d4eb417e4f05f06ab", tokens=0)

        form = {"identity": "alice@example.org"}
        r = self.client.post("/accounts/login/", form)
        self.assertContains(r, "Too many attempts")
        self.assertEqual(len(mail.outbox), 0)

        self.client.cookies[device.COOKIE_NAME] = cookie
        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login_link_sent/")
        self.assertEqual(len(mail.outbox), 1)

    def test_trusted_device_skips_the_client_ip_bucket(self) -> None:
        cookie = self.device_cookie()
        TokenBucket.objects.create(value="auth-ip-127.0.0.1", tokens=0)

        self.client.cookies[device.COOKIE_NAME] = cookie
        form = {"identity": "alice@example.org"}
        r = self.client.post("/accounts/login/", form)
        self.assertRedirects(r, "/accounts/login_link_sent/")
        self.assertEqual(len(mail.outbox), 1)

    def test_wrong_passwords_for_other_emails_do_not_lock_out(self) -> None:
        for i in range(200):
            form = {"action": "login", "email": f"user{i}@example.org", "password": "wrong"}
            self.client.post("/accounts/login/", form)

        r = self.client.post("/accounts/login/", self.good)
        self.assertRedirects(r, self.checks_url)
