from unittest import skipUnless

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from hc.api.models import Check, Ping
from hc.test import BaseTestCase


class PingBySlugTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="foo", slug="foo")
        self.url = f"/ping/{self.project.ping_key}/foo"

    def test_it_works(self) -> None:
        r = self.client.get(self.url)
        self.assertEqual(r.content, b"OK")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, None)

    def test_post_works(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        r = csrf_client.post(self.url, "hello world", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.method, "POST")
        assert ping.body_raw
        self.assertEqual(bytes(ping.body_raw), b"hello world")

    def test_head_works(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        r = csrf_client.head(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ping.objects.count(), 1)

    def test_it_never_caches(self) -> None:
        r = self.client.get(self.url)
        assert "no-cache" in r["Cache-Control"]

    def test_fail_endpoint_works(self) -> None:
        r = self.client.get(self.url + "/fail")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")

    def test_start_endpoint_works(self) -> None:
        r = self.client.get(self.url + "/start")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "start")

    def test_zero_exit_status_works(self) -> None:
        r = self.client.get(self.url + "/0")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, None)
        self.assertEqual(ping.exitstatus, 0)

    def test_nonzero_exit_status_works(self) -> None:
        r = self.client.get(self.url + "/123")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")
        self.assertEqual(ping.exitstatus, 123)

    def test_it_answers_a_preflight_and_records_nothing(self) -> None:
        for url in (self.url, self.url + "/fail", "/ping/rrrrrrrrrrrrrrrrrrrrrr/foo", f"/ping/{self.project.ping_key}/FOO"):
            with self.subTest(url=url), self.assertNumQueries(0):
                r = self.client.options(url, HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
                self.assertEqual(r.status_code, 204)
                self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
                self.assertIn("no-cache", r.headers["Cache-Control"])

        self.assertFalse(Ping.objects.exists())

    @skipUnless(connection.features.has_select_for_update_of, "no row locks")
    def test_it_locks_the_check_and_not_its_project(self) -> None:
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        (select,) = [q["sql"] for q in ctx.captured_queries if q["sql"].startswith("SELECT")]
        self.assertTrue(select.endswith(' FOR NO KEY UPDATE OF "api_check"'), select)

    def test_it_handles_duplicates(self) -> None:
        # Another check with the same slug:
        Check.objects.create(project=self.project, name="foo", slug="foo")

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 409)

    def test_it_handles_wrong_ping_key(self) -> None:
        r = self.client.get("/ping/rrrrrrrrrrrrrrrrrrrrrr/foo")
        self.assertEqual(r.status_code, 404)

    def test_it_handles_unknown_slug(self) -> None:
        self.check.delete()
        for query in ("", "?create=1"):
            r = self.client.get(self.url + query)
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.content, b"not found")
        self.assertFalse(Check.objects.exists())

    def test_it_rejects_uppercase_slug(self) -> None:
        r = self.client.get(self.url + "FOO")
        self.assertEqual(r.content, b"invalid url format")
        self.assertEqual(r.status_code, 400)
