from __future__ import annotations

import json

from hc.api.models import Channel, WebhookSpec
from hc.test import BaseTestCase


class ChannelModelTestCase(BaseTestCase):
    def test_webhook_spec_handles_mixed(self) -> None:
        c = Channel(kind="webhook")
        c.value = json.dumps(
            {
                "method_down": "GET",
                "url_down": "http://example.org",
                "body_down": "",
                "headers_down": {"X-Status": "X"},
                "method_up": "POST",
                "url_up": "http://example.org/up/",
                "body_up": "hello world",
                "headers_up": {"X-Status": "OK"},
            }
        )

        self.assertEqual(
            c.down_webhook_spec,
            WebhookSpec(
                method="GET",
                url="http://example.org",
                body="",
                headers={"X-Status": "X"},
            ),
        )

        self.assertEqual(
            c.up_webhook_spec,
            WebhookSpec(
                method="POST",
                url="http://example.org/up/",
                body="hello world",
                headers={"X-Status": "OK"},
            ),
        )

    def test_slack_team_reads_team_name(self) -> None:
        c = Channel(kind="slack")
        c.value = json.dumps({"team_name": "Foo Team", "incoming_webhook": {}})
        self.assertEqual(c.slack_team, "Foo Team")

    def test_slack_team_reads_nested_team(self) -> None:
        c = Channel(kind="slack")
        c.value = json.dumps({"team": {"name": "Bar Team"}, "incoming_webhook": {}})
        self.assertEqual(c.slack_team, "Bar Team")

    def test_slack_team_handles_missing_team(self) -> None:
        c = Channel(kind="slack")
        c.value = json.dumps({"incoming_webhook": {"channel": "#foo"}})
        self.assertIsNone(c.slack_team)

    def test_slack_team_handles_plain_url_value(self) -> None:
        c = Channel(kind="slack", value="https://hooks.slack.com/services/foo")
        self.assertIsNone(c.slack_team)
