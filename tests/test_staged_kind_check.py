"""`scripts/staged-kind-check.sh` — the one-kind-per-commit hook."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "staged-kind-check.sh"


def _repo(tmp_path: Path) -> Path:
    run = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (tmp_path / "seed.txt").write_text("seed\n")
    run("add", "seed.txt")
    run("commit", "-qm", "seed")
    return tmp_path


def _stage(repo: Path, *names: str) -> None:
    """Fixture paths stay off `.claude/skills/*/SKILL.md` and friends: `tests/test_guidance_refs_resolve.py`
    reads those as citations and a fake one dangles."""
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
        subprocess.run(["git", "-C", str(repo), "add", name], check=True, capture_output=True)


def _run(repo: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, env=env)


@pytest.mark.parametrize(
    ("staged", "rc"),
    [
        ((".claude/fixture.txt", "hc/thing.py"), 1),  # the defect the hook is for
        (("CLAUDE.md", "tests/test_thing.py"), 1),  # CLAUDE.md is claude-kind by name, not by directory
        ((".claude/settings.json", "CLAUDE.md"), 0),  # both claude-kind
        (("hc/thing.py", "tests/test_thing.py", "templates/docs/x.md"), 0),  # a feat/fix commit legitimately mixes these
    ],
)
def test_the_hook_refuses_only_a_mixed_kind(tmp_path, staged, rc):
    repo = _repo(tmp_path)
    _stage(repo, *staged)
    done = _run(repo)
    assert done.returncode == rc, done.stdout + done.stderr
    if rc:
        assert "split the commit" in done.stdout


def _stopped_merge(repo: Path, heads: int = 1) -> None:
    """Both kinds arrive from THEIRS, so each is new against HEAD and a staged set of the two is really mixed."""
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
    shas = []
    for n in range(heads):
        run("checkout", "-q", "-b", f"theirs{n}")
        _stage(repo, f".claude/fixture{n}.txt", f"hc/thing{n}.py")
        run("commit", "-qm", "both kinds on their side")
        run("checkout", "-q", "-")
        shas.append(
            subprocess.run(
                ["git", "-C", str(repo), "rev-parse", f"theirs{n}"], check=True, capture_output=True, text=True
            ).stdout.strip()
        )
    (repo / ".git" / "MERGE_HEAD").write_text("".join(sha + "\n" for sha in shas))


def test_a_merge_exempts_its_own_files(tmp_path):
    """The mixed set a merge itself stages passes: the author chose neither side, and splitting is impossible.

    Asserted against the arm's absence too, because a single-kind staged set would pass either way."""
    repo = _repo(tmp_path)
    _stopped_merge(repo)
    _stage(repo, ".claude/fixture0.txt", "hc/thing0.py")
    assert _run(repo).returncode == 0

    (repo / ".git" / "MERGE_HEAD").unlink()
    assert _run(repo).returncode == 1, "the staged set must be one the hook refuses without the exemption"


def test_a_merge_does_not_exempt_a_pair_only_our_side_touched(tmp_path):
    """A mixed pair from our own history, staged by hand during a stopped merge, is the author's, not the merge's."""
    repo = _repo(tmp_path)
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    run("checkout", "-q", "-b", "theirs", base)
    _stage(repo, "docs/other.md")
    run("commit", "-qm", "theirs touches one other file")
    run("checkout", "-q", "-")
    _stage(repo, ".claude/ours.txt", "hc/ours.py")
    run("commit", "-qm", "our side touched both kinds since the base")
    theirs = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "theirs"], check=True, capture_output=True, text=True
    ).stdout.strip()
    (repo / ".git" / "MERGE_HEAD").write_text(theirs + "\n")
    for path in (".claude/ours.txt", "hc/ours.py"):  # edited again and staged by hand, inside the stopped merge
        (repo / path).write_text("edited during the merge\n")
    run("add", ".claude/ours.txt", "hc/ours.py")
    assert _run(repo).returncode == 1


def test_an_octopus_merge_exempts_every_heads_files(tmp_path):
    """`MERGE_HEAD` carries one line per merged head; read as one, the arm is a git fatal and rc 128."""
    repo = _repo(tmp_path)
    _stopped_merge(repo, heads=2)
    _stage(repo, ".claude/fixture0.txt", "hc/thing0.py", ".claude/fixture1.txt", "hc/thing1.py")
    assert _run(repo).returncode == 0


def test_a_merge_does_not_exempt_files_neither_parent_touched(tmp_path):
    """A mixed pair neither side of the merge touched is judged, not exempted."""
    repo = _repo(tmp_path)
    _stopped_merge(repo)
    _stage(repo, ".claude/fixture0.txt", "hc/thing0.py")  # the merge's own, excused
    _stage(repo, ".claude/other.json", "hc/unrelated.py")  # neither side's, still judged
    done = _run(repo)
    assert done.returncode == 1
    assert "split the commit" in done.stdout


def _merging(repo: Path, theirs: dict[str, str], ours: dict[str, str] | None = None) -> int:
    """`git merge --no-commit` of a branch that writes `theirs`, after our side writes `ours`; its rc, 1 on a conflict."""
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
    git("checkout", "-q", "-b", "theirs")
    for name, text in theirs.items():
        _write(repo, name, text)
    git("commit", "-qm", "their side")
    git("checkout", "-q", "-")
    for name, text in (ours or {}).items():
        _write(repo, name, text)
    if ours:
        git("commit", "-qm", "our side")
    return subprocess.run(
        ["git", "-C", str(repo), "merge", "-q", "--no-commit", "--no-ff", "theirs"], capture_output=True
    ).returncode


def _write(repo: Path, name: str, text: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", name], check=True, capture_output=True)


def test_an_own_claude_edit_beside_a_merge_of_another_kind_is_refused(tmp_path):
    """The merge brings code alone; the author's own CLAUDE.md edit staged with it is a mix the author made, and splittable."""
    repo = _repo(tmp_path)
    assert _merging(repo, {"hc/thing.py": "theirs\n"}) == 0
    assert _run(repo).returncode == 0, "the merge alone is excused"
    _write(repo, "CLAUDE.md", "mine\n")
    done = _run(repo)
    assert done.returncode == 1 and "split the commit" in done.stdout and "  CLAUDE.md\n" in done.stdout, done.stdout
    assert "hc/thing.py" not in done.stdout, "what the merge brings is excused, not listed"


def test_an_own_edit_of_another_kind_beside_a_merge_of_claude_kind_files_is_refused(tmp_path):
    """The mirror: the merge brings claude-kind files alone, and the author's own README.md staged with it is the mix."""
    repo = _repo(tmp_path)
    assert _merging(repo, {".claude/fixture.txt": "theirs\n"}) == 0
    assert _run(repo).returncode == 0, "the merge alone is excused"
    _write(repo, "README.md", "mine\n")
    done = _run(repo)
    assert done.returncode == 1 and "split the commit" in done.stdout and "  README.md\n" in done.stdout, done.stdout
    assert ".claude/fixture.txt" not in done.stdout, "what the merge brings is excused, not listed"


def test_an_own_edit_to_a_file_the_merge_brings_is_judged_by_its_content(tmp_path):
    """A path the other side changed is excused only while it holds what the merge makes of it."""
    repo = _repo(tmp_path)
    assert _merging(repo, {".claude/fixture.txt": "theirs\n", "hc/thing.py": "theirs\n"}) == 0
    assert _run(repo).returncode == 0
    _write(repo, ".claude/fixture.txt", "theirs, then mine\n")
    _write(repo, "hc/thing.py", "theirs, then mine\n")
    assert _run(repo).returncode == 1


def test_a_merge_that_brings_both_kinds_takes_an_own_change_of_one_kind(tmp_path):
    """The merge already mixes, so an own fix of one kind adds no mix; an own change of both kinds still does."""
    repo = _repo(tmp_path)
    assert _merging(repo, {".claude/fixture.txt": "theirs\n", "hc/thing.py": "theirs\n"}) == 0
    _write(repo, "hc/fix.py", "mine\n")
    assert _run(repo).returncode == 0
    _write(repo, "CLAUDE.md", "mine\n")
    assert _run(repo).returncode == 1


def test_a_conflict_s_resolution_is_the_merge_s(tmp_path):
    """A conflicted path's resolution is the merge's, so the merge brings both kinds here and an own CLAUDE.md edit
    of one kind passes; read as the author's, the resolved code would make that edit a mix."""
    repo = _repo(tmp_path)
    _write(repo, "hc/x.py", "base\n")
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x"], check=True, capture_output=True)
    assert _merging(repo, {"hc/x.py": "theirs\n", ".claude/fixture.txt": "theirs\n"}, ours={"hc/x.py": "ours\n"}) == 1
    _write(repo, "hc/x.py", "ours\ntheirs\n")
    assert _run(repo).returncode == 0
    _write(repo, "CLAUDE.md", "mine\n")
    assert _run(repo).returncode == 0


def _merge_of_code_with_an_own_mixed_pair(repo: Path) -> None:
    """A stopped merge that brings code, and an own pair of both kinds beside it: refused while the merge is rebuilt."""
    assert _merging(repo, {"hc/thing.py": "theirs\n"}) == 0
    _write(repo, ".claude/fixture.txt", "mine\n")
    _write(repo, "hc/mine.py", "mine\n")
    assert _run(repo).returncode == 1


@pytest.mark.parametrize("names", ["a missing object", "a tree"])
def test_a_merge_head_that_names_no_commit_is_refused_before_merge_tree_runs(tmp_path, names):
    repo = _repo(tmp_path)
    _merge_of_code_with_an_own_mixed_pair(repo)
    tree = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD^{tree}"], check=True, capture_output=True, text=True)
    head = "0" * 40 if names == "a missing object" else tree.stdout.strip()
    (repo / ".git" / "MERGE_HEAD").write_text(head + "\n")
    done = _run(repo)
    assert done.returncode == 2 and f"the merge of {head}: it names no commit" in done.stdout, done.stdout + done.stderr


def test_a_merge_tree_that_exits_1_without_a_tree_is_refused(tmp_path, tmp_path_factory):
    """The head resolves, but merge-tree fails with exit 1 and prints nothing: an error, not a conflict."""
    repo = _repo(tmp_path)
    _merge_of_code_with_an_own_mixed_pair(repo)
    stub = tmp_path_factory.mktemp("bin") / "git"
    stub.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do [ "$arg" = merge-tree ] && { echo "merge-tree: not something we can merge" >&2; exit 1; }; done\n'
        f'exec "{shutil.which("git")}" "$@"\n'
    )
    stub.chmod(0o755)
    done = _run(repo, env={**os.environ, "PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}"})
    assert done.returncode == 2 and "cannot rebuild the merge of " in done.stdout, done.stdout + done.stderr
    assert "names no commit" not in done.stdout, "the head resolves; the refusal is merge-tree's failure"
