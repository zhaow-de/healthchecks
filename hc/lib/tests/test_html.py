from __future__ import annotations

from unittest import TestCase

from hc.lib.html import html2text


class Html2TextTestCase(TestCase):
    def test_it_works(self) -> None:
        sample = """
            <style>css goes here</style>
            <h1 class="foo">Hello</h1>
            World
            <script>js goes here</script>
            """

        self.assertEqual(html2text(sample), "Hello World")

    def test_it_does_not_inject_whitespace(self) -> None:
        sample = """<b>S</b>UCCESS"""
        self.assertEqual(html2text(sample), "SUCCESS")

    def test_it_skips_pre(self) -> None:
        sample = """<p>Output:</p><pre>line 1\nline 2</pre><p>Done</p>"""
        self.assertEqual(html2text(sample), "Output:line 1 line 2Done")
        self.assertEqual(html2text(sample, skip_pre=True), "Output:Done")
