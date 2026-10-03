from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test.utils import override_settings

from hc.test import BaseTestCase


@override_settings(SITE_NAME="Mychecks", PING_ENDPOINT="http://ping.example.com/")
class PopulateSearchDbTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base_dir = Path(tmp.name)
        self.docs = self.base_dir / "templates" / "docs"
        self.docs.mkdir(parents=True)

        self.write_doc(
            "introduction",
            "<h1>Introduction to SITE_NAME</h1>\n<p>Ping <code>PING_URL</code> regularly.</p>\n<pre>code_block_text</pre>",
        )

    def write_doc(self, slug: str, html: str) -> None:
        (self.docs / f"{slug}.html-fragment").write_text(html)

    def run_command(self) -> str:
        """Run populate_searchdb against the scratch BASE_DIR, return what it printed."""
        printed = StringIO()
        with override_settings(BASE_DIR=self.base_dir), redirect_stdout(printed):
            call_command("populate_searchdb", stdout=StringIO())
        return printed.getvalue()

    def query(self, sql: str, params: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
        with closing(sqlite3.connect(self.base_dir / "search.db")) as con:
            return con.execute(sql, params).fetchall()

    def test_it_indexes_title_and_body(self) -> None:
        printed = self.run_command()

        self.assertIn("Processing introduction", printed)
        rows = self.query("SELECT slug, title, body FROM docs")
        self.assertEqual(
            rows,
            [
                (
                    "introduction",
                    "Introduction to Mychecks",
                    # Placeholders are replaced and <pre> content is left out
                    "Ping http://ping.example.com/your-uuid-here regularly.",
                )
            ],
        )

    def test_it_supports_stemmed_full_text_search(self) -> None:
        self.run_command()

        # The porter tokenizer matches "pinging" to "Ping"
        rows = self.query("SELECT slug FROM docs WHERE docs MATCH ?", ("pinging",))
        self.assertEqual(rows, [("introduction",)])

    def test_it_keeps_placeholders_in_self_hosted_docs(self) -> None:
        self.write_doc("self_hosted", "<h1>Self-hosted SITE_NAME</h1>\n<p>Run it yourself.</p>")

        self.run_command()

        rows = self.query("SELECT title, body FROM docs WHERE slug = 'self_hosted'")
        self.assertEqual(rows, [("Self-hosted SITE_NAME", "Run it yourself.")])

    def test_it_replaces_existing_index(self) -> None:
        with closing(sqlite3.connect(self.base_dir / "search.db")) as con:
            con.execute("CREATE TABLE docs (slug, title, body)")
            con.execute("INSERT INTO docs VALUES ('stale', 'Stale', 'Stale body')")
            con.commit()

        self.run_command()
        self.run_command()

        rows = self.query("SELECT slug FROM docs")
        self.assertEqual(rows, [("introduction",)])
