from unittest import TestCase
from zoneinfo import ZoneInfo

from hc.lib.tz import all_timezones, legacy_timezones


class TimezonesTestCase(TestCase):
    def test_every_zone_loads(self) -> None:
        for tz in all_timezones:
            with self.subTest(tz=tz):
                self.assertEqual(ZoneInfo(tz).key, tz)

    def test_it_lists_no_legacy_name(self) -> None:
        self.assertFalse(legacy_timezones.keys() & set(all_timezones))
        self.assertNotIn("Factory", all_timezones)

    def test_every_legacy_name_maps_to_a_listed_zone(self) -> None:
        for legacy, current in legacy_timezones.items():
            with self.subTest(legacy=legacy):
                self.assertIn(current, all_timezones)
