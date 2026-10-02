from __future__ import annotations

import os
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command

from hc.test import BaseTestCase

SNIPPET_NAMES = [
    "bash_curl",
    "bash_wget",
    "browser",
    "cs",
    "node",
    "go",
    "python_urllib2",
    "python_requests",
    "python_requests_fail",
    "python_requests_start",
    "python_requests_payload",
    "php",
    "powershell",
    "powershell_inline",
    "ruby",
]


class PygmentizeTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        # The command reads and writes templates/front/snippets relative to the
        # working directory, so run it in a scratch copy of that directory.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.snippets = Path(tmp.name) / "templates" / "front" / "snippets"
        self.snippets.mkdir(parents=True)
        for src in (settings.BASE_DIR / "templates" / "front" / "snippets").glob("*.txt"):
            shutil.copy(src, self.snippets / src.name)

        cwd = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, cwd)

    def run_command(self) -> str:
        stdout = StringIO()
        call_command("pygmentize", stdout=stdout)
        return stdout.getvalue()

    def test_it_highlights_every_snippet(self) -> None:
        self.run_command()

        for name in SNIPPET_NAMES:
            with self.subTest(name=name):
                html = (self.snippets / f"{name}.html").read_text()
                self.assertTrue(html.startswith('<div class="highlight"><pre>'))
                self.assertIn("{{ ping_url }}", html)
                self.assertNotIn("PING_URL", html)

    def test_it_uses_language_specific_lexers(self) -> None:
        self.run_command()

        python = (self.snippets / "python_requests.html").read_text()
        self.assertIn('<span class="kn">import</span>', python)

        # PhpLexer(startinline=True) highlights code that has no "<?php" opener
        php = (self.snippets / "php.html").read_text()
        self.assertIn('<span class="nb">file_get_contents</span>', php)

    def test_it_replaces_site_root_and_ping_endpoint(self) -> None:
        (self.snippets / "bash_curl.txt").write_text("curl SITE_ROOT/api/v3/checks/ PING_ENDPOINTabc\n")

        self.run_command()

        html = (self.snippets / "bash_curl.html").read_text()
        self.assertIn("{{ SITE_ROOT }}/api/v3/checks/", html)
        self.assertIn("{{ PING_ENDPOINT }}abc", html)

    def test_it_requires_pygments(self) -> None:
        with patch("hc.front.management.commands.pygmentize.have_pygments", False):
            output = self.run_command()

        self.assertIn("This command requires the Pygments package.", output)
        self.assertEqual(list(self.snippets.glob("*.html")), [])
