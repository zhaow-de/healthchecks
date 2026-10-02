---
name: merge-pr
description: Use when a reviewed pull request into develop is ready to merge and the local clone needs cleanup afterward — e.g. "merge PR #60 and clean up". Merge-commit only (never squash or rebase), Dependabot PRs included.
allowed-tools: Bash(git status:*), Bash(git checkout:*), Bash(git pull:*), Bash(git branch:*), Bash(git ls-remote:*), Bash(git push:*), Bash(git fetch:*), Bash(gh pr list --repo zhaow-de/healthchecks:*), Bash(gh pr view --repo zhaow-de/healthchecks:*), Bash(gh pr merge --repo zhaow-de/healthchecks:*), Bash(uv run python scripts/merge-gate.py:*)
---

# merge-pr

## Overview

Merging a PR is a shared, hard-to-reverse action: gate it on verification first, then clean up local state safely.

PRs handled by this skill **always merge with a merge commit** (`--merge`) — never squash, never rebase — Dependabot's included: this repository has no separate skill for them. The merge commit is written by `gh`, so it carries no `Co-Authored-By:` trailer.

Every `gh` call below carries `--repo zhaow-de/healthchecks` (`CLAUDE.md`); with it, `gh` needs the PR number and leaves the local clone alone.

## When to use

- The user confirms a PR is reviewed and ready and asks to merge it, clean up local branches, or both.
- Finishing a Claude-authored PR after the user's review.

**Not for:** opening or editing PRs (the `open-pr` skill); merging into `main` (release-only — the `release` skill).

## Step 1 — Identify the PR

The number is the user's, or the open PR of the current branch:

```bash
gh pr list --repo zhaow-de/healthchecks --head <branch> --state open --json number,title,url
```

## Step 2 — The merge gate (STOP if ANY fails)

GitHub has no single ready-to-merge field; readiness is spread across several. Run the evaluator from the repo root of a clone whose `origin` is `zhaow-de/healthchecks`, with `gh` authenticated — it fetches the PR itself, fetches the base and head branches from `origin`, and prints `GATE PASSED` or lists every failing gate (`tests/test_merge_gate.py` drives every arm):

```bash
uv run python scripts/merge-gate.py <number>
```

`scripts/merge-gate.py` is the list of gates, and each failure line says what to resolve. One of its decisions looks redundant and is not: it refuses a red or unfinished `Full test suite` run although GitHub's branch rule does too — the rule lives in `.github/settings.yml`, which one PR can change, so do not relax the gate on its strength. The `coverage/coveralls` status is reported beside the verdict and is never a stop or a wait.

**If any gate fails:** report which one and why, ask the user to resolve it (update the branch, fix CI, re-read, tick the box), then **STOP**. Do not merge.

## Step 3 — Merge

```bash
gh pr merge --repo zhaow-de/healthchecks <number> --merge --delete-branch
```

`--merge` keeps per-commit history and the `Co-Authored-By:` trailers. `--delete-branch` deletes the head branch on GitHub; with `--repo`, `gh` neither switches branches nor deletes the local one — Steps 4 to 7 do that.

## Step 4 — Sync develop (never through a dirty worktree)

```bash
git status --porcelain
git branch --show-current
```

On `develop` with a clean tree, `git pull --ff-only`; not a fast-forward is a STOP (never a local merge commit). On `<headRefName>` with a clean tree, `git checkout develop` first. Otherwise — a dirty tree — do not switch; move the ref without touching the worktree:

```bash
git fetch origin develop:develop
```

A refspec without `+` fast-forwards a branch that is not checked out and refuses anything else, the current branch included: a refusal is a STOP and a report, never a `+` or a `--force`. This line stands in wherever the pull cannot run — never nothing: `git fetch --all --prune` alone advances `origin/develop` and leaves the local `develop` at the pre-merge commit.

## Step 5 — Delete the local branch

```bash
git branch -d <headRefName>
```

Run git from the repo root. `-d` needs only that the current branch is another one; when Step 4 left you on `<headRefName>` (a dirty tree), the delete waits with the switch. Because the PR merged with a merge commit, the branch is fully integrated and `-d` succeeds. (If `-d` ever errors "not fully merged" **and** the PR shows merged **and** the remote branch is gone, the work IS integrated — `git branch -D <headRefName>` is then safe. A Dependabot branch usually has no local copy: nothing to delete.)

## Step 6 — Confirm the remote branch is gone

```bash
git ls-remote --heads origin <headRefName>
```

Empty output = deleted (expected from Step 3). If it still prints a ref, **warn** the user, then delete it:

```bash
git push origin --delete <headRefName>
```

## Step 7 — Fetch all remotes + prune

```bash
git fetch --all --prune
```

## Report

Summarize: PR merged (or which gate stopped you), develop synced (pull, or the `develop:develop` fetch, or the refusal that deferred it), local and remote branch deleted, prune done.
