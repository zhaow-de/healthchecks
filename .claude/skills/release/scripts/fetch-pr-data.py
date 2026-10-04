#!/usr/bin/env python3
"""Collect what reached develop since the last release tag, as input for the release notes.

Writes one JSON file and prints its path on stdout, alone, so whoever runs it reads the path.
Everything a human reads goes to stderr; the path comes from `tempfile`, so two runs never collide.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime

# The repository. Every gh call names it, so the script does not depend on the clone's remotes or on
# `gh repo set-default`, either of which could point gh at the original project.
REPO = "zhaow-de/healthchecks"

# `gh pr list` returns at most `--limit` rows and says nothing when it truncates, so a limit below
# the real count silently drops the oldest PRs. The number is headroom; the refusal below is the
# guard, because any fixed number is outgrown eventually.
PR_LIMIT = 2000

# Head branches of the pull requests the release skill opens into develop. They carry no change of their own.
SKIP_HEAD_PREFIXES = ("chore/back-merge-", "chore/pre-release-sync-")

TYPE_MAP = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "test": "Tests",
    "ci": "CI/Build",
    "build": "CI/Build",
}


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ERROR: {' '.join(cmd)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def parse_title(title: str) -> dict[str, str | bool]:
    """Split a Conventional Commits header into its parts."""
    match = re.match(r"^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.*)$", title)
    if match:
        return {
            "type": match.group(1),
            "type_label": TYPE_MAP.get(match.group(1), "Other Changes"),
            "breaking": match.group(3) is not None,
            "short_desc": match.group(4),
        }
    return {"type": "other", "type_label": "Other Changes", "breaking": False, "short_desc": title}


new_version = run(["cz", "version", "--project"])
release_date = datetime.now().astimezone().strftime("%Y-%m-%d")

# The last release tag on main. There is none before the first release.
tag_result = subprocess.run(["git", "describe", "--tags", "--abbrev=0", "origin/main"], capture_output=True, text=True)
last_tag = tag_result.stdout.strip() if tag_result.returncode == 0 else None
last_tag_date = datetime.fromisoformat(run(["git", "log", "-1", "--format=%aI", last_tag])) if last_tag else None

prs = json.loads(
    run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            REPO,
            "--state",
            "merged",
            "--base",
            "develop",
            "--limit",
            str(PR_LIMIT),
            "--json",
            "number,title,body,url,author,mergedAt,headRefName",
        ]
    )
)

# `>=`, not `>`: saturation is indistinguishable from a coincidence at exactly the limit.
if len(prs) >= PR_LIMIT:
    print(
        f"REFUSING: `gh pr list` returned {len(prs)} PRs against --limit {PR_LIMIT}, so the list may be "
        f"truncated and the release notes would silently lose their oldest entries. Raise PR_LIMIT in "
        f"{__file__} above the real count and re-run.",
        file=sys.stderr,
    )
    sys.exit(1)

pr_data = []
for pr in prs:
    if (pr.get("headRefName") or "").startswith(SKIP_HEAD_PREFIXES):
        continue
    merged_at = pr.get("mergedAt")
    if not merged_at:
        continue
    if last_tag_date is not None and datetime.fromisoformat(merged_at) <= last_tag_date:
        continue
    pr_data.append(
        {
            "number": pr["number"],
            "title": pr["title"],
            "description": pr.get("body", ""),
            "url": pr["url"],
            "author": pr["author"]["login"],
            **parse_title(pr["title"]),
        }
    )

# Commits that reached develop without a pull request. Pull requests are merged with a merge commit,
# so their commits are not on the first-parent chain, and the merge commits are left out by --no-merges.
commit_range = f"{last_tag}..HEAD" if last_tag else "HEAD"
commit_log = run(["git", "log", "--first-parent", "--no-merges", "--format=%h%x09%s", commit_range])
direct_commits = []
for line in commit_log.splitlines():
    short_hash, subject = line.split("\t", 1)
    direct_commits.append({"hash": short_hash, "subject": subject, **parse_title(subject)})

output = {
    "version": new_version,
    "release_date": release_date,
    "last_tag": last_tag,
    "prs": pr_data,
    "direct_commits": direct_commits,
}

with tempfile.NamedTemporaryFile(mode="w", prefix="release_pr_data_", suffix=".json", delete=False) as handle:
    json.dump(output, handle, indent=2)
    out_path = handle.name

print(f"Prepared {len(pr_data)} PRs and {len(direct_commits)} direct commits for the release notes", file=sys.stderr)
print(out_path)
