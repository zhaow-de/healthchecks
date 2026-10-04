"""Every path a live surface cites resolves to a file that exists.

Outside the scope, deliberately: the application under `hc/`, `templates/` and `static/`, whose own paths its own tests hold.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The surfaces a session loads or follows; `tests/` for the comments that send a reader somewhere.
LIVE = ("CLAUDE.md", ".claude/", "scripts/", "tests/")
# Where a code span naming any repository path is held to resolve.
SPANS = ("CLAUDE.md", ".claude/", "scripts/")

_GUIDANCE = re.compile(
    r"\.claude/(?:rules/[A-Za-z0-9._-]+\.md"
    r"|skills/[A-Za-z0-9._-]+/(?:SKILL\.md|references/[A-Za-z0-9._-]+\.md|scripts/[A-Za-z0-9._-]+\.(?:py|sh))"
    r"|workflows/[A-Za-z0-9._-]+\.js"
    r"|hooks/[A-Za-z0-9._-]+\.sh"
    r"|settings\.json)"
)
# A path with no directory before it: `references/<name>` and `scripts/<name>` inside a skill mean that skill's own
# file; `scripts/<name>` anywhere else is the repository's tooling, and a skill that runs the tooling writes it the
# same way, so inside a skill a script resolves against the skill's directory first and the repository root second.
_RELATIVE = re.compile(r"(?<![A-Za-z0-9._/-])(references/[A-Za-z0-9._-]+\.md|scripts/[A-Za-z0-9._-]+\.(?:py|sh))")
_SPAN = re.compile(r"`([^`\n]+)`")
_PATH = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+/?")
# A skill or a workflow named as one: code-span names before the word (`a`, `b` and `c` workflows; the `x` skill's)
# or after it (the workflows `a`, `b` and `c`), and a skill's slash command (`/x` or `/x <args>`).
_NAMES = r"((?:`[a-z0-9-]+`(?:, | and | or ))*`[a-z0-9-]+`)"
_NAMED_BEFORE = re.compile(_NAMES + r"(?:'s)? (skill|workflow)s?\b")
_NAMED_AFTER = re.compile(r"\b(skill|workflow)s? " + _NAMES)
_SLASH = re.compile(r"`/([a-z0-9-]+)(?: [^`\n]*)?`")
_NAME = re.compile(r"`([a-z0-9-]+)`")

# Prefixes assembled at run time, so this file's own allowlists and fixtures never read as citations when the
# checker walks the real tree -- an allowlist made of the literals it allows could not fail.
_C = ".claude" + "/"
_RULES, _SKILLS, _FLOWS, _HOOKS = _C + "rules/", _C + "skills/", _C + "workflows/", _C + "hooks/"
_SCRIPTS = "scripts" + "/"

# Paths a test builds to drive a refusal over a synthetic tree; they name no file and must not. Asserted both
# ways, so an entry that stops being cited, or starts resolving, fails rather than sitting here unread.
_SYNTHETIC: set[str] = set()
# Code spans naming a path that is never tracked by design: the gitignored local settings and the lesson inbox
# file, which each checkout creates. Asserted both ways, like the synthetic set.
_UNTRACKED = {"hc/local_settings.py", ".local/agent-lessons/main.jsonl"}

# Walked prefixes that cite nothing today and are kept anyway. Asserted both ways, so a prefix that starts citing
# loses its entry here.
_QUIET: set[str] = set()


def _walked(listed: list[str], scope: tuple[str, ...] = LIVE) -> list[str]:
    return [r for r in listed if r.startswith(scope)]


def _skill_of(rel: str) -> str | None:
    parts = rel.split("/")
    return "/".join(parts[:3]) if rel.startswith(_SKILLS) and len(parts) > 3 else None


def _read(root: Path, rel: str) -> str | None:
    try:
        return (root / rel).read_text(encoding="utf-8")
    except UnicodeDecodeError, FileNotFoundError:
        return None


def citations(root: Path, listed: list[str]) -> dict[str, list[str]]:
    """Every guidance and tooling path a live surface of `root` cites, absolute or relative, mapped to the surfaces citing it."""
    found: dict[str, list[str]] = {}
    for rel in _walked(listed):
        text = _read(root, rel)
        if text is None:
            continue
        targets = set(_GUIDANCE.findall(text))
        skill = _skill_of(rel)
        for m in _RELATIVE.findall(text):
            if skill is None:
                if m.startswith(_SCRIPTS):
                    targets.add(m)
            elif m.startswith(_SCRIPTS) and not (root / skill / m).is_file() and (root / m).is_file():
                targets.add(m)
            else:
                targets.add(f"{skill}/{m}")
        for target in targets:
            found.setdefault(target, []).append(rel)
    return found


def dangling(root: Path, listed: list[str], allowed: set[str]) -> dict[str, list[str]]:
    """The cited guidance and tooling paths that name no file, the allowlisted synthetic ones aside."""
    found = citations(root, listed)
    return {t: sorted(s) for t, s in found.items() if t not in allowed and not (root / t).is_file()}


def span_paths(root: Path, listed: list[str]) -> dict[str, list[str]]:
    """Every code span under `SPANS` that is a repository path -- two segments or more, the first of them a top-level
    name the index holds, so a URL host, an image name or `owner/repo` is not one -- mapped to the surfaces writing it."""
    top = {p.split("/")[0] for p in listed}
    found: dict[str, list[str]] = {}
    for rel in _walked(listed, SPANS):
        text = _read(root, rel)
        if text is None:
            continue
        for span in set(_SPAN.findall(text)):
            if _PATH.fullmatch(span) and span.split("/")[0] in top:
                found.setdefault(span, []).append(rel)
    return found


def unresolved_spans(root: Path, listed: list[str], allowed: set[str]) -> dict[str, list[str]]:
    """The code-span paths that name neither a tracked file nor a tracked directory; inside a skill, its own directory
    is tried first, as for a relative citation."""
    files = set(listed)
    dirs = {"/".join(p.split("/")[:i]) for p in listed for i in range(1, p.count("/") + 1)}
    out: dict[str, list[str]] = {}
    for span, surfaces in span_paths(root, listed).items():
        bare = span.rstrip("/")
        for surface in surfaces:
            skill = _skill_of(surface)
            candidates = [bare, *([f"{skill}/{bare}"] if skill else [])]
            if span not in allowed and not any(c in files or c in dirs for c in candidates):
                out.setdefault(span, []).append(surface)
    return {span: sorted(s) for span, s in out.items()}


def named(root: Path, listed: list[str]) -> dict[str, list[str]]:
    """Every skill and workflow `SPANS` name as one, as the file that has to exist, mapped to the surfaces naming it."""
    found: dict[str, list[str]] = {}
    for rel in _walked(listed, SPANS):
        text = _read(root, rel)
        if text is None:
            continue
        pairs = [(kind, names) for names, kind in _NAMED_BEFORE.findall(text)] + _NAMED_AFTER.findall(text)
        pairs += [("skill", f"`{name}`") for name in _SLASH.findall(text)]
        targets = {
            f"{_SKILLS}{name}/SKILL.md" if kind == "skill" else f"{_FLOWS}{name}.js"
            for kind, names in pairs
            for name in _NAME.findall(names)
        }
        for target in targets:
            found.setdefault(target, []).append(rel)
    return found


def unnamed(root: Path, listed: list[str]) -> dict[str, list[str]]:
    """The skills and workflows named as one that the index does not hold."""
    files = set(listed)
    return {t: sorted(s) for t, s in named(root, listed).items() if t not in files}


def stale_allowlist(root: Path, cited: dict[str, list[str]], allowed: set[str]) -> tuple[list[str], list[str]]:
    """(the allowlisted paths nothing cites any more, the allowlisted paths that now name a real file)."""
    return sorted(p for p in allowed if p not in cited), sorted(p for p in allowed if (root / p).is_file())


def quiet_prefixes(root: Path, listed: list[str], prefixes: tuple[str, ...]) -> set[str]:
    """The walked prefixes under which no surface cites any guidance or tooling at all."""
    return {p for p in prefixes if not citations(root, [r for r in listed if r.startswith(p)])}


def _tracked() -> list[str]:
    listed = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True)
    return listed.stdout.split()


def test_a_live_surface_cites_no_guidance_or_tooling_file_that_is_missing():
    listed = _tracked()
    cited = citations(REPO, listed)
    assert len(cited) > 8, "the citation regex found suspiciously few targets -- it is broken, not the tree clean"
    assert dangling(REPO, listed, _SYNTHETIC) == {}, "live surfaces cite guidance or tooling files that do not exist"


def test_every_path_the_guidance_writes_as_code_resolves():
    listed = _tracked()
    assert len(span_paths(REPO, listed)) > 20, "the span reader found suspiciously few paths -- it is broken, not the tree clean"
    assert unresolved_spans(REPO, listed, _UNTRACKED) == {}, "code spans name paths the index does not hold"


def test_every_skill_and_workflow_named_as_one_exists():
    listed = _tracked()
    found = named(REPO, listed)
    assert {t for t in found if t.startswith(_SKILLS)} and {t for t in found if t.startswith(_FLOWS)}, (
        "the name reader found no skill or no workflow -- it is broken, not the tree clean"
    )
    assert unnamed(REPO, listed) == {}, "the guidance names skills or workflows that do not exist"


def test_every_walked_prefix_earns_its_place():
    """A prefix contributing nothing is a surface that moved or a scope quietly shrunk."""
    listed = _tracked()
    quiet = quiet_prefixes(REPO, listed, LIVE)
    assert quiet - _QUIET == set(), f"walked prefixes citing no guidance or tooling at all: {sorted(quiet - _QUIET)}"
    assert _QUIET - quiet == set(), f"prefixes recorded as quiet that now cite: {sorted(_QUIET - quiet)}"


def test_the_allowlists_are_neither_stale_nor_resolving():
    """An allowlisted path that stopped being cited, or that now names a real file, is an entry to delete."""
    listed = _tracked()
    unused, real = stale_allowlist(REPO, citations(REPO, listed), _SYNTHETIC)
    assert unused == [], f"allowlisted synthetic paths no longer cited anywhere: {unused}"
    assert real == [], f"allowlisted synthetic paths now name real files, so they are citations: {real}"
    spans = span_paths(REPO, listed)
    assert sorted(p for p in _UNTRACKED if p not in spans) == [], "allowlisted untracked paths no longer written anywhere"
    tracked = {"/".join(p.split("/")[:i]) for p in listed for i in range(1, p.count("/") + 2)}
    assert sorted(p for p in _UNTRACKED if p.rstrip("/") in tracked) == [], "allowlisted untracked paths are now tracked"


_LIVE_RULE, _GONE_RULE = _RULES + "live.md", _RULES + "gone.md"
_KEEP_SKILL, _A_FLOW, _A_HOOK = _SKILLS + "keep/SKILL.md", _FLOWS + "flow.js", _HOOKS + "guard.sh"
_A_REF, _A_SCRIPT = _SKILLS + "keep/references/ref.md", _SKILLS + "keep/scripts/tool.py"
_SETTINGS = _C + "settings.json"
_TOOL = _SCRIPTS + "gate.py"


def _fake(tmp_path: Path) -> list[str]:
    """A tree whose live surfaces cite every shape, beside a file outside the scope citing a deleted rule."""
    for rel in (_LIVE_RULE, _KEEP_SKILL, _A_FLOW, _A_HOOK, _A_REF, _A_SCRIPT, _SETTINGS, _TOOL):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("a guidance file\n")
    (tmp_path / "templates" / "docs").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text(
        f"reads `{_LIVE_RULE}`, `{_KEEP_SKILL}`, `{_A_FLOW}`, `{_A_HOOK}` and `{_SETTINGS}`, and runs `{_TOOL}`\n"
    )
    # The skill cites its own reference and script relatively, and the repository's script the same way.
    (tmp_path / _KEEP_SKILL).write_text(f"renders `references/ref.md`, runs `{_SCRIPTS}tool.py` and then `{_SCRIPTS}gate.py`\n")
    (tmp_path / "templates" / "docs" / "a.md").write_text(f"cited `{_GONE_RULE}` and `{_SCRIPTS}gone.py`\n")
    return ["CLAUDE.md", _LIVE_RULE, _KEEP_SKILL, _A_FLOW, _A_HOOK, _A_REF, _A_SCRIPT, _SETTINGS, _TOOL, "templates/docs/a.md"]


def test_the_checker_names_a_live_surface_and_leaves_one_outside_the_scope(tmp_path):
    listed = _fake(tmp_path)
    assert dangling(tmp_path, listed, set()) == {}, "the template's dead citations are outside the scope"
    corpus = tmp_path / "CLAUDE.md"
    corpus.write_text(corpus.read_text() + f"and `{_GONE_RULE}`\n")
    assert dangling(tmp_path, listed, set()) == {_GONE_RULE: ["CLAUDE.md"]}
    assert dangling(tmp_path, listed, {_GONE_RULE}) == {}, "an allowlisted path is not dangling"


def test_the_checker_reads_every_citation_shape(tmp_path):
    listed = _fake(tmp_path)
    assert set(citations(tmp_path, listed)) == {
        _LIVE_RULE,
        _KEEP_SKILL,
        _A_FLOW,
        _A_HOOK,
        _A_REF,
        _A_SCRIPT,
        _SETTINGS,
        _TOOL,
    }, "a citation shape the tree uses went unread"


def test_a_skills_own_relative_citation_resolves_against_its_directory(tmp_path):
    """`references/x.md` inside a SKILL.md means that skill's own file, and is how the tree usually writes it."""
    listed = _fake(tmp_path)
    (tmp_path / _A_REF).unlink()
    assert dangling(tmp_path, listed, set()) == {_A_REF: [_KEEP_SKILL]}


def test_a_skills_script_falls_back_to_the_repository_root_and_not_further(tmp_path):
    """A skill runs the repository's `scripts/` by the same relative spelling as its own; with neither file there, the
    skill's own reading is the one reported, beside the root citation that dangles too."""
    listed = _fake(tmp_path)
    assert citations(tmp_path, listed)[_TOOL] == ["CLAUDE.md", _KEEP_SKILL]
    (tmp_path / _TOOL).unlink()
    assert dangling(tmp_path, listed, set()) == {_TOOL: ["CLAUDE.md"], _SKILLS + "keep/" + _TOOL: [_KEEP_SKILL]}


def test_the_allowlist_check_catches_an_uncited_entry_and_a_resolving_one(tmp_path):
    listed = _fake(tmp_path)
    cited = citations(tmp_path, listed)
    assert stale_allowlist(tmp_path, cited, {_GONE_RULE}) == ([_GONE_RULE], []), "an entry nothing cites is named"
    assert stale_allowlist(tmp_path, cited, {_LIVE_RULE}) == ([], [_LIVE_RULE]), "an entry naming a real file is named"


def test_the_quiet_check_names_a_barren_prefix_and_not_a_citing_one(tmp_path):
    listed = _fake(tmp_path)
    assert quiet_prefixes(tmp_path, listed, ("CLAUDE.md", "templates/")) == {"templates/"}, "the docs cite nothing walked"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text("# nothing here\n")
    assert quiet_prefixes(tmp_path, [*listed, "tests/test_m.py"], ("tests/",)) == {"tests/"}
    (tmp_path / "tests" / "test_m.py").write_text(f"# see `{_LIVE_RULE}`\n")
    assert quiet_prefixes(tmp_path, [*listed, "tests/test_m.py"], ("tests/",)) == set()


def test_a_code_span_path_resolves_to_a_tracked_file_or_directory(tmp_path):
    """Read off the index, not the disk: a span naming a file a checkout happens to hold untracked is still a miss."""
    listed = _fake(tmp_path)
    (tmp_path / "hc" / "api").mkdir(parents=True)
    (tmp_path / "hc" / "api" / "models.py").write_text("x\n")
    listed.append("hc/api/models.py")
    page = tmp_path / _LIVE_RULE
    page.write_text(
        "`hc/api/models.py`, `hc/api/`, `hc/api`, `templates/docs/`, `ghcr.io/x/y`, `owner/repo`, `/api/v1/`, `hc/<app>/`"
        f" and `{_SCRIPTS}tool.py`\n"
    )
    assert unresolved_spans(tmp_path, listed, set()) == {_SCRIPTS + "tool.py": [_LIVE_RULE]}, (
        "outside a skill a script is the root's"
    )
    page.write_text("`hc/api/views.py` and `hc/front/`\n")
    (tmp_path / "hc" / "api" / "views.py").write_text("untracked\n")
    assert unresolved_spans(tmp_path, listed, set()) == {"hc/api/views.py": [_LIVE_RULE], "hc/front/": [_LIVE_RULE]}
    assert unresolved_spans(tmp_path, listed, {"hc/api/views.py", "hc/front/"}) == {}
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("# `hc/gone.py`\n")
    (tmp_path / "templates" / "docs" / "a.md").write_text("`hc/gone.py`\n")
    assert "hc/gone.py" not in span_paths(tmp_path, [*listed, "tests/test_x.py"]), "a span outside the scope is not read"


def test_a_skill_or_workflow_is_read_by_the_name_it_is_given(tmp_path):
    listed = _fake(tmp_path)
    listed += [_SKILLS + "release/SKILL.md", _FLOWS + "review.js"]
    page = tmp_path / _LIVE_RULE
    page.write_text(
        "the `release` skill's merge; the workflows `review`, `pre-review` and `re-review`; the `gone` workflow;"
        " `/tidy round` and `/release`; `review` alone is no name, nor `/api/v1/`\n"
    )
    assert set(named(tmp_path, listed)) == {
        _SKILLS + "release/SKILL.md",
        _SKILLS + "tidy/SKILL.md",
        _FLOWS + "review.js",
        _FLOWS + "pre-review.js",
        _FLOWS + "re-review.js",
        _FLOWS + "gone.js",
    }
    assert unnamed(tmp_path, listed) == {
        _SKILLS + "tidy/SKILL.md": [_LIVE_RULE],
        _FLOWS + "pre-review.js": [_LIVE_RULE],
        _FLOWS + "re-review.js": [_LIVE_RULE],
        _FLOWS + "gone.js": [_LIVE_RULE],
    }


def test_the_walked_scope_is_the_one_recorded_here():
    """Deleting a prefix shrinks what the other tests iterate over, so the tuples themselves are pinned: a scope change
    is a deliberate edit here."""
    assert LIVE == ("CLAUDE.md", ".claude/", "scripts/", "tests/")
    assert SPANS == ("CLAUDE.md", ".claude/", "scripts/")
