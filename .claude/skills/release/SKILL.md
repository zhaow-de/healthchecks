---
name: release
description: Cut a release of zhaow-de/healthchecks — bump the version on a release branch cut from develop, open a PR into main, merge it, push the v<version> tag, create the GitHub Release with its notes, and back-merge main into develop
allowed-tools: Bash(git add:*), Bash(git checkout:*), Bash(git tag:*), Bash(git status:*), Bash(git commit:*), Bash(git push:*), Bash(git pull:*), Bash(git fetch:*), Bash(git merge:*), Bash(git merge-base:*), Bash(git log:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git remote get-url:*), Bash(gh auth status:*), Bash(gh pr create --repo zhaow-de/healthchecks:*), Bash(gh pr view --repo zhaow-de/healthchecks:*), Bash(gh pr merge --repo zhaow-de/healthchecks:*), Bash(gh release create --repo zhaow-de/healthchecks:*), Bash(gh api repos/zhaow-de/healthchecks/:*), Bash(cz:*), Bash(uv:*), Bash(timeout:*), Bash(which:*), Bash(sed:*), Bash(grep:*), Bash(echo:*), Read, Edit, Write, AskUserQuestion
---

> **This skill has never been run end to end.** Its steps are verified against the tree, not against a real cut, so read what each one prints rather than assuming it worked. After the first real release, re-read the whole skill against what actually happened and correct it in the same branch — that read is owed once and is the only thing a first cut can give.

## Every `gh` call names `zhaow-de/healthchecks`

`gh` otherwise works out its target from the clone's remotes and its `set-default` choice, and the original project, `healthchecks/healthchecks`, accepts no AI-assisted contributions (`CLAUDE.md`): a release PR or a GitHub Release created there is a mistake that cannot be taken back quietly. So every `gh` call below carries `--repo zhaow-de/healthchecks` (an API path spells `repos/zhaow-de/healthchecks/`), `scripts/fetch-pr-data.py` passes it too, and after each create the printed URL must start with `https://github.com/zhaow-de/healthchecks/` — if it does not, stop and tell the user at once.

## Context

- Current branch: !`git branch --show-current`
- Current version: !`cz version --project 2>/dev/null || echo "(cz not installed yet — step 1 installs it)"`
- Origin: !`git remote get-url origin`
- Prerequisites: !`which gh && which uv && echo "all found" || echo "MISSING tools"`
- `cz` present already: !`which cz || echo "(absent — step 1 installs it)"`

## Instructions

1. **Verify prerequisites and install `cz`** from the context above. If not on `develop`, ask the user to switch branches first. If `gh` or `uv` is missing, report and stop — those two are the environment's, not this skill's to install. The origin above must name `zhaow-de/healthchecks`, or stop.

   `cz` is deliberately not a project dependency — a release is the only thing that uses it. Install it, then prove it answers:

   ```bash
   uv tool install commitizen
   cz version --project
   ```

   If `cz version --project` still fails after the install, stop and report — every later step that bumps or reads the version runs through it. Confirm `gh auth status` succeeds — if it returns 401, ask the user to run `gh auth refresh -h github.com` first.

2. **Update develop and check it against GitHub and against main**:
   ```bash
   git pull origin develop
   git fetch origin main
   ```

   *Unpushed commits* — the local branch can be ahead of GitHub:
   ```bash
   git log origin/develop..develop --oneline
   ```
   If this prints anything, stop and show the user: `develop` takes no direct push, so those commits reach it through a PR or not at all, and a release never ships commits that exist only in this clone.

   *Drift* — a commit on `main` that is not on `develop` will conflict in the release PR:
   ```bash
   git log develop..origin/main --oneline
   ```

   If this shows any commits, use `AskUserQuestion` to ask whether to resolve it now by merging `main` into `develop`, or to abort:
   - Show the drifting commits (so the user can see what's about to come in).
   - Options: "Yes, back-merge main → develop now" / "Abort, I'll handle it manually".

   **If the user chooses to back-merge:**
   ```bash
   git merge origin/main --no-edit
   ```

   - If the merge succeeds cleanly: `develop` takes no direct push (`.github/settings.yml`), so land it exactly as step 17 lands the back-merge — a short `chore/pre-release-sync-<timestamp>` branch, a PR into `develop` titled `Pre-release sync of main into develop` (no type, for step 17's reason), poll-then-merge. Then continue to step 3.
   - If the merge fails with conflicts, do **not** push. Investigate each conflicted file, propose a resolution to the user (typical patterns: `.cz.toml`, `pyproject.toml` and the README badge → the higher version; `uv.lock` → either side, then `uv lock`; modified-on-main but deleted-on-develop → confirm the fix exists in the replacement code, then keep the deletion), apply it, commit the merge, and land it via the same PR route. Only then continue.

   **If the user chooses to abort:** stop and report — do not proceed.

3. **Create the release branch**:
   ```bash
   git checkout -b "release/$(date +%Y%m%d-%H%M%S)"
   ```

4. **Bump the version files** — `--version-files-only`, so nothing is committed or tagged yet, and no changelog is written:
   ```bash
   cz bump --yes --version-files-only
   ```

   This computes the new version from the commit types since the last tag (rules in `.cz.toml`) and rewrites it in `.cz.toml`, `pyproject.toml` and the README `Version` badge. This repository has no `CHANGELOG.md` and gets none: never add `--changelog`. If `cz` stops with `NO_COMMITS_FOUND` or `NO_COMMITS_TO_BUMP`, there is nothing to release: switch back to `develop`, delete the release branch, and report.

5. **Refresh `uv.lock` to record the new version**:
   ```bash
   uv lock
   ```
   `cz bump` does not touch `uv.lock`; without this step `uv sync --locked`, which CI and the Docker build run, fails on the released commit.

6. **Verify the bump**. `cz bump` silently skips a `version_files` entry whose line no longer contains the previous version string, so check every home:

   ```bash
   NEW_VERSION=$(cz version --project)
   PYPROJECT_VERSION=$(grep -E '^version' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
   README_VERSION=$(grep -oE 'badge/version-v[0-9]+\.[0-9]+\.[0-9]+' README.md | head -1 | sed -E 's/.*-v//')

   if [ "$PYPROJECT_VERSION" != "$NEW_VERSION" ] || [ "$README_VERSION" != "$NEW_VERSION" ]; then
       echo "ERROR: cz bump skipped one or more version_files"
       echo "  cz says: $NEW_VERSION"
       echo "  pyproject.toml: $PYPROJECT_VERSION"
       echo "  README.md badge: $README_VERSION"
       exit 1
   fi
   if ! uv lock --check; then
       echo "ERROR: uv.lock does not match pyproject.toml"
       exit 1
   fi
   if [ -e CHANGELOG.md ]; then
       echo "ERROR: CHANGELOG.md exists; this repository keeps no changelog file"
       exit 1
   fi
   echo "OK: version $NEW_VERSION in .cz.toml, pyproject.toml, README.md and uv.lock"
   ```

   If this fails, stop and report — do not push. The usual cause of a skipped file is a version that drifted from `.cz.toml` in a past release, so the find-and-replace cannot locate the old value.

7. **Fetch the data for the release notes.** It prints the path it wrote on stdout alone; step 8 needs that path itself, since a variable dies with this command:
   ```bash
   uv run python .claude/skills/release/scripts/fetch-pr-data.py
   ```

   It lists the PRs merged into `develop` since the last release tag, and the commits that reached `develop` without a PR. If it refuses a possibly truncated `gh` list, do what its message says and re-run this step.

8. **Write the release notes**: read the data file at the path step 7 printed and follow [release-notes-format.md](release-notes-format.md), writing the notes to `.tmp/release-notes-v<VERSION>.md`, `<VERSION>` being the data file's `version`. The file becomes the GitHub Release's description in step 16; nothing is written into the repository. If the data file lists no PRs and no direct commits, there is nothing to release: `git checkout -- .cz.toml pyproject.toml README.md uv.lock`, `git checkout develop`, delete the release branch with `git branch -D`, and report.

9. **Commit the release and create the tag**:
   ```bash
   VERSION=$(cz version --project) &&
     git add .cz.toml pyproject.toml README.md uv.lock &&
     git commit -m "chore(release): bump version to v$VERSION" &&
     git tag "v$VERSION"
   ```

   One commit carries the bump and the refreshed lockfile, made from files `cz` and `uv` rewrote, so it carries no `Co-Authored-By:` trailer; the tag points at it. Later steps type the version in as `<VERSION>`.

10. **Push the release branch**:
    ```bash
    git push -u origin "$(git branch --show-current)"
    ```

11. **Create the PR** into `main`, with the description from [pr-description.md](pr-description.md) (fill in `{version}`, and paste the notes of step 8 under its last heading, so they survive on GitHub if the file is lost) written to `.tmp/release-pr-v<VERSION>.md`:
    ```bash
    gh pr create --repo zhaow-de/healthchecks --base main --head <release branch> --title "Release v<VERSION>" --assignee @me --body-file .tmp/release-pr-v<VERSION>.md
    ```
    The title carries no type, for step 17's reason.

12. **Check and store the PR URL and number** from the output of step 11: the URL starts with `https://github.com/zhaow-de/healthchecks/pull/` and ends in the number.

13. **Return to develop**:
    ```bash
    git checkout develop
    ```

14. **Auto-merge the release PR** with a merge commit (preserving the tagged bump commit on `main`). Releases run end to end without pausing to ask. Stop only if something is genuinely worth attention: the PR has conflicts, or it was closed without merging.

    **Read the suite's verdict first, by name, on the release branch's own head sha.** `.github/settings.yml` requires the `Full test suite` context on `main`, so this read is the same verdict the merge below waits on, not a second opinion. Run it as its OWN command, re-read every ~45 s, and never as one long foreground loop:

    ```bash
    SHA=$(git rev-parse "v<VERSION>")
    timeout 40 gh api "repos/zhaow-de/healthchecks/commits/$SHA/check-runs" --jq '[.check_runs[] | {n: .name, s: .status, c: (.conclusion // "")}]' | uv run python -c '
    import sys, json
    try:
        runs = json.loads(sys.stdin.read())
    except ValueError:
        runs = None
    if not isinstance(runs, list):
        print("no reading — the call did not return a check-run list; re-read it"); raise SystemExit
    run = next((r for r in runs if r["n"] == "Full test suite"), None)
    if run is None:
        print("pending (not registered yet)"); raise SystemExit
    if run["s"] != "completed":
        print(f"pending ({run["s"]})"); raise SystemExit
    print("success" if run["c"] in ("success", "neutral", "skipped") else f"failed ({run["c"]})")
    '
    ```

    A `pending` reading is this poll working: re-read it; a `pending` or a no-reading still repeating 30 minutes after the PR opened is stalled and worth attention. A `failed` reading stops the release, as do conflicts and a PR closed unmerged; before a re-cut, delete the local tag (`git tag -d v<VERSION>`), or step 9 fails on it. Only once it prints `success`, read the PR's state with per-call timeouts, as its OWN command re-issued every ~30 s, and merge as soon as GitHub reports it mergeable and not blocked by branch protection:
    ```bash
    PR_NUMBER=<the PR number from step 12>

    pr_state=$(timeout 30 gh pr view --repo zhaow-de/healthchecks "$PR_NUMBER" --json state -q .state)
    pr_mergeable=$(timeout 30 gh pr view --repo zhaow-de/healthchecks "$PR_NUMBER" --json mergeable -q .mergeable)
    pr_state_status=$(timeout 30 gh pr view --repo zhaow-de/healthchecks "$PR_NUMBER" --json mergeStateStatus -q .mergeStateStatus)
    if [ "$pr_state" = "MERGED" ]; then
        echo "PR merged!"
    elif [ "$pr_state" = "CLOSED" ]; then
        echo "PR was closed without merging — stop"
    elif [ "$pr_mergeable" = "CONFLICTING" ]; then
        echo "PR has conflicts — stop, do not merge"
    elif [ "$pr_mergeable" = "MERGEABLE" ] && [ "$pr_state_status" != "BLOCKED" ]; then
        timeout 60 gh pr merge --repo zhaow-de/healthchecks "$PR_NUMBER" --merge --delete-branch
    else
        echo "PR not ready (state: $pr_state, mergeable: $pr_mergeable, status: $pr_state_status) — re-run this block in ~30 s"
    fi
    ```

15. **Push the release tag**, after checking that the bump commit it points at is on `main`. The tag was created in step 9 and persists across the branch switch.
    ```bash
    git fetch origin main &&
      git merge-base --is-ancestor "v<VERSION>" origin/main &&
      git push origin "v<VERSION>"
    ```
    If `git merge-base` exits non-zero, the release PR was not merged with a merge commit and the tag is not on `main`: stop, do not push the tag, and report. The pushed tag starts `.github/workflows/image.yml`, which builds `ghcr.io/zhaow-de/healthchecks` and tags it `v<VERSION>`, `latest` and the commit's sha.

16. **Create the GitHub Release** with the notes of step 8 as its description. If `.tmp/release-notes-v<VERSION>.md` is missing, recover the notes from the release PR's body (`gh pr view --repo zhaow-de/healthchecks <PR number> --json body -q .body`); if they are empty, stop and do not publish.
    ```bash
    gh release create --repo zhaow-de/healthchecks "v<VERSION>" --title "v<VERSION>" --notes-file ".tmp/release-notes-v<VERSION>.md" --verify-tag
    ```
    `--verify-tag` aborts if the tag was not pushed in step 15. The command prints the Release URL: it starts with `https://github.com/zhaow-de/healthchecks/releases/`; keep it for the final report.

17. **Back-merge `main` → `develop` via a PR.** `develop` takes no direct push (`.github/settings.yml`), so the back-merge cannot be a plain `git push`. Cut a dedicated `chore/back-merge-v<VERSION>` branch off `origin/main` (a branch of its own keeps the PR's head distinct from the long-lived ref, and step 18 deletes it). Push it, open the PR, then auto-merge with the same read-then-merge pair as step 14 — the `Full test suite` reading on this branch's head, `git rev-parse origin/main`, then the merge block with this PR's number — each re-issued the same way:
    ```bash
    git fetch origin main &&
      git checkout -b "chore/back-merge-v<VERSION>" origin/main &&
      git push -u origin "chore/back-merge-v<VERSION>" &&
      gh pr create --repo zhaow-de/healthchecks --base develop --head "chore/back-merge-v<VERSION>" --title "Back-merge v<VERSION> into develop" --body "Back-merge of the \`v<VERSION>\` release from \`main\` into \`develop\` so the two branches stay in step. Opened by the \`release\` skill."
    ```
    The title has no Conventional Commits type on purpose: GitHub copies it into the merge commit, `cz` reads every line of every message, and a typed title would count as a change, so a later release with nothing new would still bump the version. Check the printed URL as in step 12.

18. **Local cleanup** — fast-forward both branches against their remotes, drop the throwaway release **and** back-merge branches, and prune stale tracking refs:
    ```bash
    git checkout develop &&
      git pull --ff-only origin develop &&
      git checkout main &&
      git pull --ff-only origin main &&
      git checkout develop &&
      git fetch --all --prune &&
      git branch -d release/<timestamp from step 3> &&
      git branch -d chore/back-merge-v<VERSION>
    ```

    Both `git branch -d` calls succeed because each branch is fully integrated via its merge commit (the release branch into `main` in step 14, the back-merge branch into `develop` in step 17). If either ever errors "not fully merged" while its PR shows merged and the remote head is gone, the work is integrated — `git branch -D` is then safe.

19. **Report success** with the release PR URL, the GitHub Release URL (printed by step 16), the back-merge PR URL, and whether the image workflow started for the tag.

## Notes

- If any step fails, stop and report the error to the user.
- Run each fenced block as written, one block at a time.
- You are already in the repo folder — do not `cd` first.
