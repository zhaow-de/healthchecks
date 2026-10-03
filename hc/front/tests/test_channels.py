from __future__ import annotations

import json

from hc.api.models import Channel
from hc.test import BaseTestCase


class ChannelsTestCase(BaseTestCase):
    def test_it_formats_complex_slack_value(self) -> None:
        ch = Channel(kind="slack", project=self.project)
        ch.value = json.dumps(
            {
                "ok": True,
                "team_name": "foo-team",
                "incoming_webhook": {"url": "http://example.org", "channel": "#bar"},
            }
        )
        ch.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertContains(r, "foo-team", status_code=200)
        self.assertContains(r, "#bar")

    def test_it_shows_webhook_post_data(self) -> None:
        ch = Channel(kind="webhook", project=self.project)
        ch.value = json.dumps(
            {
                "method_down": "POST",
                "url_down": "http://down.example.com",
                "body_down": "foobar",
                "headers_down": {},
                "method_up": "GET",
                "url_up": "http://up.example.com",
                "body_up": "",
                "headers_up": {},
            }
        )
        ch.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)

        self.assertEqual(r.status_code, 200)
        # These are inside a modal, which the channel's name opens:
        self.assertContains(r, f'data-bs-target="#name-{ch.code}"')
        self.assertContains(r, f'id="name-{ch.code}"')
        self.assertContains(r, "http://down.example.com")
        self.assertContains(r, "http://up.example.com")
        self.assertContains(r, "foobar")

    def test_it_shows_unconfirmed_email(self) -> None:
        channel = Channel(project=self.project, kind="email")
        channel.value = "alice@example.org"
        channel.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Unconfirmed")

    def test_it_shows_down_only_note_for_email(self) -> None:
        channel = Channel(project=self.project, kind="email")
        channel.value = json.dumps({"value": "alice@example.org", "up": False, "down": True})
        channel.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "(down only)")

    def test_it_shows_up_only_note_for_email(self) -> None:
        channel = Channel(project=self.project, kind="email")
        channel.value = json.dumps({"value": "alice@example.org", "up": True, "down": False})
        channel.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "(up only)")

    def test_it_shows_channel_issues_indicator(self) -> None:
        Channel.objects.create(
            kind="slack",
            project=self.project,
            last_error="x",
            value="https://example.org",
        )

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertContains(r, "broken-channels", status_code=200)

    def test_it_hides_actions_from_readonly_users(self) -> None:
        self.bobs_membership.role = "r"
        self.bobs_membership.save()

        ch = Channel.objects.create(project=self.project, kind="webhook", value="{}")

        self.client.login(username="bob@example.org", password="password")
        r = self.client.get(self.channels_url)

        self.assertNotContains(r, "Add Integration", status_code=200)
        self.assertNotContains(r, "ic-delete")
        self.assertNotContains(r, f"/integrations/{ch.code}/edit/")
        # The name modals are not rendered, so nothing may toggle them
        self.assertNotContains(r, f'id="name-{ch.code}"')
        self.assertNotContains(r, f'data-bs-target="#name-{ch.code}"')

    def test_it_shows_disabled_note(self) -> None:
        ch = Channel(kind="slack", project=self.project)
        ch.value = "https://example.org"
        ch.disabled = True
        ch.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertContains(r, '<span class="badge text-bg-danger">Disabled</span>', status_code=200)

    def test_it_shows_fix_button_for_disabled_email(self) -> None:
        ch = Channel(kind="email", project=self.project)
        ch.value = "bob@example.org"
        ch.disabled = True
        ch.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.channels_url)
        self.assertContains(r, "Fix&hellip;", status_code=200)
