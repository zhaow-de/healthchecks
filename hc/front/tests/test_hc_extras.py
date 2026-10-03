from __future__ import annotations

from datetime import datetime, timezone
from datetime import timedelta as td
from unittest import TestCase
from urllib.parse import urlparse
from uuid import UUID

from django.test.utils import override_settings

from hc.api.models import Check
from hc.front.templatetags.hc_extras import (
    absolute_site_logo_url,
    break_underscore,
    first5,
    hc_duration,
    mask_key,
    mask_ro_key,
    mask_rw_key,
    site_hostname,
    sortchecks,
)


class HcExtrasTestCase(TestCase):
    def test_hc_duration_works(self) -> None:
        samples = [
            (60, "1 minute"),
            (120, "2 minutes"),
            (3600, "1 hour"),
            (3660, "1 hour 1 minute"),
            (86400, "1 day"),
            (604800, "1 week"),
            (2419200, "4 weeks"),
            (2592000, "30 days"),
            (3801600, "44 days"),
        ]

        for seconds, expected_result in samples:
            result = hc_duration(td(seconds=seconds))
            self.assertEqual(result, expected_result)


class AbsoluteSiteLogoUrlTestCase(TestCase):
    def _test(self, site_root: str, site_logo_url: str | None, expected_result: str) -> None:
        subpath = urlparse(site_root).path
        with override_settings(
            SITE_ROOT=site_root,
            SITE_LOGO_URL=site_logo_url,
            STATIC_URL=f"{subpath}/static/",
        ):
            self.assertEqual(absolute_site_logo_url(), expected_result)

    def test_it_handles_default(self) -> None:
        self._test(
            site_root="http://example.org",
            site_logo_url=None,
            expected_result="http://example.org/static/img/logo.png",
        )

    def test_it_handles_default_with_subpath(self) -> None:
        self._test(
            site_root="http://example.org/subpath",
            site_logo_url=None,
            expected_result="http://example.org/subpath/static/img/logo.png",
        )

    def test_it_handles_external_url(self) -> None:
        self._test(
            site_root="http://example.org",
            site_logo_url="http://example.com/foo.png",
            expected_result="http://example.com/foo.png",
        )

    def test_it_handles_leading_slash(self) -> None:
        self._test(
            site_root="http://example.org",
            site_logo_url="/foo/bar.png",
            expected_result="http://example.org/foo/bar.png",
        )

    def test_it_handles_leading_slash_with_subpath(self) -> None:
        self._test(
            site_root="http://example.org/subpath",
            site_logo_url="/foo/bar.png",
            expected_result="http://example.org/foo/bar.png",
        )


class SiteHostnameTestCase(TestCase):
    @override_settings(SITE_ROOT="http://example.org")
    def test_it_works(self) -> None:
        self.assertEqual(site_hostname(), "example.org")

    @override_settings(SITE_ROOT="http://example.org/foo")
    def test_it_handles_subpath(self) -> None:
        self.assertEqual(site_hostname(), "example.org")


class MaskKeyTestCase(TestCase):
    def test_it_works(self) -> None:
        self.assertEqual(mask_key("X" * 32), "XXXX" + "*" * 28)

    def test_it_handles_hashed_key(self) -> None:
        key = f"ABCDEFGH.{'0' * 64}"
        self.assertEqual(mask_rw_key(key), "hcw_ABCD" + "*" * 24)
        self.assertEqual(mask_ro_key(key), "hcr_ABCD" + "*" * 24)


class SortChecksTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.early = Check(name="early", last_ping=dt)
        self.late = Check(name="late", last_ping=dt + td(hours=1))
        self.never = Check(name="never")

    def test_it_sorts_by_last_ping(self) -> None:
        checks = sortchecks([self.never, self.late, self.early], "last_ping")
        # Checks that have never been pinged go last
        self.assertEqual(checks, [self.early, self.late, self.never])

    def test_it_sorts_by_last_ping_descending(self) -> None:
        checks = sortchecks([self.early, self.never, self.late], "-last_ping")
        self.assertEqual(checks, [self.never, self.late, self.early])

    def test_it_moves_down_checks_first(self) -> None:
        self.never.status = "down"
        checks = sortchecks([self.early, self.late, self.never], "last_ping")
        self.assertEqual(checks, [self.never, self.early, self.late])


class BreakUnderscoreTestCase(TestCase):
    def test_it_breaks_long_strings(self) -> None:
        s = "a_very_long_identifier_with_underscores"
        self.assertEqual(break_underscore(s), s.replace("_", "_\u200b"))

    def test_it_leaves_short_strings_alone(self) -> None:
        self.assertEqual(break_underscore("short_name"), "short_name")


class MiscFiltersTestCase(TestCase):
    def test_first5_works(self) -> None:
        rid = UUID("63832bb7-ddd5-4f2d-bf0a-cac885212963")
        self.assertEqual(first5(rid), "63832")
