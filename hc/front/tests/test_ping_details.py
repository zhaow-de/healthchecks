from datetime import timedelta as td

from django.utils.timezone import now

from hc.api.models import Check, Ping
from hc.test import BaseTestCase

MIME_BODY = b"""Content-Type: multipart/alternative; boundary=bbb

--bbb
Content-Type: text/plain;charset=utf-8
Content-Transfer-Encoding: base64

aGVsbG8gd29ybGQ=

--bbb
"""


class PingDetailsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.url = f"/checks/{self.check.code}/last_ping/"

    def test_it_works(self) -> None:
        self.profile.tz = "Europe/Riga"
        self.profile.save()

        self.check.tz = "Europe/Berlin"
        self.check.kind = "cron"
        self.check.save()

        Ping.objects.create(owner=self.check, n=1, body_raw=b"this is body")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "this is body", status_code=200)

        # It should offer both the profile's tz and the check's tz
        # in the "Time received" field
        self.assertContains(r, "Europe/Riga")
        self.assertContains(r, "Europe/Berlin")

    def test_it_keeps_divs_out_of_paragraphs(self) -> None:
        Ping.objects.create(owner=self.check, n=1, body_raw=b"this is body")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        # A browser closes an open <p> at a <div>, and turns the </p> that
        # follows into an extra empty paragraph
        self.assertNotRegex(r.content.decode(), r"(?s)<p\b[^>]*>(?:(?!</p>).)*<div")

    def test_it_displays_duration(self) -> None:
        expected_duration = td(minutes=5)
        end_time = now()
        start_time = end_time - expected_duration

        Ping.objects.create(owner=self.check, created=start_time, n=1, kind="start")
        Ping.objects.create(owner=self.check, created=end_time, n=2, kind=None)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, "5 min 0 sec", status_code=200)

    def test_it_requires_logged_in_user(self) -> None:
        Ping.objects.create(owner=self.check, n=1)

        r = self.client.get(self.url)
        self.assertRedirects(r, "/accounts/login/?next=" + self.url)

    def test_it_shows_fail(self) -> None:
        Ping.objects.create(owner=self.check, n=1, kind="fail")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "/fail", status_code=200)

    def test_it_shows_start(self) -> None:
        Ping.objects.create(owner=self.check, n=1, kind="start")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(f"/checks/{self.check.code}/pings/1/")
        self.assertContains(r, "/start", status_code=200)

    def test_it_shows_log(self) -> None:
        Ping.objects.create(owner=self.check, n=1, kind="log")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(f"/checks/{self.check.code}/pings/1/")
        self.assertContains(r, "/log", status_code=200)

    def test_last_ping_lookup_excludes_log_ign_start(self) -> None:
        Ping.objects.create(owner=self.check, n=1)
        Ping.objects.create(owner=self.check, n=2, kind="log")
        Ping.objects.create(owner=self.check, n=3, kind="ign")
        Ping.objects.create(owner=self.check, n=4, kind="start")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "#1", status_code=200)

    def test_it_accepts_n(self) -> None:
        # remote_addr, scheme, method, ua, body, action, rid:
        self.check.ping("1.2.3.4", "http", "post", "tester", b"foo-123", "success", None)
        self.check.ping("1.2.3.4", "http", "post", "tester", b"bar-456", "success", None)

        self.client.login(username="alice@example.org", password="password")

        r = self.client.get(f"/checks/{self.check.code}/pings/1/")
        self.assertContains(r, "foo-123", status_code=200)

        r = self.client.get(f"/checks/{self.check.code}/pings/2/")
        self.assertContains(r, "bar-456", status_code=200)

    def test_it_checks_ownership(self) -> None:
        Ping.objects.create(owner=self.check, n=1)

        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_handles_missing_ping(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(f"/checks/{self.check.code}/pings/123/")
        self.assertContains(r, "No additional information is", status_code=200)

    def test_it_shows_nonzero_exitstatus(self) -> None:
        Ping.objects.create(owner=self.check, n=1, kind="fail", exitstatus=42)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "(failure, exit status 42)", status_code=200)

    def test_it_shows_zero_exitstatus(self) -> None:
        Ping.objects.create(owner=self.check, n=1, exitstatus=0)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "(exit status 0)", status_code=200)

    def test_it_shows_mime_body_verbatim(self) -> None:
        # An email-scheme row: its body is shown raw, not parsed as MIME
        Ping.objects.create(owner=self.check, n=1, scheme="email", body_raw=MIME_BODY)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        # aGVsbG8gd29ybGQ= is base64("hello world"): no MIME decoding happens
        self.assertContains(r, "aGVsbG8gd29ybGQ=", status_code=200)
        self.assertNotContains(r, "hello world")
        self.assertNotContains(r, "email-body-")

    def test_it_handles_utf8_body(self) -> None:
        Ping.objects.create(owner=self.check, n=1, body_raw="glāžšķūņu rūķīši".encode())

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, "<pre>glāžšķūņu rūķīši", status_code=200)

    def test_it_shows_ignored_nonzero_exitstatus(self) -> None:
        Ping.objects.create(owner=self.check, n=1, kind="ign", exitstatus=42)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(f"/checks/{self.check.code}/pings/1/")
        self.assertContains(r, "(ignored)", status_code=200)
