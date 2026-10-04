import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test.utils import override_settings

from hc.test import BaseTestCase

SNIPPET_NAMES = [
    "bash_curl",
    "bash_wget",
    "browser",
    "node",
    "go",
    "python_urllib2",
    "python_requests",
]


class PygmentizeTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        # The command reads and writes templates/front/snippets under BASE_DIR,
        # so run it against a scratch copy of that directory.
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.base_dir = Path(tmp)
        self.snippets = self.base_dir / "templates" / "front" / "snippets"
        self.snippets.mkdir(parents=True)
        for src in (settings.BASE_DIR / "templates" / "front" / "snippets").glob("*.txt"):
            src.copy(self.snippets / src.name)

    def run_command(self) -> str:
        stdout = StringIO()
        with override_settings(BASE_DIR=self.base_dir):
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

    def test_it_requires_pygments(self) -> None:
        with patch("hc.front.management.commands.pygmentize.have_pygments", False):
            output = self.run_command()

        self.assertIn("This command requires the Pygments package.", output)
        self.assertEqual(list(self.snippets.glob("*.html")), [])
