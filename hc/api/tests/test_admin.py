from __future__ import annotations

from datetime import timedelta as td

from django.contrib import admin
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils.timezone import now

from hc.api.admin import ChannelsAdmin, ChecksAdmin
from hc.api.models import Channel, Check, Notification, Ping
from hc.test import BaseTestCase

EMAIL_VALUE = '{"value": "alice@example.org", "up": true, "down": true}'


class ApiAdminTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project, tags="foo bar")

        self.alice.is_staff = True
        self.alice.is_superuser = True
        self.alice.save()

    def test_it_shows_channel_list_with_slack(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        Channel.objects.create(project=self.project, kind="slack", value="https://example.org")

        r = self.client.get("/admin/api/channel/")
        self.assertContains(r, '<span class="ic">slack</span>')

    def test_it_shows_checks(self) -> None:
        self.check.name = "Backup & Restore"
        self.check.save()
        charlies_check = Check.objects.create(project=self.charlies_project)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:api_check_changelist"))

        # The name and the tags, escaped
        self.assertContains(r, ">Backup &amp; Restore</a> <span>foo</span> <span>bar</span>")
        self.assertContains(r, self.check.get_absolute_url())
        self.assertContains(r, ">unnamed</a>")
        self.assertContains(r, charlies_check.get_absolute_url())

        # The owner's email and a link to the project
        project_url = self.project.get_absolute_url()
        self.assertContains(r, f'alice@example.org &rsaquo; <a href="{project_url}">Alices Project</a>')
        charlies_project_url = self.charlies_project.get_absolute_url()
        self.assertContains(r, f'charlie@example.org &rsaquo; <a href="{charlies_project_url}">Default</a>')

        # The default timeout of a simple check
        self.assertContains(r, '<td class="field-timeout_schedule">1 day</td>', html=True)

    def test_timeout_schedule_shows_simple_timeout(self) -> None:
        check = Check(kind="simple", timeout=td(hours=2, minutes=30))
        self.assertEqual(ChecksAdmin(Check, admin.site).timeout_schedule(check), "2 hours 30 minutes")

    def test_timeout_schedule_shows_schedule(self) -> None:
        checks_admin = ChecksAdmin(Check, admin.site)
        cron = Check(kind="cron", schedule="0 9 * * 1-5")
        self.assertEqual(checks_admin.timeout_schedule(cron), "0 9 * * 1-5")

        oncalendar = Check(kind="oncalendar", schedule="Mon *-*-* 09:00:00")
        self.assertEqual(checks_admin.timeout_schedule(oncalendar), "Mon *-*-* 09:00:00")

    def test_timeout_schedule_truncates_long_schedule(self) -> None:
        check = Check(kind="cron", schedule="0,5,10,15,20,25,30,35,40,45,50,55 * * * *")
        result = ChecksAdmin(Check, admin.site).timeout_schedule(check)
        self.assertEqual(result, "0,5,10,15,20,25,30,35,40,45,50...")

    def test_timeout_schedule_handles_unknown_kind(self) -> None:
        check = Check(kind="bogus")
        self.assertEqual(ChecksAdmin(Check, admin.site).timeout_schedule(check), "Unknown")

    def test_it_filters_pings(self) -> None:
        http_get = Ping.objects.create(owner=self.check, scheme="http", method="GET")
        https_post = Ping.objects.create(owner=self.check, scheme="https", method="POST", kind="start")
        http_fail = Ping.objects.create(owner=self.check, scheme="http", method="HEAD", kind="fail")

        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:api_ping_changelist")

        def ids(params: dict[str, str]) -> set[int]:
            r = self.client.get(url, params)
            self.assertEqual(r.status_code, 200)
            return {ping.id for ping in r.context["cl"].result_list}

        # The sidebar offers each filter's choices
        r = self.client.get(url)
        self.assertContains(r, '<a href="?scheme=https">HTTPS</a>', html=True)
        self.assertNotContains(r, "?scheme=email")
        self.assertContains(r, '<a href="?method=DELETE">DELETE</a>', html=True)
        self.assertContains(r, '<a href="?kind=fail">fail</a>', html=True)

        self.assertEqual(ids({}), {http_get.id, https_post.id, http_fail.id})
        self.assertEqual(ids({"scheme": "http"}), {http_get.id, http_fail.id})
        self.assertEqual(ids({"method": "POST"}), {https_post.id})
        self.assertEqual(ids({"kind": "fail"}), {http_fail.id})
        self.assertEqual(ids({"scheme": "https", "kind": "start"}), {https_post.id})

    def test_it_shows_channel_columns(self) -> None:
        long_value = "x" * 150
        Channel.objects.create(project=self.project, kind="email", value=EMAIL_VALUE)
        Channel.objects.create(project=self.project, kind="webhook", value=long_value, disabled=True)
        Channel.objects.create(project=self.project, kind="slack", last_error="Received status code 500")
        Channel.objects.create(
            project=self.charlies_project,
            kind="group",
            last_notify=now(),
            last_notify_duration=td(seconds=2.5),
        )

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:api_channel_changelist"))

        self.assertContains(r, "email (not verified)")
        self.assertContains(r, f'<td class="field-chopped_value">{"x" * 100}…</td>', html=True)
        self.assertContains(r, """<td class="field-status"><span class="d">Disabled</span></td>""", html=True)
        self.assertContains(r, """<td class="field-status"><span class="e">Error</span></td>""", html=True)
        self.assertContains(r, '<td class="field-status">OK</td>', html=True)
        self.assertContains(r, '<td class="field-time">2.5</td>', html=True)

        channels_url = reverse("hc-channels", args=[self.project.code])
        self.assertContains(r, f'alice@example.org &rsaquo; <a href="{channels_url}">Alices Project</a>')
        charlies_channels_url = reverse("hc-channels", args=[self.charlies_project.code])
        self.assertContains(r, f'charlie@example.org &rsaquo; <a href="{charlies_channels_url}">Default</a>')

    def test_channel_columns_for_new_channel(self) -> None:
        channel = Channel(project=self.project, kind="email", value=EMAIL_VALUE, email_verified=True)
        channels_admin = ChannelsAdmin(Channel, admin.site)
        self.assertEqual(channels_admin.transport(channel), '<span class="ic">email</span> &nbsp; email')
        self.assertEqual(channels_admin.chopped_value(channel), EMAIL_VALUE)
        self.assertEqual(channels_admin.status(channel), "-")
        self.assertIsNone(channels_admin.time(channel))

    def test_it_filters_channels_by_last_notify_duration(self) -> None:
        Channel.objects.create(project=self.project, kind="webhook")
        fast = Channel.objects.create(project=self.project, kind="webhook", last_notify_duration=td(seconds=2))
        slow = Channel.objects.create(project=self.project, kind="webhook", last_notify_duration=td(seconds=7))

        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:api_channel_changelist")

        # A channel that has never sent a notification has no duration and is left out
        r = self.client.get(url, {"last_notify_duration": "1"})
        self.assertEqual({c.id for c in r.context["cl"].result_list}, {fast.id, slow.id})

        r = self.client.get(url, {"last_notify_duration": "6"})
        self.assertEqual(list(r.context["cl"].result_list), [slow])

    def test_it_filters_channels_by_last_error(self) -> None:
        ok = Channel.objects.create(project=self.project, kind="webhook")
        failing = Channel.objects.create(project=self.project, kind="webhook", last_error="Connection timed out")

        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:api_channel_changelist")

        r = self.client.get(url, {"status": "ok"})
        self.assertEqual(list(r.context["cl"].result_list), [ok])

        r = self.client.get(url, {"status": "error"})
        self.assertEqual(list(r.context["cl"].result_list), [failing])

    def test_disable_action_disables_channels(self) -> None:
        c1 = Channel.objects.create(project=self.project, kind="webhook")
        c2 = Channel.objects.create(project=self.project, kind="slack")
        c3 = Channel.objects.create(project=self.project, kind="email")

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "disable", "_selected_action": [c1.id, c2.id]}
        r = self.client.post(reverse("admin:api_channel_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        messages = [str(m) for m in get_messages(r.wsgi_request)]
        self.assertEqual(messages, ["Disabled 2 channel(s)"])

        disabled = {c.id: c.disabled for c in Channel.objects.all()}
        self.assertEqual(disabled, {c1.id: True, c2.id: True, c3.id: False})

    def test_it_shows_and_filters_notifications(self) -> None:
        channel = Channel.objects.create(project=self.project, kind="webhook", value="<value>")
        ok = Notification.objects.create(owner=self.check, channel=channel, check_status="down")
        failed = Notification.objects.create(owner=self.check, channel=channel, check_status="up", error="Received status code 500")

        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:api_notification_changelist")

        r = self.client.get(url)
        self.assertContains(r, "<div>&lt;value&gt;</div>", count=2)
        channels_url = reverse("hc-channels", args=[self.project.code])
        self.assertContains(r, f'<div><a href="{channels_url}">Alices Project</a></div>', count=2)
        self.assertContains(r, '<a href="?status=ok">OK</a>', html=True)
        self.assertContains(r, '<a href="?status=error">Error</a>', html=True)

        r = self.client.get(url, {"status": "ok"})
        self.assertEqual(list(r.context["cl"].result_list), [ok])

        r = self.client.get(url, {"status": "error"})
        self.assertEqual(list(r.context["cl"].result_list), [failed])
