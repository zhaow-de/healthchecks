"""merge-gate.py: the read line must be at the floor and name the head, with the exceptions the cases
below drive, and every gh call it makes names this repository."""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "merge-gate.py"


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gate = _load(_SCRIPT, "merge_gate")


def _eval(pr, fetched=(), kept=None):
    return gate.evaluate(pr, list(fetched), kept)


TIP = "6f02667280cfbd7b76cb39d3139a5f865d995c61"
PREV = "20a3bddb1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f"


def _pr(**over) -> dict:
    pr = {
        "number": 1,
        "url": "https://github.com/zhaow-de/healthchecks/pull/1",
        "headRefName": "feat/x",
        "baseRefName": "develop",
        "state": "OPEN",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}],
        "body": f"## Summary\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n- [x] done\n",
        "headRefOid": TIP,
    }
    pr.update(over)
    return pr


def _stale_body(sha: str = PREV) -> str:
    return f"## Summary\n\nRead before push by: Claude Fable 5.1 at {sha[:8]}\n\n- [x] done\n"


def test_a_read_at_the_head_passes():
    assert _eval(_pr()) == []


def test_the_clone_s_answer_admits_or_refuses_a_head_past_the_read():
    pr = _pr(body=_stale_body())
    assert _eval(pr, kept=True) == []
    for answer in (None, "the head's tree is not the read's"):
        fails = _eval(pr, kept=answer)
        assert len(fails) == 1 and fails[0].startswith(f"the read named in the body covers {PREV[:8]}, not the head {TIP[:8]}")
        assert ("the head's tree is not the read's" in fails[0]) is isinstance(answer, str), answer


def test_a_stale_read_the_clone_was_not_asked_about_fails():
    assert len(_eval(_pr(body=_stale_body()))) == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/healthchecks/healthchecks/pull/1",
        "https://github.com/zhaow-de/healthchecks-fork/pull/1",
        "https://github.com/zhaow-de/healthchecks/issues/1",
        "",
        None,
    ],
    ids=["the original project", "a look-alike name", "not a pull request", "empty", "not fetched"],
)
def test_a_pull_request_of_another_repository_fails(url):
    """Every gh call names the repository; the URL the pull request comes back with is the check that it did."""
    fails = _eval(_pr(url=url))
    assert len(fails) == 1 and fails[0].startswith("url is ") and "zhaow-de/healthchecks" in fails[0], fails


def _env(root: pathlib.Path) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
        "GIT_EDITOR": "true",
        "PATH": os.environ["PATH"],
        "HOME": str(root),
    }


def _git(cwd: pathlib.Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=_env(cwd), check=True, capture_output=True, text=True).stdout.strip()


CLOSED = "Refine-Round-Closed: 2026-09-23T00:00:00Z"


def _feat_repo(root: pathlib.Path, *, notes: bool = False) -> None:
    """A new repo whose develop, also origin/develop, holds code.py (and notes.txt "a", with `notes`), with branch feat
    checked out one commit above it, "feat: code"."""
    root.mkdir()
    _git(root, "init", "-q", "-b", "develop")
    (root / "code.py").write_text("x = 1\n")
    if notes:
        (root / "notes.txt").write_text("a\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "update-ref", "refs/remotes/origin/develop", "HEAD")
    _git(root, "checkout", "-q", "-b", "feat")
    (root / "code.py").write_text("x = 2\n")
    _git(root, "commit", "-q", "-am", "feat: code")


def _rebased_repo(
    root: pathlib.Path,
    *,
    merge_instead: bool = False,
    collide: bool = False,
    change_a_patch: bool = False,
    reword: bool = False,
    drop_a_commit: bool = False,
    stack_a_commit: bool = False,
    empty_above: bool = False,
    two_empty_above: bool = False,
) -> tuple[str, str]:
    """A branch of two patches, the second a line in notes.txt, rebased onto — or, `merge_instead`, merged with — a base
    that moved in a file of its own, or with `collide` in notes.txt at the same place, resolved by hand; returns (the
    read's tip, the head). Each other flag varies the head."""
    _feat_repo(root, notes=True)
    (root / "notes.txt").write_text("a\nb\n")
    _git(root, "commit", "-q", "-am", "docs: note b")
    read = _git(root, "rev-parse", "HEAD")
    for n in range(2 if two_empty_above else 1 if empty_above else 0):
        _git(root, "commit", "-q", "--allow-empty", "-m", f"claude(refine): round 9 closes ({n})", "-m", CLOSED)
    _git(root, "checkout", "-q", "develop")
    if collide:
        (root / "notes.txt").write_text("a\nc\n")
    else:
        (root / "other.py").write_text("y = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "docs: note c" if collide else "feat: other")
    _git(root, "update-ref", "refs/remotes/origin/develop", "HEAD")
    _git(root, "checkout", "-q", "feat")
    if merge_instead and drop_a_commit:
        _git(root, "reset", "-q", "--hard", "HEAD~1")  # after the merge, HEAD~1 would be the read's tip
    done = subprocess.run(
        ["git", "merge" if merge_instead else "rebase", "develop"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_env(root),
    )
    if collide:
        assert done.returncode != 0 and "notes.txt" in done.stdout + done.stderr, (done.stdout, done.stderr)
        (root / "notes.txt").write_text("a\nb\nc\n")
        _git(root, "add", "-A")
        if merge_instead:
            _git(root, "commit", "-q", "--no-edit")
        else:
            _git(root, "-c", "core.editor=true", "rebase", "--continue")
    else:
        assert done.returncode == 0, (done.stdout, done.stderr)
    if change_a_patch:
        (root / "code.py").write_text("x = 3\n")
        _git(root, "commit", "-q", "-a", "--amend", "--no-edit")
    if drop_a_commit and not merge_instead:
        _git(root, "reset", "-q", "--hard", "HEAD~1")
    if reword:
        _git(root, "commit", "-q", "--amend", "-m", "docs: note b, probe KILLED")
    if stack_a_commit:
        (root / "notes.txt").write_text((root / "notes.txt").read_text() + "d\n")
        _git(root, "commit", "-q", "-am", "docs: note d")
    return read, _git(root, "rev-parse", "HEAD")


def _unmoved_repo(root: pathlib.Path, extras: str, *, merge_above: bool = False) -> tuple[str, str]:
    """The read on a base that has not moved, with `extras` above it in order (`e` a refine closing commit, `x` an
    empty commit that closes nothing); `merge_above` tops the head with a merge, which `git log --no-merges` drops
    from the message list, so only a tree check can refuse the file it adds."""
    _feat_repo(root)
    read = _git(root, "rev-parse", "HEAD")
    for kind in extras:
        if kind == "e":
            _git(root, "commit", "-q", "--allow-empty", "-m", "claude(refine): round 9 closes", "-m", CLOSED)
        else:
            _git(root, "commit", "-q", "--allow-empty", "-m", "chore: an empty commit that closes no round")
    if merge_above:
        (root / "unread.py").write_text("x = 666\n")
        _git(root, "add", "unread.py")
        tree = _git(root, "write-tree")
        merge = _git(root, "commit-tree", tree, "-p", "HEAD", "-p", "refs/remotes/origin/develop", "-m", "Merge develop")
        _git(root, "reset", "-q", "--hard", merge)
    return read, _git(root, "rev-parse", "HEAD")


_SHAPES = {"rebased": {}, "merged": {"merge_instead": True}}
_MORE = {
    "changed": ({"change_a_patch": True}, "is not the read's patches on the moved base: code.py differs"),
    "resolved": ({"collide": True}, "is not the read's patches on the moved base: notes.txt differs"),
    "stacked": ({"stack_a_commit": True}, "the messages from the base to the head are not the read's"),
}


@pytest.mark.parametrize("shape", list(_SHAPES))
def test_the_arm_admits_the_read_rebased_onto_or_merged_with_the_moved_base(tmp_path, shape):
    """Driven on a real repo rather than stubbed: the arm is built on `git merge-tree` and a stub would
    measure the stub."""
    arm = gate.head_is_the_read
    read, head = _rebased_repo(tmp_path / shape, **_SHAPES[shape])
    assert arm(read, head, "origin/develop", cwd=tmp_path / shape) is True
    assert arm(read[:8], head, "origin/develop", cwd=tmp_path / shape) is True, "the body names the read by a prefix"
    assert arm(head, head, "origin/develop", cwd=tmp_path / shape) is True, "the head is its own read"


@pytest.mark.parametrize("shape", list(_SHAPES))
def test_the_arm_admits_a_refine_closing_commit_above_the_read(tmp_path, shape):
    read, head = _rebased_repo(tmp_path / shape, empty_above=True, **_SHAPES[shape])
    assert gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / shape) is True, shape


def test_the_arm_admits_the_closing_commit_on_a_base_that_has_not_moved(tmp_path):
    read, head = _unmoved_repo(tmp_path / "e", "e")
    assert gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / "e") is True


@pytest.mark.parametrize("extras", ["", "e"])
def test_the_arm_refuses_a_merge_carrying_a_file_the_read_never_saw_on_a_base_that_has_not_moved(tmp_path, extras):
    root = tmp_path / (extras or "none")
    read, head = _unmoved_repo(root, extras, merge_above=True)
    answer = gate.head_is_the_read(read, head, "origin/develop", cwd=root)
    assert isinstance(answer, str) and answer.startswith("the head's tree is not the read's"), answer


@pytest.mark.parametrize("extras", ["x", "ex", "xe", "ee"])
def test_the_arm_refuses_any_commit_above_the_read_but_one_closing_commit(tmp_path, extras):
    read, head = _unmoved_repo(tmp_path / extras, extras)
    answer = gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / extras)
    assert isinstance(answer, str) and answer.startswith("the messages from the base"), answer


def test_the_arm_refuses_a_read_commit_remade_with_a_file_the_read_never_saw(tmp_path):
    root = tmp_path / "remade"
    _unmoved_repo(root, "")
    _git(root, "commit", "-q", "--allow-empty", "-m", "claude(refine): round 9 closes")
    read = _git(root, "rev-parse", "HEAD")  # the read ends in an empty commit
    _git(root, "reset", "-q", "--hard", "HEAD~1")
    (root / "unread.py").write_text("x = 666\n")
    _git(root, "add", "unread.py")
    _git(root, "commit", "-q", "-m", "claude(refine): round 9 closes")  # the read's own message: the list still matches
    answer = gate.head_is_the_read(read, _git(root, "rev-parse", "HEAD"), "origin/develop", cwd=root)
    assert isinstance(answer, str) and answer.startswith("the head's tree is not the read's"), answer


def test_the_arm_refuses_a_second_refine_closing_commit_above_the_read(tmp_path):
    read, head = _rebased_repo(tmp_path / "two-empty", two_empty_above=True)
    answer = gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / "two-empty")
    assert isinstance(answer, str) and answer.startswith("the messages from the base"), answer


@pytest.mark.parametrize(("shape", "more"), [(s, m) for s in _SHAPES for m in _MORE], ids=lambda v: v)
def test_the_arm_refuses_a_head_that_is_more_than_the_rebase_or_the_merge(tmp_path, shape, more):
    """`resolved` is a conflict with the moved base settled by hand: what the hand wrote is a delta nobody read."""
    flags, why = _MORE[more]
    read, head = _rebased_repo(tmp_path / more, **_SHAPES[shape], **flags)
    answer = gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / more)
    assert isinstance(answer, str) and why in answer, answer


@pytest.mark.parametrize("shape", list(_SHAPES))
def test_the_arm_refuses_a_branch_that_lost_a_commit(tmp_path, shape):
    read, head = _rebased_repo(tmp_path / "lost", drop_a_commit=True, **_SHAPES[shape])
    answer = gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / "lost")
    assert isinstance(answer, str) and answer.startswith("the messages from the base"), answer


def test_the_arm_refuses_a_reworded_commit_and_names_what_it_could_not_compare(tmp_path):
    arm = gate.head_is_the_read
    read, head = _rebased_repo(tmp_path / "reworded", reword=True)
    answer = arm(read, head, "origin/develop", cwd=tmp_path / "reworded")
    assert isinstance(answer, str) and answer.startswith("the messages from the base"), answer
    why = arm("0" * 40, head, "origin/develop", cwd=tmp_path / "reworded")
    assert isinstance(why, str) and why.startswith("`git fetch`"), "an unknown read with no origin to fetch from"
    _git(tmp_path / "reworded", "update-ref", "-d", "refs/remotes/origin/develop")
    why = arm(read, head, "origin/develop", cwd=tmp_path / "reworded")
    assert isinstance(why, str) and why.startswith("`git merge-base`"), "no origin/develop to take a merge base against"


def _amended_repo(root: pathlib.Path, kind: str) -> tuple[str, str]:
    """A branch of two patches on a base that did not move, its tip re-created as `kind` says; returns (the read's tip, the head)."""
    _feat_repo(root)
    (root / "note.txt").write_text("n\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "feat: note\n\nProbe: SURVIVED")
    read = _git(root, "rev-parse", "HEAD")
    if kind == "redated":
        env = {**_env(root), "GIT_COMMITTER_DATE": "2030-01-01T00:00:00Z"}
        subprocess.run(["git", "commit", "-q", "--amend", "--no-edit"], cwd=root, env=env, check=True, capture_output=True)
    elif kind == "reworded":
        _git(root, "commit", "-q", "--amend", "-m", "feat: note\n\nProbe: KILLED, control proven")
    elif kind == "parent_reworded":
        _git(root, "reset", "-q", "--hard", "HEAD~1")
        _git(root, "commit", "-q", "--amend", "-m", "feat: code, probe KILLED")
        _git(root, "cherry-pick", read)
    elif kind == "tree_changed":
        (root / "note.txt").write_text("nn\n")
        _git(root, "commit", "-q", "-a", "--amend", "--no-edit")
    else:
        raise AssertionError(kind)
    return read, _git(root, "rev-parse", "HEAD")


@pytest.mark.parametrize("kind", ["redated", "reworded", "parent_reworded", "tree_changed"])
def test_on_an_unmoved_base_the_arm_admits_a_re_created_tip_and_refuses_a_changed_one(tmp_path, kind):
    """The head commit's own message is not enough: a reword below the tip with the tip cherry-picked back keeps the tip's
    tree and message and changes what the pre-review graded, so the messages are compared from the base, as the reads do."""
    read, head = _amended_repo(tmp_path / kind, kind)
    assert head != read
    answer = gate.head_is_the_read(read, head, "origin/develop", cwd=tmp_path / kind)
    if kind == "redated":
        assert answer is True
    elif kind == "tree_changed":
        assert answer == "the head's tree is not the read's"
    else:
        assert isinstance(answer, str) and answer.startswith("the messages from the base"), (kind, answer)


def _stub_main(monkeypatch, pr: dict, api_reply) -> tuple[list[list[str]], list[str], list[str]]:
    """main() with gh, the growth walk and the arm stubbed: no network, no fetch. Returns the gh command lines it ran,
    the order of the fetch and the arm, and the read each arm call was given."""
    calls: list[list[str]] = []
    order: list[str] = []
    reads: list[str] = []

    def fake_gh(argv: list[str]) -> str:
        calls.append(argv)
        if argv[:3] == ["gh", "pr", "view"]:
            return json.dumps(pr)
        if argv[:2] == ["gh", "api"] and argv[2].startswith(f"repos/{gate.REPO}/commits/"):
            return api_reply(argv[2].rsplit("/", 1)[1])
        raise AssertionError(argv)

    monkeypatch.setattr(gate, "_gh", fake_gh)
    monkeypatch.setattr(gate, "fetch_branches", lambda base, head_ref: order.append("fetch") or [])
    monkeypatch.setattr(gate, "head_is_the_read", lambda read, head, base: order.append("arm") or reads.append(read) or True)
    return calls, order, reads


def test_main_fetches_the_base_before_the_arm_reads_it(monkeypatch, capsys):
    """Read before the fetch, a stale clone's answer refuses the head the arm exists to admit."""
    _, order, _ = _stub_main(monkeypatch, _pr(body=_stale_body()), lambda sha: json.dumps({"sha": PREV}))
    assert gate.main(["merge-gate.py", "1"]) == 0, capsys.readouterr().out
    assert order == ["fetch", "arm"], order


def test_main_names_the_repository_on_every_gh_call(monkeypatch, capsys):
    """`gh pr view` takes `--repo`; `gh api` has no such flag and names the repository in its path."""
    calls, _, _ = _stub_main(monkeypatch, _pr(body=_stale_body()), lambda sha: json.dumps({"sha": PREV}))
    assert gate.main(["merge-gate.py", "1"]) == 0, capsys.readouterr().out
    assert [argv[:2] for argv in calls] == [["gh", "pr"], ["gh", "api"]], calls
    view, api = calls
    assert view[view.index("--repo") + 1] == "zhaow-de/healthchecks" and "1" in view, view
    assert api[2] == f"repos/zhaow-de/healthchecks/commits/{PREV[:8]}", api


def test_main_resolves_the_read_s_short_sha_before_the_clone_is_asked(monkeypatch, capsys):
    """`git fetch origin <abbrev>` cannot fetch by an abbreviated id, so GitHub is asked for the full one first; a sha
    GitHub does not know falls back to the prefix, which the clone may still hold."""
    _, _, reads = _stub_main(monkeypatch, _pr(body=_stale_body()), lambda sha: json.dumps({"sha": PREV}))
    assert gate.main(["merge-gate.py", "1"]) == 0, capsys.readouterr().out
    assert reads == [PREV]

    def unknown(sha: str) -> str:
        raise subprocess.CalledProcessError(1, ["gh", "api"], output="", stderr="HTTP 422: No commit found for SHA")

    _, _, reads = _stub_main(monkeypatch, _pr(body=_stale_body()), unknown)
    assert gate.main(["merge-gate.py", "1"]) == 0, capsys.readouterr().out
    assert reads == [PREV[:8]]


def test_main_asks_github_nothing_more_for_a_read_at_the_head(monkeypatch, capsys):
    calls, order, _ = _stub_main(monkeypatch, _pr(), lambda sha: pytest.fail("no commit lookup for a read at the head"))
    assert gate.main(["merge-gate.py", "1"]) == 0, capsys.readouterr().out
    assert [argv[:3] for argv in calls] == [["gh", "pr", "view"]] and order == ["fetch"], (calls, order)


@pytest.mark.parametrize("argv", [[], ["--fable-paths"], ["1", "2"], ["#1"], ["١"]], ids=lambda v: repr(v))
def test_main_refuses_anything_but_one_pull_request_number(monkeypatch, capsys, argv):
    """No current-branch default and no subcommand: the gate judges the pull request it is named, and runs nothing else."""
    monkeypatch.setattr(gate, "_gh", lambda argv: pytest.fail(f"gh ran: {argv}"))
    assert gate.main(["merge-gate.py", *argv]) == 2
    assert "usage: merge-gate.py <pull request number>" in capsys.readouterr().err


BOT = [{"authors": [{"login": "dependabot[bot]"}]}]
BUMP_PR = {"headRefName": "dependabot/uv/develop/django-6.1.2", "body": "Bumps django.\n\n- [x] done\n"}


def test_the_exemption_is_reachable_from_the_fetch_the_gate_actually_makes():
    """The arm's input has to be in FIELDS, or it refuses every PR of that shape instead of exempting one.

    The case below builds its PR from `FIELDS` alone, so a key the arm reads and `main()` does not fetch
    cannot be smuggled in by the test."""
    values = {"headRefName": "dependabot/uv/develop/django-6.1.2", "body": "Bumps django.\n", "headRefOid": TIP, "commits": BOT}
    # Only what the fetch returns: `update()` would put `commits` back whether or not FIELDS asks for it.
    bump = {key: values.get(key) for key in gate.FIELDS.split(",")}
    assert "commits" in bump, "FIELDS does not fetch `commits`, so the dependabot arm refuses every such PR"
    assert gate.read_line_fails(bump) == []


def test_the_fetch_carries_every_field_evaluate_reads():
    """The same trap for the other arms: a field missing from the fetch reads as None and refuses every PR."""
    for key in ("url", "baseRefName", "state", "isDraft", "mergeable", "mergeStateStatus", "reviewDecision"):
        assert key in gate.FIELDS.split(","), key
    for key in ("statusCheckRollup", "body", "headRefOid", "headRefName", "number"):
        assert key in gate.FIELDS.split(","), key


def test_a_dependabot_bump_with_no_fix_commit_needs_no_read_line():
    """A bump nobody edited has nothing for a reviewer to read, so merge-pr merges it on the other arms alone."""
    assert _eval(_pr(**BUMP_PR, commits=BOT)) == []


def test_a_dependabot_pr_carrying_a_fix_commit_takes_every_arm():
    """The exemption is for a PR with NO fix commit; one commit of mine is what withdraws it."""
    mine = [*BOT, {"authors": [{"login": "claude"}]}]
    fails = _eval(_pr(**BUMP_PR, commits=mine))
    assert len(fails) == 1 and fails[0].startswith("no 'Read before push by:")


def test_a_dependabot_pr_with_no_commit_list_fails():
    """Refused rather than exempted: an exemption that cannot be scoped is not one."""
    fails = _eval(_pr(**BUMP_PR))
    assert len(fails) == 1 and "commit list was not fetched" in fails[0]


def test_a_dependabot_branch_with_an_empty_commit_list_is_not_exempt():
    """`all()` over an empty list is True, which would exempt a PR whose commits came back as none."""
    fails = _eval(_pr(**BUMP_PR, commits=[]))
    assert len(fails) == 1 and fails[0].startswith("no 'Read before push by:")


def test_a_commit_with_no_author_entries_withdraws_the_dependabot_exemption():
    """Flattened, such a commit contributes nothing and vanishes; the exemption then survives a commit
    nothing is known about, which is not `every commit is the bot's`."""
    fails = _eval(_pr(**BUMP_PR, commits=[*BOT, {"authors": []}]))
    assert len(fails) == 1 and fails[0].startswith("no 'Read before push by:")


def test_a_missing_or_placeholder_line_fails():
    unrecorded = "no 'Read before push by: <model> at <sha>' line in the body: the whole-branch read is unrecorded"
    assert _eval(_pr(body="## Summary\n\n- [x] done\n")) == [unrecorded]
    assert _eval(_pr(body=f"Read before push by: <model> at {TIP}\n")) == [unrecorded]
    assert _eval(_pr(body="Read before push by: Claude Fable 5.1\n")) == [unrecorded]


def _read_by(model: str) -> str:
    return f"## Summary\n\nRead before push by: {model} at {TIP}\n\n- [x] done\n"


def test_a_read_below_the_floor_fails():
    fails = _eval(_pr(body=_read_by("Claude Haiku 4.5")))
    assert len(fails) == 1 and "the floor is Claude Opus or Claude Fable" in fails[0]
    assert len(_eval(_pr(body=_read_by("Claude Sonnet 4.6")))) == 1


@pytest.mark.parametrize("model", ["Claude Opus 4.8", "Claude Opus 5.5", "Claude Fable 5.1", "claude opus 5"])
def test_one_floor_admits_an_opus_or_a_fable_read_wherever_the_pr_reaches(model):
    """One floor, no path tier: what the PR touches does not change who may read it."""
    assert _eval(_pr(body=_read_by(model))) == []


@pytest.mark.parametrize(
    ("shape", "body"),
    [
        ("an HTML comment, which the rendered PR hides", "## Summary\n\n<!--\n{read}\n-->\n\n- [x] done\n"),
        ("a fenced block, which is a quotation of code", "## Summary\n\n```\n{read}\n```\n\n- [x] done\n"),
        ("a quoted line, which is somebody else's text", "## Summary\n\n> {read}\n\n- [x] done\n"),
        ("an unterminated comment, which hides the rest of the rendered page", "## Summary\n\n<!-- note to self\n{read}\n"),
        ("a line under an unterminated opener", "## Summary\n\n<!-- \n\n{read}\n\nmore prose\n"),
        (
            "a ``` block nested inside a ```` block, which is how this feature gets documented",
            "## Summary\n\n````\n```\n{read}\n```\n````\n\n- [x] done\n",
        ),
        ("an unterminated fence, which renders the rest as code", "## Summary\n\n```\n{read}\n"),
        (
            "a <details> block, collapsed until somebody clicks it",
            "## Summary\n\n<details><summary>why</summary>\n{read}\n</details>\n\n- [x] done\n",
        ),
    ],
)
def test_a_read_line_a_reader_cannot_see_is_no_recorded_read(shape, body):
    """A read claimed where the page does not show it is a read nobody can check."""
    fails = _eval(_pr(body=body.format(read=f"Read before push by: Claude Fable 5.1 at {TIP}")))
    assert len(fails) == 1 and "the whole-branch read is unrecorded" in fails[0], (shape, fails)


@pytest.mark.parametrize(
    ("shape", "above"),
    [
        ("an unterminated tilde fence", "~~~"),
        ("a tilde fence whose info string carries backticks, which CommonMark allows", "~~~`js`"),
        ("a <details> that comments out its own closer, so the element never closes", "<details><!--</details>-->"),
    ],
)
def test_no_delimiter_line_above_the_read_line_leaves_it_counting(shape, above):
    """The prefix rule refuses on a delimiter line itself, a tilde fence or a details element that comments out its own
    closer among them, rather than on a judgement about what the delimiter does."""
    body = f"## Summary\n\n{above}\n\nRead before push by: Claude Opus 5 at {TIP}\n\n- [x] done\n"
    assert _eval(_pr(body=body)), shape


def test_a_one_line_comment_above_the_line_leaves_it_counting():
    """A comment that opens and closes on one line, as the template's under `## Summary` does, hides nothing below it
    under any parse, so the prefix runs on past it."""
    body = f"## Summary\n\n<!-- A few sentences on what the change does and why. -->\n\nRead before push by: Claude Opus 5 at {TIP}\n\n- [x] done\n"
    assert _eval(_pr(body=body)) == []


def test_the_refusal_says_when_the_line_is_there_but_hidden():
    body = f"## Summary\n\n<!--\nRead before push by: Claude Fable 5.1 at {TIP}\n-->\n\n- [x] done\n"
    fails = _eval(_pr(body=body))
    assert len(fails) == 1 and "the line is in the body but inside" in fails[0]


@pytest.mark.parametrize(
    ("shape", "body"),
    [
        (
            "a </details> inside a code span, which the renderer escapes rather than honouring",
            "## Summary\n\n<details><summary>why</summary>\n\nthe `</details>` tag closes it\n\n{read}\n</details>\n",
        ),
        ("a fence opener whose info string carries <!--", "## Summary\n\n```<!--\n-->\n{read}\n```\n"),
        ("a fence opener whose info string carries <details", "## Summary\n\n```<details\n</details>\n{read}\n```\n"),
    ],
)
def test_a_closer_the_renderer_does_not_honour_does_not_reveal_the_line(shape, body):
    """A renderer settles fences before inline markup exists, and a code span is content, so the walk does too."""
    assert _eval(_pr(body=body.format(read=f"Read before push by: Claude Opus 5 at {TIP}"))), shape


@pytest.mark.parametrize(
    ("shape", "below"),
    [
        ("an inline `<!--` in prose, which renders as text", "the walker treats `<!--` as an opener"),
        ("an inline `<details>` in prose", "about `<details>` blocks and what they hide"),
        ("a four-space-indented fence, which is an indented code block", "    ```"),
        ("a line-initial ```x``` span, whose info string has a backtick", "```gh pr view```"),
        ("a comment closed with --!>, which every browser honours", "<!-- a note --!>"),
        ("a terminated fence quoting a command", "```\ngh pr view 1\n```"),
    ],
)
def test_prose_about_the_gate_does_not_refuse_the_pr_it_sits_in(shape, below):
    """A PR body that DISCUSSES comments and fences must not lose the line it carries. The prose sits BELOW the read line,
    which is where a PR puts its discussion and where the plain-prefix rule leaves it alone."""
    body = f"## Summary\n\nRead before push by: Claude Opus 5 at {TIP}\n\n{below}\n\n- [x] done\n"
    assert _eval(_pr(body=body)) == [], shape


def test_a_comment_above_the_read_line_closed_the_html_way_still_records_the_read():
    """`--!>` closes a comment in every browser, so the page shows what follows and the read line counts: a comment
    that opens and closes on its own line leaves the plain prefix running."""
    body = f"## Summary\n\n<!-- a note --!>\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n- [x] done\n"
    assert _eval(_pr(body=body)) == []


def test_a_read_line_below_a_details_that_hides_it_is_no_recorded_read():
    """The hole the plain prefix closes: a one-line `<details>` that comments out its own closer leaves the element
    open, so the page renders the read line collapsed while a walk shows it."""
    body = f"## Summary\n\n<details><!--</details>-->\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n- [x] done\n"
    fails = _eval(_pr(body=body))
    assert len(fails) == 1 and "plain prefix" in fails[0], fails


def test_a_read_line_below_a_fence_is_refused_and_told_why():
    """The cost of the prefix, stated: a body that opens a fence above its read line is refused, and the refusal
    names the prefix rather than claiming the line is missing."""
    body = f"## Summary\n\n```\ngh pr view 1\n```\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n- [x] done\n"
    fails = _eval(_pr(body=body))
    assert len(fails) == 1 and "plain prefix" in fails[0], fails


@pytest.mark.parametrize(
    "model",
    ["Claude Opus or Claude Fable", "Claude Fable or Claude Opus", "Claude Opus, Claude Fable", "Claude Opus 5 or anyone"],
)
def test_a_read_line_naming_two_readers_records_no_read(model):
    body = f"## Summary\n\nRead before push by: {model} at {TIP}\n\n- [x] done\n"
    fails = _eval(_pr(body=body))
    assert len(fails) == 1 and "more than one reader" in fails[0], fails


def test_the_template_as_shipped_records_no_read():
    """A minimal edit of the placeholder must not produce a line the gate accepts, so the shipped line and its
    marker-stripped form are both refused."""
    template = (_ROOT / ".github" / "pull_request_template.md").read_text()
    line = next(ln for ln in template.splitlines() if ln.startswith("Read before push by:"))
    stripped = line.replace("<model — ", "").replace(">", "").replace("<sha", TIP)
    for candidate in (line, stripped):
        fails = _eval(_pr(body=f"## Summary\n\n{candidate}\n\n- [x] done\n"))
        assert fails, f"the gate accepted the template's read line: {candidate!r}"


def test_the_template_with_its_read_line_filled_and_its_box_ticked_passes():
    """The template is the body open-pr starts from, so filling it in the two places it asks must be enough."""
    template = (_ROOT / ".github" / "pull_request_template.md").read_text()
    lines = template.splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.startswith("Read before push by:"))
    lines[at] = f"Read before push by: Claude Opus 5.5 at {TIP}"
    body = "\n".join(lines).replace("- [ ]", "- [x]")
    assert _eval(_pr(body=body)) == []
    assert any("checklist" in f for f in _eval(_pr(body="\n".join(lines)))), "the template ships an unticked box"


def test_every_other_arm_still_fires():
    pr = _pr(
        url="https://github.com/healthchecks/healthchecks/pull/1",
        baseRefName="main",
        isDraft=True,
        mergeable="UNKNOWN",
        mergeStateStatus="BLOCKED",
        reviewDecision="CHANGES_REQUESTED",
        statusCheckRollup=[{"conclusion": "FAILURE"}, {"state": "PENDING"}],
        body=f"Read before push by: Claude Fable 5.1 at {TIP}\n\n- [ ] not yet\n",
    )
    fails = _eval(pr)
    assert [f.split(" ")[0] for f in fails] == [
        "url",
        "base",
        "PR",
        "mergeable='UNKNOWN'",
        "mergeStateStatus=BLOCKED",
        "reviewDecision=CHANGES_REQUESTED",
        "1",
        "1",
        "PR",
    ]


def test_a_conflicting_pr_and_an_empty_rollup_each_fail_alone():
    """Conflicts are a stop, not a wait; an empty rollup is CI that has not registered yet, never a pass."""
    assert [f.split(" ")[0] for f in _eval(_pr(mergeable="CONFLICTING"))] == ["mergeable=CONFLICTING"]
    fails = _eval(_pr(statusCheckRollup=[]))
    assert len(fails) == 1 and "no CI checks reported yet" in fails[0] and "tests.yml" in fails[0], fails


def test_a_neutral_or_skipped_check_is_done_and_a_status_context_is_read_by_its_state():
    """A check run reports `conclusion`, a commit status (Coveralls posts one) reports `state`; both are read."""
    done = [{"conclusion": "SUCCESS"}, {"conclusion": "NEUTRAL"}, {"conclusion": "SKIPPED"}, {"state": "SUCCESS"}]
    assert _eval(_pr(statusCheckRollup=done)) == []
    assert [f for f in _eval(_pr(statusCheckRollup=[*done, {"state": "FAILURE"}])) if "failing" in f]
    assert [f for f in _eval(_pr(statusCheckRollup=[*done, {"state": "PENDING"}])) if "still running" in f]


@pytest.mark.parametrize("state", ["FAILURE", "ERROR", "PENDING", "EXPECTED", "SUCCESS"])
def test_the_coveralls_status_is_reported_and_never_a_stop_or_a_wait(state):
    """tests.yml keeps the Coveralls upload off the merge path and settings.yml leaves its status unrequired."""
    pr = _pr(statusCheckRollup=[{"conclusion": "SUCCESS"}, {"context": "coverage/coveralls", "state": state}])
    assert _eval(pr) == []
    assert gate.informational(pr) == [f"coverage/coveralls is {state}, never a stop or a wait"]


@pytest.mark.parametrize(
    "other", [{"context": "ci/other", "state": "FAILURE"}, {"name": "coverage/coveralls", "conclusion": "FAILURE"}], ids=repr
)
def test_another_status_and_a_check_run_under_the_coveralls_name_still_count(other):
    """The exemption is the one commit status by its context; a check run reports a `name`, never a `context`."""
    pr = _pr(statusCheckRollup=[{"conclusion": "SUCCESS"}, other])
    assert [f for f in _eval(pr) if "failing" in f] and gate.informational(pr) == []


def test_main_prints_the_coveralls_state_beside_the_verdict(monkeypatch, capsys):
    coveralls = {"context": "coverage/coveralls", "state": "FAILURE"}
    _stub_main(monkeypatch, _pr(statusCheckRollup=[{"conclusion": "SUCCESS"}, coveralls]), lambda sha: pytest.fail(sha))
    assert gate.main(["merge-gate.py", "1"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "GATE PASSED — ready to merge",
        "  informational: coverage/coveralls is FAILURE, never a stop or a wait",
    ]


def test_an_unfetched_branch_fails_the_gate():
    fails = gate.evaluate(_pr(), None, None)
    assert len(fails) == 1 and "were not fetched" in fails[0]


def test_both_branches_are_fetched_from_origin(monkeypatch):
    seen = []
    monkeypatch.setattr(
        gate.subprocess, "run", lambda args, **kwargs: seen.append(args) or gate.subprocess.CompletedProcess(args, 0, "", "")
    )
    assert gate.fetch_branches("develop", "feat/x") == []
    assert seen == [["git", "fetch", "-q", "origin", "develop", "feat/x"]]


def test_a_branch_that_cannot_be_fetched_is_one_refusal_not_a_crash(monkeypatch):
    def raise_fetch(*args, **kwargs):
        raise gate.subprocess.CalledProcessError(128, args[0], output="", stderr="fatal: couldn't find remote ref gone/branch\n")

    monkeypatch.setattr(gate.subprocess, "run", raise_fetch)
    assert gate.fetch_branches("develop", "gone/branch") == [
        "the branch could not be fetched: fatal: couldn't find remote ref gone/branch"
    ]

    def time_out(args, **kwargs):
        raise gate.subprocess.TimeoutExpired(args, 120)

    monkeypatch.setattr(gate.subprocess, "run", time_out)
    fails = gate.fetch_branches("develop", "feat/x")
    assert len(fails) == 1 and fails[0].startswith("the branch could not be fetched: ")


def test_an_unchecked_box_quoted_in_a_code_span_is_not_a_box() -> None:
    """The marker inside a code span renders as text."""
    body = f"## Summary\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\nthe gate parses `- [ ]` items\n\n- [x] done\n"
    assert not [f for f in _eval(_pr(body=body)) if "checklist" in f]


def test_an_unchecked_box_in_a_fenced_block_is_not_a_box() -> None:
    """A fenced block is code to a reader, so a list marker inside it is not a checklist item."""
    body = f"## Summary\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n```\n- [ ] not a box\n```\n\n- [x] done\n"
    assert not [f for f in _eval(_pr(body=body)) if "checklist" in f]


def test_a_real_unchecked_box_still_fails() -> None:
    """The two exemptions above must not have widened into ignoring the box the arm exists to catch."""
    body = f"## Summary\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n- [ ] not done\n"
    assert [f for f in _eval(_pr(body=body)) if "checklist" in f]


def _boxed(body: str) -> bool:
    return any(
        "checklist" in f for f in _eval(_pr(body=f"## Summary\n\nRead before push by: Claude Fable 5.1 at {TIP}\n\n{body}\n"))
    )


def test_a_real_box_inside_details_is_still_a_box() -> None:
    """GitHub renders a task list inside `<details>`."""
    assert _boxed("<details>\n<summary>later</summary>\n\n- [ ] real\n\n</details>")


def test_a_real_box_on_a_quoted_line_is_still_a_box() -> None:
    """A blockquote is visible on the page, so a box inside it counts, its marker stripped before the match."""
    assert _boxed("> - [ ] real") and _boxed("> > - [ ] nested quote")


def test_the_star_and_numbered_spellings_are_boxes() -> None:
    """Every list marker CommonMark renders opens a box, not `- [ ]` alone."""
    assert _boxed("* [ ] real") and _boxed("+ [ ] real") and _boxed("1. [ ] real") and _boxed("1) [ ] real")


def test_a_nested_box_is_a_box() -> None:
    assert _boxed("- outer\n  - [ ] inner")


def test_a_marker_that_is_only_text_is_not_a_box() -> None:
    """A code span at the line's start, and a list item whose content is a code span, both render as text."""
    assert not _boxed("`- [ ]` is the marker") and not _boxed("- `[ ]` is the marker's text")


def test_a_box_inside_a_details_html_block_is_literal_text() -> None:
    """With no blank line after `<summary>`, CommonMark keeps the HTML block open, and GitHub draws no box there."""
    assert not _boxed("<details>\n<summary>later</summary>\n- [ ] literal\n</details>")
    assert _boxed("<details>\n<summary>later</summary>\n\n- [ ] real\n\n</details>")


def test_a_box_right_after_a_closing_details_tag_is_literal_text() -> None:
    """The closing tag opens an HTML block of its own, to the next blank line."""
    assert not _boxed("<details>\n\n- [x] done\n\n</details>\n- [ ] literal") and _boxed(
        "<details>\n\n- [x] done\n\n</details>\n\n- [ ] real"
    )


def test_a_quoted_fence_or_comment_is_still_code() -> None:
    """A fenced block or an HTML comment inside a blockquote renders as code or nothing, never as a task item --
    while a plain quoted box in the same body is still a box, so this case fails in both directions."""
    assert (
        not _boxed("> ```\n> - [ ] in quoted code\n> ```")
        and not _boxed("> <!--\n> - [ ] in quoted comment\n> -->")
        and not _boxed("> > ```\n> > - [ ] nested\n> > ```")
    )
    assert _boxed("> ```\n> - [ ] in quoted code\n> ```\n\n> - [ ] real")


def test_a_quoted_fence_inside_a_fence_does_not_close_it() -> None:
    """Fence content is literal: a `> ```` line inside an open fence is code, not a quoted fence closing the block."""
    assert not _boxed("```\n> ```\n- [ ] still inside the fence\n```")


def test_a_quoted_fence_or_comment_ends_with_its_blockquote() -> None:
    """Neither takes lazy continuation, so the blockquote's end closes it and a box after it is a rendered box."""
    assert (
        _boxed("> ```\n> code\n\n- [ ] real") and _boxed("> <!--\n> hidden\n\n- [ ] real") and _boxed("> ```\n> code\n- [ ] real")
    )
    assert not _boxed("> ```\n> - [ ] in quoted code\n\n> more quote")


def test_a_quoted_fence_closed_by_an_unquoted_fence_line_opens_a_new_fence() -> None:
    """The unquoted line ends the blockquote and starts a top-level fence that runs on, so nothing after it is a box."""
    assert not _boxed("> ```\n```\n- [ ] after")


def test_a_quoted_html_block_ends_with_its_blockquote() -> None:
    """An HTML block takes no lazy continuation either, so the blockquote's end closes it and a box after it counts."""
    assert _boxed("> <details>\n- [ ] real") and not _boxed("> <details>\n> - [ ] literal")


def test_a_construct_two_quotes_deep_is_closed_by_a_line_one_quote_deep() -> None:
    """A blockquote ends at the first line with fewer markers than it opened with, not only at an unquoted line."""
    assert _boxed("> > ```\n> - [ ] real") and _boxed("> > <!--\n> - [ ] real")
    assert not _boxed("> > ```\n> > - [ ] in code\n> more") and _boxed("> > ```\n> > - [ ] in code\n> > ```\n> > - [ ] later")


def test_a_quote_marker_alone_is_content_to_an_unquoted_html_block() -> None:
    """A `>`-only line is blank inside a quoted block and content inside an unquoted one, so each is measured at its own depth."""
    assert (
        not _boxed("<details>\n>\n- [ ] box") and _boxed("> <details>\n>\n> - [ ] x") and not _boxed("> <details>\n> >\n> - [ ] x")
    )


def test_a_deeper_quoted_fence_line_inside_a_quoted_fence_is_content() -> None:
    """A fence opened one quote deep is closed by a one-quote line, not by a two-quote one, which is code to it."""
    assert not _boxed("> ```\n> > ```\n> - [ ] after") and _boxed("> ```\n> ```\n> - [ ] after")


def test_the_tail_of_a_block_comments_closing_line_is_not_a_box() -> None:
    """The line carrying `-->` is the HTML block's last line, so a marker after it is raw text on the page, not a task
    item; on the next line it is a box again."""
    assert (
        not _boxed("<!--\nhidden\n--> - [ ] box")
        and not _boxed("> <!--\n> hidden\n> --> - [ ] box")
        and _boxed("<!--\nhidden\n-->\n- [ ] box")
    )


def test_an_html_block_or_comment_admits_at_most_three_columns_of_indent() -> None:
    """Four spaces, or a tab at the line's start, before the opener is an indented code block on the page, and a box
    after it is drawn."""
    assert not _boxed("## Checklist\n\n   <details>\n- [ ] unchecked")
    assert _boxed("## Checklist\n\n    <details>\n- [ ] unchecked") and _boxed("## Checklist\n\n\t<details>\n- [ ] unchecked")
    assert _boxed("## Checklist\n\n    <!--\n- [ ] unchecked") and _boxed("- notes\n    <details>\n- [ ] unchecked")


def test_an_openers_indent_is_measured_as_the_page_measures_it() -> None:
    """A tab after a quote marker expands from the line's start, so it stops two columns past the marker and opens a
    block; a non-breaking space is content, not indent, so it opens nothing and the box after it is drawn."""
    assert not _boxed("## C\n\n> \t<details>\n> - [ ] x") and not _boxed("## C\n\n>\t<details>\n> - [ ] x")
    assert _boxed("## C\n\n <details>\n- [ ] x")


def test_a_quote_marker_is_indented_at_most_three_spaces() -> None:
    """Four spaces, a tab or a non-breaking space before `>` make the line code or a paragraph, not a quote, so a
    `<details>` there opens nothing and the quoted box on the next line is drawn; three spaces still quote."""
    assert _boxed("    > <details>\n> - [ ] x") and _boxed("\t> <details>\n> - [ ] x") and _boxed(" > <details>\n> - [ ] x")
    assert not _boxed("   > <details>\n> - [ ] x") and _boxed("   > - [ ] x")


def test_a_tab_after_a_quote_marker_before_a_fence_is_a_fence() -> None:
    """A tab expands from the line's start, so after a quote marker it stops two columns in and opens a fence; at
    the line's own start it reaches column four, which is an indented code block, and the box after it is drawn."""
    assert not _boxed("> \t```\n> - [ ] x\n> ```") and _boxed("\t```\n- [ ] x\n```")


def test_a_box_behind_an_over_indented_quote_marker_still_counts() -> None:
    """Four spaces before `>` is a list item's nested content or indented code, and the walk tracks no list; the marker
    opens nothing and the box behind it counts, so the gate is loud where the page shows code and never silent
    where it draws the box."""
    assert _boxed("- item\n    > - [ ] x") and _boxed("- item\n    > > - [ ] x")


def test_an_unknown_tag_hides_nothing_from_the_checklist() -> None:
    """`<detailsx>` is a spelling the block regex declines and the `<details` arm is the read line's alone, so for the
    checklist the tag is content and the box past the blank line counts, as the page draws it."""
    assert _boxed("## C\n\n<detailsx>\n\n- [ ] real")


def test_a_tag_condition_6_does_not_open_hides_nothing_from_the_checklist() -> None:
    """`<details-foo> text` is a paragraph on the page -- condition 6 wants a space, a tab, `>`, `/>` or the line's
    end after the tag name -- and the box on the next line interrupts it, so it counts; `<details>` and
    `<details open>` still open the block that hides theirs."""
    assert _boxed("## C\n\n<details-foo> text\n- [ ] real")
    assert _boxed("<summary-x> text\n- [ ] real")
    assert not _boxed("<details>\n- [ ] literal\n</details>")
    assert not _boxed("<details open>\n- [ ] literal\n</details>")
