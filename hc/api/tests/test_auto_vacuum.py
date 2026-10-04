import sqlite3
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.db import connection
from django.db.backends.sqlite3.base import DatabaseWrapper
from django.test import TestCase


def change_counter(path: Path) -> int:
    """The file change counter of the database header, which every committed write raises."""
    return int.from_bytes(path.read_bytes()[24:28], "big")


# TestCase: under pytest-django a SimpleTestCase may not open the DatabaseWrapper connect() builds
@skipUnless(connection.vendor == "sqlite", "reads SQLite's auto_vacuum")
class AutoVacuumTestCase(TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "db.sqlite"

    def connect(self) -> DatabaseWrapper:
        settings_dict = {**connection.settings_dict, "NAME": str(self.path)}
        wrapper = DatabaseWrapper(settings_dict, alias="auto_vacuum_test")
        self.addCleanup(wrapper.close)
        wrapper.ensure_connection()
        return wrapper

    def auto_vacuum(self) -> int:
        db = sqlite3.connect(self.path)
        self.addCleanup(db.close)
        return db.execute("PRAGMA auto_vacuum").fetchone()[0]

    def test_it_makes_a_new_file_incremental(self) -> None:
        wrapper = self.connect()
        with wrapper.cursor() as cursor:
            cursor.execute("CREATE TABLE t (x INTEGER)")
        wrapper.close()

        self.assertEqual(self.auto_vacuum(), 2)

    def test_it_does_not_write_to_an_existing_file(self) -> None:
        for mode, value in (("NONE", 0), ("INCREMENTAL", 2)):
            with self.subTest(mode=mode):
                self.path.unlink(missing_ok=True)
                db = sqlite3.connect(self.path)
                db.execute(f"PRAGMA auto_vacuum = {mode}")
                db.execute("CREATE TABLE t (x INTEGER)")
                db.commit()
                db.close()
                before = change_counter(self.path)

                wrapper = self.connect()
                with wrapper.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM t")
                wrapper.close()

                self.assertEqual(change_counter(self.path), before)
                self.assertEqual(self.auto_vacuum(), value)
