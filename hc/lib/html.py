from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


class TextOnlyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = True
        self.buf: list[str] = []
        self.skiplist = {"script", "style"}

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.skiplist:
            self.active = False

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skiplist:
            self.active = True

    def handle_data(self, data: str) -> None:
        if self.active and data:
            self.buf.append(data)

    def get_text(self) -> str:
        messy = "".join(self.buf)
        return " ".join(messy.split())


def html2text(html: str, skip_pre: bool = False) -> str:
    parser = TextOnlyParser()
    if skip_pre:
        parser.skiplist.add("pre")

    parser.feed(html)
    return parser.get_text()
