from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "count-list.sh"
CORPUS = (REPO / "CLAUDE.md", *sorted((REPO / ".claude" / "rules").glob("*.md")))  # the always-loaded rules

_ENTRY = re.compile(r'^\s*emit "([^"]+)"', re.MULTILINE)
_CORPUS_ENTRY = re.compile(r"count: `scripts/count-list\.sh ([a-z0-9-]+)`")
_CITED_ENTRY = re.compile(r"scripts/count-list\.sh ([a-z0-9][a-z0-9-]*)")
# The entries no corpus line cites.
NOT_NAMED: set[str] = set()
_VALUE = re.compile(r"\d+(?: passed)?")


def _tracked(*pathspecs: str) -> list[str]:
    """The index's paths, so an untracked scratch file never turns the suite red."""
    listed = subprocess.run(["git", "-C", str(REPO), "ls-files", *pathspecs], capture_output=True, text=True, check=True)
    return listed.stdout.split()


def develop_resolves() -> bool:
    """`develop` is a ref this checkout can resolve; a pull request's CI checkout has none until it makes one."""
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", "develop"], cwd=REPO, capture_output=True).returncode == 0


def _names() -> list[str]:
    return _ENTRY.findall(SCRIPT.read_text())


def test_this_checkout_carries_what_the_counts_measure_from():
    """The state `non-pr-commits-on-develop` needs, asked of the checkout rather than read off a workflow file.

    A `pull_request` checkout is shallow and detached at the merge ref with `origin/develop` alone, so both halves
    are things CI has to be told to provide; without them the whole-list test below skips, and this one fails
    instead of letting the skip read as a pass.
    """
    shallow = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--is-shallow-repository"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert shallow == "false", "a shallow clone: `git fetch --unshallow`, or `fetch-depth: 0` in CI"
    assert develop_resolves(), (
        "no local `develop`: `git branch --force develop origin/develop`, which is what CI runs after its checkout -- "
        "`non-pr-commits-on-develop` refuses without it"
    )


def test_every_rule_window_is_a_full_instant_and_not_a_bare_date():
    """The reason is at the RULE_SINCE constants; this refuses a window inlined through any of git's date flags."""
    constant = re.compile(
        r"^\s*(?:(?:readonly|export|local|declare|typeset)(?:\s+-[A-Za-z]+)*\s+)?([A-Z_]*RULE_SINCE)=(\"[^\"]*\"|'[^']*'|\S+)",
        re.M,
    )

    def _unquote(raw: str) -> str:
        return raw[1:-1] if len(raw) > 1 and raw[:1] in "\"'" and raw[-1:] == raw[:1] else raw

    def seen(text: str) -> list[tuple[str, str]]:
        return [(m.group(1), _unquote(m.group(2))) for m in constant.finditer(text)]

    for spelling, value in (
        ('X_RULE_SINCE="2026-09-13"', "2026-09-13"),
        ("  X_RULE_SINCE='2026-09-13'", "2026-09-13"),
        ("export X_RULE_SINCE=2026-09-13", "2026-09-13"),
        ('    readonly X_RULE_SINCE="2026-09-13"', "2026-09-13"),
        ('X_RULE_SINCE="1 week ago"', "1 week ago"),
        ("  local -r X_RULE_SINCE='3 days ago'", "3 days ago"),
        ("typeset -r X_RULE_SINCE=yesterday", "yesterday"),
        ('declare -rx X_RULE_SINCE="2026-09-13"', "2026-09-13"),
        ("readonly\tX_RULE_SINCE=2026-09-13", "2026-09-13"),
    ):
        assert seen(spelling) == [("X_RULE_SINCE", value)], f"the guard no longer sees {spelling!r} as it is written"
    code = "\n".join(line for line in SCRIPT.read_text().splitlines() if not line.lstrip().startswith("#"))
    since = seen(code)
    assert since, "no RULE_SINCE constant found -- the windows moved somewhere this test cannot see"
    # A spelling the pattern cannot parse drops its window out of `since` unchecked, and the assert above catches
    # only the case where EVERY constant vanished. The counts have to agree, so an unreadable spelling fails
    # instead of hiding.
    assert len(re.findall(r"[A-Z_]*RULE_SINCE=", code)) == len(since), (
        f"a RULE_SINCE assignment is spelled in a way this test cannot read: {since}"
    )
    for name, value in since:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value), f"{name}={value!r} is not an instant"
    window = re.compile(r"--(?:since|after|until|before|since-as-filter|max-age|min-age)[= ](?!['\"]?\$)[^ ]+")
    for spelling in (
        "--since=2026-09-13",
        "--after=2027-01-01",
        "--until='2026-09-13'",
        "--since=yesterday",
        '--before="1 day ago"',
        "--since 2026-09-13",
        "--since-as-filter=2026-09-13",
        "--max-age=1757000000",
    ):
        assert window.search(spelling), f"the guard no longer sees {spelling!r}"
    inlined = window.findall(code)
    assert inlined == [], f"a window is inlined instead of naming its RULE_SINCE: {inlined}"


def test_the_corpus_names_every_entry_but_the_one_the_script_carries_on_its_own():
    names = _names()
    assert len(names) == len(set(names)), f"two entries answer to one name: {sorted(names)}"
    texts = [p.read_text() for p in CORPUS]
    corpus = {name for text in texts for name in _CORPUS_ENTRY.findall(text)}
    inline = sum(text.count("count: ") for text in texts) - sum(len(_CORPUS_ENTRY.findall(text)) for text in texts)
    assert inline == 0, f"{inline} corpus count(s) carry a command inline instead of naming an entry"
    assert corpus <= set(names), f"the corpus names entries the script lacks: {sorted(corpus - set(names))}"
    assert set(names) - corpus == NOT_NAMED, f"entries the corpus does not name: {sorted(set(names) - corpus)}"


def test_every_entry_the_guidance_runs_exists_and_every_entry_is_run_by_something():
    """A skill that runs `scripts/count-list.sh <entry>` by name runs an entry that exists, and an entry no corpus line
    cites is still run by the guidance -- otherwise nothing reads its value and it is dead weight in every run."""
    names = set(_names())
    cited: dict[str, list[str]] = {}
    for rel in _tracked("CLAUDE.md", ".claude"):
        for name in _CITED_ENTRY.findall((REPO / rel).read_text(encoding="utf-8", errors="replace")):
            cited.setdefault(name, []).append(rel)
    assert len(cited) >= len(names), f"the citation pattern found suspiciously few entries: {sorted(cited)}"
    unknown = {name: files for name, files in cited.items() if name not in names}
    assert unknown == {}, f"guidance runs entries the script lacks: {unknown}"
    assert NOT_NAMED <= set(cited), f"entries nothing in the guidance runs: {sorted(NOT_NAMED - set(cited))}"


def test_a_named_entry_runs_alone_and_an_unknown_name_is_refused():
    one = subprocess.run(["bash", str(SCRIPT), "changelog-files"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert one.returncode == 0 and one.stdout.splitlines() == [f"changelog-files\t{one.stdout.split(chr(9))[1].strip()}"], (
        one.stdout + one.stderr
    )
    none = subprocess.run(["bash", str(SCRIPT), "no-such-entry"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert none.returncode == 2 and "no entry named no-such-entry" in none.stderr, none.stdout + none.stderr


_CLIENT_EXEMPTIONS = {
    "hc/lib/curl.py": "import pycurl\n",
    "hc/integrations/webhook/tests/test_notify.py": "import apprise\nimport requests\n",
}


@pytest.mark.parametrize("module", ["webhook", "apprise"])
@pytest.mark.parametrize("line", ["import apprise", "from apprise import Apprise", "import apprise.plugins", "import requests"])
def test_http_clients_outside_hc_lib_curl_counts_a_module_that_imports_a_client(tmp_path, module, line):
    def count() -> str:
        done = subprocess.run(
            ["bash", str(SCRIPT), "http-clients-outside-hc-lib-curl"], cwd=tmp_path, capture_output=True, text=True, timeout=120
        )
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    transport = tmp_path / "hc" / "integrations" / module / "transport.py"
    for path, text in {**_CLIENT_EXEMPTIONS, f"hc/integrations/{module}/transport.py": "from hc.lib import curl\n"}.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    assert count() == "http-clients-outside-hc-lib-curl\t0\n"
    transport.write_text(transport.read_text() + line + "\n")
    assert count() == "http-clients-outside-hc-lib-curl\t1\n"


@pytest.mark.skipif(
    not develop_resolves(), reason="non-pr-commits-on-develop reads the develop ref by name, and this checkout has none"
)
def test_the_script_prints_one_shaped_line_per_entry():
    """Every entry reads the checkout alone, so the whole list runs here with no network and no API."""
    done = subprocess.run(["bash", str(SCRIPT)], cwd=REPO, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == len(_names()), done.stdout
    for line in lines:
        name, tab, value = line.partition("\t")
        assert tab == "\t" and name, f"no name and tab: {line!r}"
        for part in value.split("; "):
            assert _VALUE.fullmatch(part), f"{name} printed no count: {value!r}"
