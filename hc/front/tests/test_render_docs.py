from __future__ import annotations

import tempfile
from contextlib import redirect_stdout
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test.utils import override_settings

from hc.test import BaseTestCase

MARKDOWN = """# Getting Started

Some *emphasis* here.

```python
print("hello")
```

| Name | Value |
|------|-------|
| a    | 1     |

Grace Time
:   How long to wait.

## Anchored {: #anchored }
"""


class RenderDocsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base_dir = Path(tmp.name)
        self.docs = self.base_dir / "templates" / "docs"
        self.docs.mkdir(parents=True)

    def run_command(self) -> tuple[str, str]:
        """Run render_docs against the scratch BASE_DIR.

        Return the command's own output and what it printed to sys.stdout.
        """
        stdout, printed = StringIO(), StringIO()
        with override_settings(BASE_DIR=self.base_dir), redirect_stdout(printed):
            call_command("render_docs", stdout=stdout)
        return stdout.getvalue(), printed.getvalue()

    def test_it_renders_markdown_to_fragment(self) -> None:
        (self.docs / "guide.md").write_text(MARKDOWN, encoding="utf-8")

        _, printed = self.run_command()

        self.assertIn("Rendering guide.md", printed)
        html = (self.docs / "guide.html-fragment").read_text(encoding="utf-8")
        self.assertTrue(html.startswith("<h1>Getting Started</h1>"))
        self.assertIn("<p>Some <em>emphasis</em> here.</p>", html)
        # fenced_code + codehilite with css_class="highlight"
        self.assertIn('<div class="highlight"><pre><span></span><code><span class="nb">print</span>', html)
        self.assertIn("<th>Name</th>", html)
        self.assertIn("<dt>Grace Time</dt>\n<dd>How long to wait.</dd>", html)
        self.assertIn('<h2 id="anchored">Anchored</h2>', html)

    def test_it_overwrites_stale_fragment(self) -> None:
        (self.docs / "guide.md").write_text("Fresh text", encoding="utf-8")
        (self.docs / "guide.html-fragment").write_text("Stale text", encoding="utf-8")

        self.run_command()

        html = (self.docs / "guide.html-fragment").read_text(encoding="utf-8")
        self.assertEqual(html, "<p>Fresh text</p>")

    def test_it_ignores_files_other_than_markdown(self) -> None:
        (self.docs / "notes.txt").write_text("# Not Markdown", encoding="utf-8")

        _, printed = self.run_command()

        self.assertEqual(printed, "")
        self.assertEqual(sorted(p.name for p in self.docs.iterdir()), ["notes.txt"])

    def test_it_requires_markdown_and_pygments(self) -> None:
        (self.docs / "guide.md").write_text(MARKDOWN, encoding="utf-8")

        for missing in ("markdown", "pygments"):

            def fake_find_spec(name: str, missing: str = missing) -> ModuleSpec | None:
                return None if name == missing else find_spec(name)

            with self.subTest(missing=missing):
                with patch("hc.front.management.commands.render_docs.find_spec", fake_find_spec):
                    output, _ = self.run_command()

                self.assertIn(f"This command requires the {missing} package.", output)
                self.assertFalse((self.docs / "guide.html-fragment").exists())
