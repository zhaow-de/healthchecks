import os
import sqlite3
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.db.backends.sqlite3.base import DatabaseWrapper
from django.test import SimpleTestCase, TestCase

import hc


def settings_module(local_settings: dict[str, Any] | None = None, **env: str) -> ModuleType:
    """hc/settings.py executed with env in place of the process's DB* variables, and
    with the names in local_settings, none by default, as hc/local_settings.py.
    """
    environ = {k: v for k, v in os.environ.items() if not k.startswith("DB")}
    stub = ModuleType("hc.local_settings")
    vars(stub).update(local_settings or {})
    local_path = settings.BASE_DIR / "hc" / "local_settings.py"
    exists = Path.exists

    # A name in the hc package, so that its import of .local_settings resolves to the stub
    spec = spec_from_file_location("hc.settings_under_test", settings.BASE_DIR / "hc" / "settings.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    with (
        patch.dict(os.environ, {**environ, **env}, clear=True),
        patch.dict(sys.modules, {"hc.local_settings": stub}),
        patch.object(hc, "local_settings", stub, create=True),
        patch.object(Path, "exists", autospec=True, side_effect=lambda p: p == local_path or exists(p)),
    ):
        spec.loader.exec_module(module)
    return module


def database_settings(**env: str) -> dict[str, Any]:
    """The default database's settings, as hc/settings.py builds them from env alone."""
    return settings_module(**env).DATABASES["default"]


class DatabaseSettingsTestCase(SimpleTestCase):
    def test_connections_persist_for_ten_minutes(self) -> None:
        for db in ("sqlite", "postgres"):
            with self.subTest(db=db):
                settings_dict = database_settings(DB=db)
                self.assertEqual(settings_dict["CONN_MAX_AGE"], 600)
                self.assertIs(settings_dict["CONN_HEALTH_CHECKS"], True)

    def test_db_conn_max_age_sets_the_lifetime(self) -> None:
        for db in ("sqlite", "postgres"):
            for value, expected in (("0", 0), ("60", 60), ("None", None)):
                with self.subTest(db=db, value=value):
                    settings_dict = database_settings(DB=db, DB_CONN_MAX_AGE=value)
                    self.assertEqual(settings_dict["CONN_MAX_AGE"], expected)


def change_counter(path: Path) -> int:
    """The file change counter of the database header. Rollback mode raises it on
    every commit, WAL mode on a commit that writes page 1, as every header change does.
    """
    return int.from_bytes(path.read_bytes()[24:28], "big")


# TestCase: under pytest-django a SimpleTestCase may not open the DatabaseWrapper connect() builds
@skipUnless(connection.vendor == "sqlite", "reads SQLite's pragmas")
class SqliteFileTestCase(TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "db.sqlite"

    def connect(self) -> DatabaseWrapper:
        settings_dict = {**connection.settings_dict, "NAME": str(self.path)}
        wrapper = DatabaseWrapper(settings_dict, alias="sqlite_file_test")
        self.addCleanup(wrapper.close)
        wrapper.ensure_connection()
        return wrapper

    def create(self, auto_vacuum: str, journal_mode: str) -> None:
        db = sqlite3.connect(self.path)
        db.execute(f"PRAGMA auto_vacuum = {auto_vacuum}")
        db.execute(f"PRAGMA journal_mode = {journal_mode}")
        db.execute("CREATE TABLE t (x INTEGER)")
        db.commit()
        db.close()

    def pragmas(self) -> tuple[int, str]:
        """auto_vacuum and journal_mode, read on a connection closed before returning."""
        db = sqlite3.connect(self.path)
        try:
            (auto_vacuum,) = db.execute("PRAGMA auto_vacuum").fetchone()
            (journal_mode,) = db.execute("PRAGMA journal_mode").fetchone()
        finally:
            db.close()
        return auto_vacuum, journal_mode

    def test_it_makes_a_new_file_incremental_and_wal(self) -> None:
        wrapper = self.connect()
        with wrapper.cursor() as cursor:
            cursor.execute("CREATE TABLE t (x INTEGER)")
        wrapper.close()

        self.assertEqual(self.pragmas(), (2, "wal"))

    def test_it_switches_an_existing_file_to_wal(self) -> None:
        for mode, value in (("NONE", 0), ("INCREMENTAL", 2)):
            with self.subTest(mode=mode):
                self.path.unlink(missing_ok=True)
                self.create(mode, "DELETE")

                self.connect().close()

                self.assertEqual(self.pragmas(), (value, "wal"))

    def test_it_does_not_write_to_a_file_in_wal_mode(self) -> None:
        for mode, value in (("NONE", 0), ("INCREMENTAL", 2)):
            with self.subTest(mode=mode):
                self.path.unlink(missing_ok=True)
                self.create(mode, "WAL")
                before = change_counter(self.path)

                wrapper = self.connect()
                with wrapper.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM t")
                wrapper.close()

                self.assertEqual(change_counter(self.path), before)
                self.assertEqual(self.pragmas(), (value, "wal"))

    def test_every_connection_syncs_normal_and_limits_the_wal(self) -> None:
        # A new file switches to WAL on its first connection, after init_command; an
        # existing one opens in WAL mode, where SQLite's default would be FULL
        for case in ("new file", "file in WAL mode"):
            with self.subTest(case=case):
                self.path.unlink(missing_ok=True)
                if case == "file in WAL mode":
                    self.create("INCREMENTAL", "WAL")

                wrapper = self.connect()
                values = []
                with wrapper.cursor() as cursor:
                    for pragma in ("journal_mode", "synchronous", "journal_size_limit", "busy_timeout"):
                        cursor.execute(f"PRAGMA {pragma}")
                        values.append(cursor.fetchone()[0])
                wrapper.close()

                # synchronous 1 is NORMAL
                self.assertEqual(values, ["wal", 1, 16777216, 5000])
