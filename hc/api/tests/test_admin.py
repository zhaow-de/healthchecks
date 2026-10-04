from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from hc.api.models import Channel, Check, Flip, Notification, Ping
from hc.test import BaseTestCase


class ApiAdminTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Backup & Restore")

        self.alice.is_staff = True
        self.alice.is_superuser = True
        self.alice.save()
        self.client.login(username="alice@example.org", password="password")

    def test_it_shows_checks(self) -> None:
        r = self.client.get(reverse("admin:api_check_changelist"))
        # The name, escaped
        self.assertContains(r, "Backup &amp; Restore")
        self.assertContains(r, '<td class="field-project nowrap">Alices Project</td>', html=True)

    def test_it_shows_pings(self) -> None:
        Ping.objects.create(owner=self.check, scheme="https", method="POST", kind="fail")

        r = self.client.get(reverse("admin:api_ping_changelist"))
        self.assertContains(r, '<td class="field-method">POST</td>', html=True)
        self.assertContains(r, '<td class="field-kind">fail</td>', html=True)

    def test_it_shows_channels(self) -> None:
        Channel.objects.create(project=self.project, kind="webhook", name="<Hook>", last_error="Timed out")

        r = self.client.get(reverse("admin:api_channel_changelist"))
        self.assertContains(r, "&lt;Hook&gt;")
        self.assertContains(r, '<td class="field-last_error">Timed out</td>', html=True)

    def test_it_shows_notifications(self) -> None:
        channel = Channel.objects.create(project=self.project, kind="webhook", name="Hook")
        Notification.objects.create(owner=self.check, channel=channel, check_status="down", error="Received status code 500")

        r = self.client.get(reverse("admin:api_notification_changelist"))
        self.assertContains(r, '<td class="field-channel nowrap">Hook</td>', html=True)
        self.assertContains(r, '<td class="field-error">Received status code 500</td>', html=True)

    def test_it_shows_flips(self) -> None:
        self.check.create_flip("down")

        r = self.client.get(reverse("admin:api_flip_changelist"))
        self.assertContains(r, '<td class="field-new_status">Down</td>', html=True)
        self.assertEqual(Flip.objects.count(), 1)

    def test_a_ping_or_notification_keeps_its_check(self) -> None:
        ping = Ping.objects.create(owner=self.check)
        channel = Channel.objects.create(project=self.project, kind="webhook")
        n = Notification.objects.create(owner=self.check, channel=channel, check_status="down")

        for url in (
            reverse("admin:api_ping_change", args=[ping.id]),
            reverse("admin:api_notification_change", args=[n.id]),
        ):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertContains(r, '<div class="readonly"><a href="')
                self.assertNotContains(r, 'name="owner"')

    def test_it_edits_relations_as_raw_ids(self) -> None:
        channel = Channel.objects.create(project=self.project, kind="webhook")
        n = Notification.objects.create(owner=self.check, channel=channel, check_status="down")
        self.check.create_flip("down")
        flip = Flip.objects.get()

        for url, field, widget in (
            (reverse("admin:api_check_change", args=[self.check.id]), "project", "vForeignKeyRawIdAdminField"),
            (reverse("admin:api_channel_change", args=[channel.id]), "project", "vForeignKeyRawIdAdminField"),
            (reverse("admin:api_channel_change", args=[channel.id]), "checks", "vManyToManyRawIdAdminField"),
            (reverse("admin:api_notification_change", args=[n.id]), "channel", "vForeignKeyRawIdAdminField"),
            (reverse("admin:api_flip_change", args=[flip.id]), "owner", "vForeignKeyRawIdAdminField"),
        ):
            with self.subTest(url=url, field=field):
                r = self.client.get(url)
                self.assertContains(r, f'name="{field}"')
                self.assertContains(r, widget)

    def test_changelists_count_their_rows_once(self) -> None:
        Ping.objects.create(owner=self.check, body_raw=b"x" * 1000)
        channel = Channel.objects.create(project=self.project, kind="webhook")
        Notification.objects.create(owner=self.check, channel=channel, check_status="down")
        self.check.create_flip("down")

        for name, table in (("ping", "api_ping"), ("notification", "api_notification"), ("flip", "api_flip")):
            with self.subTest(name=name), CaptureQueriesContext(connection) as ctx:
                r = self.client.get(reverse(f"admin:api_{name}_changelist"))
                self.assertEqual(r.status_code, 200)
                counts = [q["sql"] for q in ctx.captured_queries if "COUNT(" in q["sql"] and table in q["sql"]]
                self.assertEqual(len(counts), 1)

    def test_ping_changelist_reads_no_body(self) -> None:
        Ping.objects.create(owner=self.check, body_raw=b"x" * 1000)

        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(reverse("admin:api_ping_changelist"))
        self.assertEqual(r.status_code, 200)
        selects = [q["sql"] for q in ctx.captured_queries if '"api_ping"."id"' in q["sql"]]
        self.assertTrue(selects)
        for sql in selects:
            self.assertNotIn("body_raw", sql)

    def test_editing_a_ping_keeps_its_body(self) -> None:
        ping = Ping.objects.create(owner=self.check, n=1, body_raw=b"hello")

        form = {
            "n": "1",
            "created_0": "2026-01-02",
            "created_1": "03:04:05",
            "scheme": "http",
            "method": "PUT",
            "exitstatus": "0",
            "rid": "a0b1c2d3-0000-4000-8000-000000000000",
        }
        r = self.client.post(reverse("admin:api_ping_change", args=[ping.id]), form)
        self.assertEqual(r.status_code, 302)

        ping.refresh_from_db()
        self.assertEqual(ping.method, "PUT")
        self.assertEqual(ping.get_body_bytes(), b"hello")
