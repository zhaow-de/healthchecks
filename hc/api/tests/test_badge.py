from __future__ import annotations

from datetime import timedelta as td
from unittest.mock import patch

from django.conf import settings
from django.core.signing import base64_hmac
from django.test.utils import override_settings
from django.utils.timezone import now

from hc.api.models import Check
from hc.test import BaseTestCase


class BadgeTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project, tags="foo bar")

        sig = base64_hmac(str(self.project.badge_key), "foo", settings.SECRET_KEY, algorithm="sha1")
        sig = sig[:8]

        self.svg_url = f"/badge/{self.project.badge_key}/{sig}-2/foo.svg"
        self.json_url = f"/badge/{self.project.badge_key}/{sig}-2/foo.json"
        self.with_late_url = f"/badge/{self.project.badge_key}/{sig}/foo.json"
        self.shields_url = f"/badge/{self.project.badge_key}/{sig}-2/foo.shields"

    def test_it_rejects_bad_signature(self) -> None:
        r = self.client.get(f"/badge/{self.project.badge_key}/12345678/foo.svg")
        self.assertEqual(r.status_code, 404)

    def test_it_returns_svg(self) -> None:
        r = self.client.get(self.svg_url)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertIn("no-cache", r["Cache-Control"])
        self.assertContains(r, "#4c1")

    def test_it_rejects_bad_format(self) -> None:
        r = self.client.get(self.json_url + "foo")
        self.assertEqual(r.status_code, 404)

    def test_it_handles_options(self) -> None:
        r = self.client.options(self.svg_url)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

    def test_it_handles_new(self) -> None:
        doc = self.client.get(self.json_url).json()
        self.assertEqual(doc, {"status": "up", "total": 1, "grace": 0, "down": 0})

    def test_it_ignores_started_when_down(self) -> None:
        self.check.last_start = now()
        self.check.status = "down"
        self.check.save()

        doc = self.client.get(self.json_url).json()
        self.assertEqual(doc, {"status": "down", "total": 1, "grace": 0, "down": 1})

    def test_it_treats_late_as_up(self) -> None:
        self.check.last_ping = now() - td(days=1, minutes=10)
        self.check.status = "up"
        self.check.save()

        doc = self.client.get(self.json_url).json()
        self.assertEqual(doc, {"status": "up", "total": 1, "grace": 1, "down": 0})

    def test_it_handles_special_characters(self) -> None:
        self.check.tags = "db@dc1"
        self.check.save()

        sig = base64_hmac(str(self.project.badge_key), "db@dc1", settings.SECRET_KEY, algorithm="sha1")
        sig = sig[:8]
        url = f"/badge/{self.project.badge_key}/{sig}/db%2540dc1.svg"

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_late_mode_returns_late_status(self) -> None:
        self.check.last_ping = now() - td(days=1, minutes=10)
        self.check.status = "up"
        self.check.save()

        doc = self.client.get(self.with_late_url).json()
        self.assertEqual(doc, {"status": "late", "total": 1, "grace": 1, "down": 0})

    def test_late_mode_ignores_started_when_late(self) -> None:
        self.check.last_start = now()
        self.check.last_ping = now() - td(days=1, minutes=10)
        self.check.status = "up"
        self.check.save()

        doc = self.client.get(self.with_late_url).json()
        self.assertEqual(doc, {"status": "late", "total": 1, "grace": 1, "down": 0})

    def test_it_returns_shields_json(self) -> None:
        doc = self.client.get(self.shields_url).json()
        self.assertEqual(
            doc,
            {"schemaVersion": 1, "label": "foo", "message": "up", "color": "success"},
        )

    @override_settings(MASTER_BADGE_LABEL="Everything")
    def test_master_badge_counts_all_checks(self) -> None:
        # A check without tags still counts toward the "*" badge
        Check.objects.create(project=self.project, status="down")

        sig = base64_hmac(str(self.project.badge_key), "*", settings.SECRET_KEY, algorithm="sha1")[:8]

        doc = self.client.get(f"/badge/{self.project.badge_key}/{sig}-2.json").json()
        self.assertEqual(doc, {"status": "down", "total": 2, "grace": 0, "down": 1})

        doc = self.client.get(f"/badge/{self.project.badge_key}/{sig}-2.shields").json()
        self.assertEqual(doc["label"], "Everything")
        self.assertEqual(doc["message"], "down")

    def test_it_skips_checks_with_tag_as_substring(self) -> None:
        # "foobar" contains "foo" as a substring but not as a tag:
        Check.objects.create(project=self.project, tags="foobar", status="down")

        doc = self.client.get(self.json_url).json()
        self.assertEqual(doc, {"status": "up", "total": 1, "grace": 0, "down": 0})

    def test_svg_badge_stops_at_first_down_check(self) -> None:
        self.check.status = "down"
        self.check.save()
        Check.objects.create(project=self.project, tags="foo", status="down")

        with patch.object(Check, "get_status", autospec=True, side_effect=Check.get_status) as get_status:
            r = self.client.get(self.svg_url)

        self.assertEqual(r["Content-Type"], "image/svg+xml")
        self.assertContains(r, "#e05d44")
        self.assertNotContains(r, "#4c1")
        # Two checks match, the loop leaves after the first "down" one
        self.assertEqual(get_status.call_count, 1)
