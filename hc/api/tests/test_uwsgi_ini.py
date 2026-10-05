import re

from django.conf import settings
from django.core.management import get_commands
from django.test import SimpleTestCase

# uWSGI 2.0.31 accepts any other key in a cron2 value and ignores it
CRON2_KEYS = {"minute", "hour", "day", "month", "week", "unique", "harakiri", "legion"}


def uwsgi_options() -> list[tuple[str, str]]:
    """Return docker/uwsgi.ini's options as (key, value) pairs, in file order."""
    pairs = []
    for line in (settings.BASE_DIR / "docker" / "uwsgi.ini").read_text().splitlines():
        line = line.strip()
        # uWSGI reads ";" or "#" as a comment only at the start of a line
        if not line or line[0] in ";#[":
            continue
        key, _, value = line.partition("=")
        pairs.append((key.strip(), value.strip()))
    return pairs


class UwsgiIniTestCase(SimpleTestCase):
    def test_every_manage_py_command_exists(self) -> None:
        # uWSGI logs no exit status, so a cron job naming a missing command
        # would fail every day unseen
        names = []
        for key, value in uwsgi_options():
            if key in ("attach-daemon", "cron2") or key.startswith("hook-"):
                names.extend(re.findall(r"\./manage\.py\s+(\S+)", value))

        self.assertTrue(names)
        commands = get_commands()
        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, commands)

    def test_every_cron2_key_is_known(self) -> None:
        values = [value for key, value in uwsgi_options() if key == "cron2"]
        self.assertTrue(values)
        for value in values:
            spec, _, command = value.partition(" ")
            with self.subTest(value=value):
                self.assertTrue(command.strip())
                keys = {pair.partition("=")[0] for pair in spec.split(",")}
                self.assertLessEqual(keys, CRON2_KEYS)

    def test_it_prunes_daily(self) -> None:
        cron = ("cron2", "minute=17,hour=3,unique=1,harakiri=1800 ./manage.py prune --skip-checks")
        self.assertIn(cron, uwsgi_options())

    def test_limit_post_is_djangos_body_limit(self) -> None:
        option = ("limit-post", str(settings.DATA_UPLOAD_MAX_MEMORY_SIZE))
        self.assertIn(option, uwsgi_options())

    def test_it_leaves_static_files_to_whitenoise(self) -> None:
        keys = {key for key, _ in uwsgi_options()}
        self.assertFalse(keys & {"check-static", "static-map", "static-gzip-dir"})

    def test_it_migrates_as_an_asap_hook(self) -> None:
        self.assertIn(("hook-asap", "exec:./manage.py migrate"), uwsgi_options())
