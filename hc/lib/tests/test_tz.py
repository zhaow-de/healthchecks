import importlib
import tempfile
import zoneinfo
from importlib.resources import files
from pathlib import Path
from unittest import TestCase
from zoneinfo import ZoneInfo

import hc.lib.tz
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

    def test_it_ignores_the_host_zoneinfo(self) -> None:
        # A host zone file absent from the tzdata package, as Debian's "localtime" is
        host = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (host / "Hc").mkdir()
        (host / "Hc" / "Extra").write_bytes(files("tzdata").joinpath("zoneinfo", "Etc", "UTC").read_bytes())

        self.addCleanup(importlib.reload, hc.lib.tz)
        self.addCleanup(zoneinfo.reset_tzpath)
        zoneinfo.reset_tzpath(to=[str(host)])
        self.assertIn("Hc/Extra", zoneinfo.available_timezones())

        reloaded = importlib.reload(hc.lib.tz)
        self.assertNotIn("Hc/Extra", reloaded.all_timezones)
        self.assertEqual(reloaded.all_timezones, all_timezones)
