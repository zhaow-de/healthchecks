import re
from datetime import timedelta as td
from uuid import UUID, uuid4

from django.core import mail
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils.timezone import now

from hc.api.models import Check, Flip, Ping
from hc.test import BaseTestCase


class PingTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.url = f"/ping/{self.check.code}"

    @override_settings(PING_BODY_LIMIT=10000)
    def test_it_works(self) -> None:
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "OK")
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(r.headers["Ping-Body-Limit"], "10000")
        self.assertEqual(r.headers["Access-Control-Expose-Headers"], "Ping-Body-Limit")

        self.check.refresh_from_db()
        self.assertEqual(self.check.n_pings, 1)
        self.assertEqual(self.check.status, "up")
        assert self.check.last_ping
        expected_aa = self.check.last_ping + td(days=1, hours=1)
        self.assertEqual(self.check.alert_after, expected_aa)

        ping = Ping.objects.get()
        self.assertEqual(ping.n, 1)
        self.assertEqual(ping.scheme, "http")
        self.assertEqual(ping.kind, None)
        self.assertEqual(ping.created, self.check.last_ping)
        self.assertIsNone(ping.exitstatus)

    def test_it_changes_status_of_paused_check(self) -> None:
        self.check.status = "paused"
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "up")

    def test_it_clears_last_start(self) -> None:
        self.check.last_start = now()
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.last_start, None)

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

    def test_it_handles_bad_uuid(self) -> None:
        r = self.client.get("/ping/not-uuid/")
        self.assertEqual(r.status_code, 404)

    def test_it_rejects_alternative_uuid_formats(self) -> None:
        # This uuid is missing separators. uuid.UUID() would accept it.
        r = self.client.get("/ping/07c2f54898504b27af5d6c9dc157ec02/")
        self.assertEqual(r.status_code, 404)

    def test_it_handles_missing_check(self) -> None:
        r = self.client.get("/ping/07c2f548-9850-4b27-af5d-6c9dc157ec02/")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.text, "not found")

    @override_settings(ADMINS=["admin@example.org"])
    def test_it_refuses_foreign_host_without_emailing_admins(self) -> None:
        r = self.client.get(self.url, HTTP_HOST="foreign.example.org")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(mail.outbox, [])

        self.check.refresh_from_db()
        self.assertEqual(self.check.n_pings, 0)

    def test_it_handles_120_char_ua(self) -> None:
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/44.0.2403.89 Safari/537.36"
        )

        r = self.client.get(self.url, HTTP_USER_AGENT=ua)
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.ua, ua)

    def test_it_truncates_long_ua(self) -> None:
        ua = "01234567890" * 30

        r = self.client.get(self.url, HTTP_USER_AGENT=ua)
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(len(ping.ua), 200)
        assert ua.startswith(ping.ua)

    def test_it_reads_forwarded_ip(self) -> None:
        ip = "1.1.1.1"
        r = self.client.get(self.url, HTTP_X_FORWARDED_FOR=ip)
        ping = Ping.objects.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ping.remote_addr, "1.1.1.1")

    def test_it_reads_forwarded_ipv6_ip(self) -> None:
        ip = "2001::1"
        r = self.client.get(self.url, HTTP_X_FORWARDED_FOR=ip)
        ping = Ping.objects.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ping.remote_addr, "2001::1")

    def test_it_reads_the_forwarded_ip_the_proxy_wrote(self) -> None:
        ip = "1.1.1.1, 2.2.2.2"
        r = self.client.get(
            self.url,
            HTTP_X_FORWARDED_FOR=ip,
            REMOTE_ADDR="3.3.3.3",
        )
        ping = Ping.objects.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ping.remote_addr, "2.2.2.2")

    def test_it_records_no_address_for_a_forwarded_entry_that_is_not_one(self) -> None:
        for ip in ("unknown", " 1.1.1.1x", "[2001:db8::1]:443:1", "x" * 60):
            with self.subTest(ip=ip):
                r = self.client.get(self.url, HTTP_X_FORWARDED_FOR=ip, REMOTE_ADDR="3.3.3.3")
                self.assertEqual(r.status_code, 200)
                self.assertIsNone(Ping.objects.latest("n").remote_addr)

        self.check.refresh_from_db()
        self.assertEqual(self.check.n_pings, 4)

    @override_settings(TRUSTED_PROXY_HOPS=0)
    def test_it_reads_remote_addr_with_no_trusted_proxy(self) -> None:
        r = self.client.get(self.url, HTTP_X_FORWARDED_FOR="1.1.1.1", REMOTE_ADDR="3.3.3.3")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ping.objects.get().remote_addr, "3.3.3.3")

    def test_it_handles_forwarded_ip_plus_port(self) -> None:
        ip = "1.1.1.1:1234"
        r = self.client.get(
            self.url,
            HTTP_X_FORWARDED_FOR=ip,
            REMOTE_ADDR="3.3.3.3",
        )
        ping = Ping.objects.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ping.remote_addr, "1.1.1.1")

    def test_it_handles_ipv4_mapped_ipv6_address(self) -> None:
        ip = "::ffff:1.1.1.1"
        r = self.client.get(
            self.url,
            HTTP_X_FORWARDED_FOR=ip,
            REMOTE_ADDR="3.3.3.3",
        )
        ping = Ping.objects.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ping.remote_addr, "1.1.1.1")

    def test_it_records_https_for_a_secure_request(self) -> None:
        r = self.client.get(self.url, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ping.objects.get().scheme, "https")

    def test_it_records_the_scheme_uwsgi_takes_from_x_forwarded_proto(self) -> None:
        # uWSGI copies X-Forwarded-Proto into wsgi.url_scheme as it is
        for value, expected in (("https", "https"), ("https, http", "http"), ("x" * 20, "http")):
            with self.subTest(value=value):
                r = self.client.get(self.url, **{"wsgi.url_scheme": value})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(Ping.objects.latest("n").scheme, expected)

    def test_it_ignores_x_forwarded_proto_django_does_not_trust(self) -> None:
        for value in ("https", "https, http"):
            with self.subTest(value=value):
                r = self.client.get(self.url, HTTP_X_FORWARDED_PROTO=value)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(Ping.objects.latest("n").scheme, "http")

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_it_reads_x_forwarded_proto_django_trusts(self) -> None:
        r = self.client.get(self.url, HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ping.objects.get().scheme, "https")

    def test_it_cuts_a_long_method_to_the_column(self) -> None:
        r = self.client.generic("VERYLONGMETHODNAME", self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ping.objects.get().method, "VERYLONGME")

    def test_it_answers_a_preflight_and_records_nothing(self) -> None:
        with self.assertNumQueries(0):
            r = self.client.options(
                self.url,
                HTTP_ORIGIN="https://example.org",
                HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
                HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type, x-run-id",
            )

        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(r.headers["Access-Control-Allow-Methods"], "GET, HEAD, POST, OPTIONS")
        self.assertEqual(r.headers["Access-Control-Allow-Headers"], "content-type, x-run-id")
        self.assertEqual(r.headers["Access-Control-Max-Age"], "600")
        self.assertFalse(Ping.objects.exists())

        self.check.refresh_from_db()
        self.assertEqual(self.check.n_pings, 0)
        self.assertEqual(self.check.status, "new")

    def test_preflight_allows_content_type_when_no_header_is_requested(self) -> None:
        r = self.client.options(self.url + "/fail", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.headers["Access-Control-Allow-Headers"], "Content-Type")

    def test_it_answers_a_preflight_to_an_unknown_check(self) -> None:
        with self.assertNumQueries(0):
            r = self.client.options("/ping/07c2f548-9850-4b27-af5d-6c9dc157ec02/")
        self.assertEqual(r.status_code, 204)

    def test_it_reads_the_check_once_and_writes_only_what_a_ping_changes(self) -> None:
        self.check.status = "up"
        self.check.save()

        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        # TestCase wraps each test in a transaction, so the atomic block shows as a savepoint
        sqls = [q["sql"] for q in ctx.captured_queries]
        self.assertEqual([sql.split()[0] for sql in sqls], ["SAVEPOINT", "SELECT", "UPDATE", "INSERT", "RELEASE"])
        update = sqls[2]
        set_clause = update.split(" SET ", 1)[1].split(" WHERE ", 1)[0]
        columns = set(re.findall(r'"(\w+)" = ', set_clause))
        expected = {
            "last_ping",
            "last_start",
            "last_start_rid",
            "last_duration",
            "status",
            "alert_after",
            "n_pings",
            "has_confirmation_link",
        }
        self.assertEqual(columns, expected)

    def test_a_session_cookie_neither_costs_queries_nor_varies_the_response(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Vary", r.headers)

        sqls = " ".join(q["sql"] for q in ctx.captured_queries)
        self.assertNotIn("django_session", sqls)
        self.assertNotIn("auth_user", sqls)

    def test_it_never_caches(self) -> None:
        r = self.client.get(self.url)
        assert "no-cache" in r["Cache-Control"]

    def test_it_updates_confirmation_flag(self) -> None:
        payload = "Please Confirm ..."
        r = self.client.post(self.url, data=payload, content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertTrue(self.check.has_confirmation_link)

    def test_fail_endpoint_works(self) -> None:
        r = self.client.get(self.url + "/fail")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "down")
        self.assertEqual(self.check.alert_after, None)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")

        flip = Flip.objects.get()
        self.assertEqual(flip.owner, self.check)
        self.assertEqual(flip.new_status, "down")
        self.assertEqual(flip.reason, "fail")

    def test_start_endpoint_works(self) -> None:
        last_ping = now() - td(hours=2)
        self.check.last_ping = last_ping
        self.check.save()

        r = self.client.get(self.url + "/start")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertTrue(self.check.last_start)
        self.assertEqual(self.check.last_ping, last_ping)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "start")

    def test_start_does_not_change_status_of_paused_check(self) -> None:
        self.check.status = "paused"
        self.check.save()

        r = self.client.get(self.url + "/start")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertTrue(self.check.last_start)
        self.assertEqual(self.check.status, "paused")

    def test_start_sets_last_start_rid(self) -> None:
        rid = uuid4()
        r = self.client.get(self.url + f"/start?rid={rid}")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertTrue(self.check.last_start)
        self.assertEqual(self.check.last_start_rid, rid)

    def test_it_accepts_uppercase_rid(self) -> None:
        rid = "04603D8B-EDF4-4E85-8F61-24BEDBCAAB59"
        r = self.client.get(self.url + f"/start?rid={rid}")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertTrue(self.check.last_start)
        self.assertEqual(self.check.last_start_rid, UUID(rid))

    def test_it_sets_last_duration(self) -> None:
        self.check.last_start = now() - td(seconds=10)
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        assert self.check.last_duration
        self.assertTrue(self.check.last_duration.total_seconds() >= 10)

    def test_it_does_not_update_last_ping_on_rid_mismatch(self) -> None:
        t = now() - td(seconds=10)
        self.check.last_start = t
        self.check.last_start_rid = uuid4()
        self.check.save()

        r = self.client.get(self.url + f"?rid={uuid4()}")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        # last_start should still be the same
        self.assertEqual(self.check.last_start, t)
        # last_duration should be not set
        self.assertIsNone(self.check.last_duration)

    def test_it_clears_last_ping_and_sets_last_duration_if_rid_matches(self) -> None:
        self.check.last_start = now() - td(seconds=10)
        self.check.last_start_rid = uuid4()
        self.check.save()

        r = self.client.get(self.url + f"?rid={self.check.last_start_rid}")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertIsNone(self.check.last_start)
        assert self.check.last_duration
        self.assertTrue(self.check.last_duration.total_seconds() >= 10)

    def test_it_clears_last_ping_if_rid_is_absent(self) -> None:
        self.check.last_start = now() - td(seconds=10)
        self.check.last_start_rid = uuid4()
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertIsNone(self.check.last_start)
        self.assertIsNone(self.check.last_duration)

    def test_it_clears_last_ping_on_failure(self) -> None:
        self.check.last_start = now() - td(seconds=10)
        self.check.last_start_rid = uuid4()
        self.check.save()

        r = self.client.get(self.url + f"/fail?rid={uuid4()}")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertIsNone(self.check.last_start)
        self.assertIsNone(self.check.last_duration)

    def test_it_requires_post(self) -> None:
        self.check.methods = "POST"
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "new")
        self.assertIsNone(self.check.last_ping)
        self.assertEqual(self.check.n_pings, 1)

        ping = Ping.objects.get()
        self.assertEqual(ping.scheme, "http")
        self.assertEqual(ping.kind, "ign")

    @override_settings(PING_BODY_LIMIT=5)
    def test_it_chops_long_body(self) -> None:
        r = self.client.post(self.url, "hello world", content_type="text/plain")
        self.assertEqual(r.headers["Ping-Body-Limit"], "5")

        ping = Ping.objects.get()
        self.assertEqual(ping.method, "POST")
        assert ping.body_raw
        self.assertEqual(bytes(ping.body_raw), b"hello")

    @override_settings(PING_BODY_LIMIT=None)
    def test_it_allows_unlimited_body(self) -> None:
        r = self.client.post(self.url, "A" * 20000, content_type="text/plain")
        self.assertNotIn("Ping-Body-Limit", r.headers)

        ping = Ping.objects.get()
        assert ping.body_raw
        self.assertEqual(len(ping.body_raw), 20000)

    def test_it_handles_manual_resume_flag(self) -> None:
        self.check.status = "paused"
        self.check.manual_resume = True
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "paused")
        self.assertEqual(self.check.n_pings, 1)

        ping = Ping.objects.get()
        self.assertEqual(ping.scheme, "http")
        self.assertEqual(ping.kind, "ign")

    def test_zero_exit_status_works(self) -> None:
        r = self.client.get(self.url + "/0")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "up")

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, None)
        self.assertEqual(ping.exitstatus, 0)

    def test_nonzero_exit_status_works(self) -> None:
        r = self.client.get(self.url + "/123")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "down")
        self.assertTrue(self.check.last_ping)
        self.assertIsNone(self.check.alert_after)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")
        self.assertEqual(ping.exitstatus, 123)

    def test_it_rejects_exit_status_over_255(self) -> None:
        r = self.client.get(self.url + "/256")
        self.assertEqual(r.status_code, 400)

    def test_it_accepts_bad_unicode(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        r = csrf_client.post(self.url, b"Hello \xe9 World", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.method, "POST")
        assert ping.body_raw
        self.assertEqual(bytes(ping.body_raw), b"Hello \xe9 World")

    def test_log_endpoint_works(self) -> None:
        r = self.client.post(self.url + "/log", "hello", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "new")
        self.assertIsNone(self.check.alert_after)
        self.assertFalse(self.check.last_ping)
        self.assertEqual(self.check.n_pings, 1)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "log")
        assert ping.body_raw
        self.assertEqual(bytes(ping.body_raw), b"hello")

        self.assertFalse(Flip.objects.exists())

    def test_it_saves_run_id(self) -> None:
        rid = uuid4()
        r = self.client.get(self.url + f"/start?rid={rid}")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.rid, rid)

    def test_it_handles_invalid_rid(self) -> None:
        samples = ["12345", "684e2e73-017e-465f-8149-d70b7c5aaa490"]
        for sample in samples:
            r = self.client.get(self.url + f"/start?rid={sample}")
            self.assertEqual(r.status_code, 400)

    def test_it_handles_success_filter_match(self) -> None:
        self.check.filter_http_body = True
        self.check.success_kw = "SUCCESS"
        self.check.save()

        r = self.client.post(self.url, data="SUCCESS!", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, None)

    def test_it_handles_success_filter_miss(self) -> None:
        self.check.filter_http_body = True
        self.check.success_kw = "SUCCESS"
        self.check.save()

        r = self.client.post(self.url, data="hello world", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "ign")

    def test_it_handles_failure_filter_match(self) -> None:
        self.check.filter_http_body = True
        self.check.failure_kw = "FAIL"
        self.check.save()

        r = self.client.post(self.url, data="FAIL!", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")

    def test_it_handles_failure_filter_miss(self) -> None:
        self.check.filter_http_body = True
        self.check.failure_kw = "FAIL"
        self.check.save()

        r = self.client.post(self.url, data="---", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "ign")

    def test_it_handles_start_filter_match(self) -> None:
        self.check.filter_http_body = True
        self.check.start_kw = "START"
        self.check.save()

        r = self.client.post(self.url, data="STARTING", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "start")

    def test_it_filters_body_that_is_not_utf8(self) -> None:
        self.check.filter_http_body = True
        self.check.failure_kw = "FAIL"
        self.check.save()

        r = self.client.post(self.url, data=b"\xff\xfe FAIL", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")
        assert ping.body_raw
        self.assertEqual(bytes(ping.body_raw), b"\xff\xfe FAIL")

    @override_settings(PING_BODY_LIMIT=8)
    def test_it_filters_body_cut_inside_a_multibyte_character(self) -> None:
        self.check.filter_http_body = True
        self.check.success_kw = "SUCCESS"
        self.check.save()

        body = "SUCCESS\u00e9".encode()
        r = self.client.post(self.url, data=body, content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, None)
        assert ping.body_raw
        self.assertEqual(bytes(ping.body_raw), body[:8])

    def test_manual_resume_takes_precedence_over_keywords(self) -> None:
        self.check.filter_http_body = True
        self.check.success_kw = "SUCCESS"
        self.check.manual_resume = True
        self.check.status = "paused"
        self.check.save()

        r = self.client.post(self.url, data="SUCCESS!", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "ign")

    def test_allowed_methods_takes_precedence_over_keywords(self) -> None:
        self.check.filter_http_body = True
        # This should normally trigger a failure
        # (because filtering is enabled but no keywords match the empty body)
        self.check.filter_default_fail = True
        # But this should take precedence and result in "ign" anyway
        self.check.methods = "POST"
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "ign")

    def test_it_handles_filter_default_fail(self) -> None:
        self.check.filter_http_body = True
        self.check.success_kw = "SUCCESS"
        self.check.filter_default_fail = True
        self.check.save()

        r = self.client.post(self.url, data="no keywords", content_type="text/plain")
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, "fail")

    def test_it_ignores_email_filters(self) -> None:
        self.check.filter_subject = True
        self.check.success_kw = "SUCCESS"
        self.check.filter_default_fail = True
        self.check.save()

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        ping = Ping.objects.get()
        self.assertEqual(ping.kind, None)
