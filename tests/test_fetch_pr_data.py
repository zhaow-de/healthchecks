"""`.claude/skills/release/scripts/fetch-pr-data.py`, the release notes' input. `cz` and `gh` are PATH stubs here; git is
real, over a scratch repository."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "release" / "scripts" / "fetch-pr-data.py"
_TAG_DATE = "2026-01-02T00:00:00+00:00"
_PRS = [
    {
        "number": 1,
        "title": "fix(api): before the tag",
        "body": "b1",
        "url": "u1",
        "author": {"login": "ann"},
        "mergedAt": "2026-01-01T10:00:00Z",
        "headRefName": "fix/before",
    },
    {
        "number": 2,
        "title": "feat(integrations): after the tag",
        "body": "b2",
        "url": "u2",
        "author": {"login": "bob"},
        "mergedAt": "2026-01-03T10:00:00Z",
        "headRefName": "feat/after",
    },
    {
        "number": 3,
        "title": "no conventional prefix",
        "body": "",
        "url": "u3",
        "author": {"login": "cid"},
        "mergedAt": "2026-01-04T10:00:00Z",
        "headRefName": "misc",
    },
    {
        "number": 4,
        "title": "chore(deps): never merged",
        "body": "",
        "url": "u4",
        "author": {"login": "dee"},
        "mergedAt": None,
        "headRefName": "dependabot/uv/develop/x",
    },
    {
        "number": 5,
        "title": "refactor(api)!: drop the v1 endpoints",
        "body": "b5",
        "url": "u5",
        "author": {"login": "eve"},
        "mergedAt": "2026-01-05T10:00:00Z",
        "headRefName": "refactor/v1",
    },
    {
        "number": 6,
        "title": "chore: back-merge main into develop",
        "body": "",
        "url": "u6",
        "author": {"login": "ann"},
        "mergedAt": "2026-01-06T10:00:00Z",
        "headRefName": "chore/back-merge-20260106",
    },
    {
        "number": 7,
        "title": "chore: sync develop before the release",
        "body": "",
        "url": "u7",
        "author": {"login": "ann"},
        "mergedAt": "2026-01-06T11:00:00Z",
        "headRefName": "chore/pre-release-sync-20260106",
    },
]
_GH_ARGS = (
    "pr list --repo zhaow-de/healthchecks --state merged --base develop --limit {limit}"
    " --json number,title,body,url,author,mergedAt,headRefName"
)


def _stub(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _repo(tmp_path: Path, *, tagged: bool) -> Path:
    """`seed`, tagged `v1.0.0` on `origin/main` when `tagged`; then on develop a direct fix, a PR's merge commit with
    the PR's own commit as its second parent, and a direct breaking feature."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_DATE": _TAG_DATE, "GIT_COMMITTER_DATE": _TAG_DATE}

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)

    def commit(name: str, subject: str) -> None:
        (repo / name).write_text(f"{subject}\n", encoding="utf-8")
        git("add", name)
        git("commit", "-qm", subject)

    git("init", "-q", "-b", "develop")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    commit("seed", "seed")
    if tagged:
        git("tag", "v1.0.0")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
    commit("direct", "fix(api): a direct fix")
    git("checkout", "-q", "-b", "feat/after")
    commit("pr", "feat(integrations): the PR's own commit")
    git("checkout", "-q", "develop")
    git("merge", "-q", "--no-ff", "-m", "Merge pull request #2 from zhaow-de/feat/after", "feat/after")
    commit("breaking", "feat!: a direct breaking change")
    return repo


def _limit() -> int:
    """The script's own `PR_LIMIT`, read from its source: the saturation case must be exactly at it."""
    match = re.search(r"^PR_LIMIT = (\d+)$", _SCRIPT.read_text(encoding="utf-8"), re.M)
    assert match, "PR_LIMIT is no longer a module-level literal in the script"
    return int(match.group(1))


def _prepare(
    tmp_path: Path, *, tagged: bool, prs: list | None = None, gh_fails: bool = False
) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _stub(bin_ / "cz", "[ \"$1 $2\" = 'version --project' ] || exit 9\necho 9.9.9")
    gh = 'printf \'%s\\n\' "$*" > "$GH_ARGS"\n'
    _stub(bin_ / "gh", gh + ("echo 'HTTP 401: Bad credentials' >&2\nexit 1" if gh_fails else 'cat "$GH_PRS"'))
    (tmp_path / "prs.json").write_text(json.dumps(_PRS if prs is None else prs), encoding="utf-8")
    env = {
        "PATH": f"{bin_}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "GH_ARGS": str(tmp_path / "gh.args"),
        "GH_PRS": str(tmp_path / "prs.json"),
    }
    done = subprocess.run(
        [sys.executable, str(_SCRIPT)], capture_output=True, text=True, cwd=_repo(tmp_path, tagged=tagged), env=env
    )
    return done, (tmp_path / "gh.args").read_text(encoding="utf-8")


def _written(done: subprocess.CompletedProcess[str]) -> Path:
    lines = done.stdout.splitlines()
    assert len(lines) == 1, f"stdout must carry the path alone, got {lines!r}"
    return Path(lines[0])


def test_the_list_names_the_repository_and_keeps_the_prs_merged_after_the_last_tag(tmp_path):
    out = None
    try:
        before = dt.date.today().isoformat()
        done, gh_args = _prepare(tmp_path, tagged=True)
        after = dt.date.today().isoformat()
        assert done.returncode == 0, done.stderr
        assert gh_args.strip() == _GH_ARGS.format(limit=_limit()), "the list names zhaow-de/healthchecks, never the remotes' pick"
        out = _written(done)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["version"] == "9.9.9" and data["release_date"] in {before, after} and data["last_tag"] == "v1.0.0"
        assert [pr["number"] for pr in data["prs"]] == [2, 3, 5], "before the tag, unmerged and the release's own PRs are out"
        feat, other, breaking = data["prs"]
        assert feat == {
            "number": 2,
            "title": "feat(integrations): after the tag",
            "description": "b2",
            "url": "u2",
            "author": "bob",
            "type": "feat",
            "type_label": "Features",
            "breaking": False,
            "short_desc": "after the tag",
        }
        assert (other["type"], other["type_label"], other["breaking"], other["short_desc"]) == (
            "other",
            "Other Changes",
            False,
            "no conventional prefix",
        )
        assert (breaking["type"], breaking["type_label"], breaking["breaking"], breaking["short_desc"]) == (
            "refactor",
            "Refactoring",
            True,
            "drop the v1 endpoints",
        )
        assert done.stderr.splitlines() == ["Prepared 3 PRs and 2 direct commits for the release notes"]
    finally:
        if out is not None:
            out.unlink(missing_ok=True)


def test_the_direct_commits_are_develop_s_own_since_the_tag_and_never_a_pr_s(tmp_path):
    """A PR is merged with a merge commit, so its commits sit off the first-parent chain and the merge itself is a
    merge; what is left is what reached develop without a PR."""
    out = None
    try:
        done, _ = _prepare(tmp_path, tagged=True)
        assert done.returncode == 0, done.stderr
        out = _written(done)
        direct = json.loads(out.read_text(encoding="utf-8"))["direct_commits"]
        assert [{k: v for k, v in c.items() if k != "hash"} for c in direct] == [
            {
                "subject": "feat!: a direct breaking change",
                "type": "feat",
                "type_label": "Features",
                "breaking": True,
                "short_desc": "a direct breaking change",
            },
            {
                "subject": "fix(api): a direct fix",
                "type": "fix",
                "type_label": "Bug Fixes",
                "breaking": False,
                "short_desc": "a direct fix",
            },
        ]
        assert all(re.fullmatch(r"[0-9a-f]{7,}", c["hash"]) for c in direct), direct
    finally:
        if out is not None:
            out.unlink(missing_ok=True)


def test_without_a_tag_every_merged_pr_and_every_direct_commit_is_kept(tmp_path):
    out = None
    try:
        done, _ = _prepare(tmp_path, tagged=False)
        assert done.returncode == 0, done.stderr
        out = _written(done)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["last_tag"] is None
        assert [pr["number"] for pr in data["prs"]] == [1, 2, 3, 5]
        assert [c["subject"] for c in data["direct_commits"]] == [
            "feat!: a direct breaking change",
            "fix(api): a direct fix",
            "seed",
        ]
        assert done.stderr.splitlines() == ["Prepared 4 PRs and 3 direct commits for the release notes"]
    finally:
        if out is not None:
            out.unlink(missing_ok=True)


def test_two_runs_do_not_collide_on_one_path(tmp_path):
    first = second = None
    try:
        for name in ("a", "b"):
            (tmp_path / name).mkdir()
        done_a, _ = _prepare(tmp_path / "a", tagged=True)
        done_b, _ = _prepare(tmp_path / "b", tagged=True)
        first, second = _written(done_a), _written(done_b)
        assert first != second
        assert first.is_file() and second.is_file()
    finally:
        for path in (first, second):
            if path is not None:
                path.unlink(missing_ok=True)


def test_a_failed_command_stops_the_script_with_its_error_and_no_path(tmp_path):
    done, gh_args = _prepare(tmp_path, tagged=True, gh_fails=True)
    assert gh_args.startswith("pr list --repo zhaow-de/healthchecks ")
    assert done.returncode == 1 and done.stdout == "", "a refusal prints no path, so there is nothing to read"
    assert done.stderr.startswith("ERROR: gh pr list --repo zhaow-de/healthchecks ") and "HTTP 401: Bad credentials" in done.stderr
    assert "Traceback" not in done.stderr


def test_a_list_as_long_as_the_limit_refuses_instead_of_writing_truncated_release_notes(tmp_path):
    limit = _limit()
    saturated = [
        {
            "number": n,
            "title": f"fix(api): pr {n}",
            "body": "",
            "url": f"u{n}",
            "author": {"login": "ann"},
            "mergedAt": "2026-01-03T10:00:00Z",
            "headRefName": f"fix/{n}",
        }
        for n in range(limit)
    ]
    done, _ = _prepare(tmp_path, tagged=True, prs=saturated)

    assert done.returncode == 1, done.stdout
    assert done.stdout == "", "a refusal prints no path, so there is nothing to read"
    assert f"--limit {limit}" in done.stderr and "REFUSING" in done.stderr


def test_one_below_the_limit_is_written_rather_than_refused(tmp_path):
    """The control on the case above: the refusal must turn on saturation, not on a long list."""
    limit = _limit()
    out = None
    try:
        nearly = [
            {
                "number": n,
                "title": f"fix(api): pr {n}",
                "body": "",
                "url": f"u{n}",
                "author": {"login": "ann"},
                "mergedAt": "2026-01-03T10:00:00Z",
                "headRefName": f"fix/{n}",
            }
            for n in range(limit - 1)
        ]
        done, _ = _prepare(tmp_path, tagged=True, prs=nearly)
        assert done.returncode == 0, done.stderr
        out = _written(done)
        assert len(json.loads(out.read_text(encoding="utf-8"))["prs"]) == limit - 1
    finally:
        if out is not None:
            out.unlink(missing_ok=True)
