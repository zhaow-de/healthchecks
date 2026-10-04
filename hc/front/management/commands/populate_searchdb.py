from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from hc.front.views import _replace_placeholders
from hc.lib.html import html2text


class Command(BaseCommand):
    help = "Rebuilds the docs search index in search.db"

    def handle(self, **options: Any) -> None:
        with closing(sqlite3.connect(settings.BASE_DIR / "search.db")) as con:
            con.execute("DROP TABLE IF EXISTS docs")
            con.execute(
                """CREATE VIRTUAL TABLE docs
                USING FTS5(slug, title, body, tokenize="porter unicode61")"""
            )

            docs_path = settings.BASE_DIR / "templates/docs"
            for doc_path in docs_path.glob("*.html-fragment"):
                slug = doc_path.stem
                print(f"Processing {slug}")

                html = _replace_placeholders(slug, doc_path.read_text(encoding="utf-8"))

                lines = html.split("\n")
                title = html2text(lines[0])
                text = html2text("\n".join(lines[1:]), skip_pre=True)

                con.execute("INSERT INTO docs VALUES (?, ?, ?)", (slug, title, text))

            con.commit()
