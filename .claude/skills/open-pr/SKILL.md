---
name: open-pr
description: Use when creating a GitHub pull request or editing a PR title or body — load BEFORE running gh pr create or any PR-body edit.
---

# open-pr

## Step 0 — the gate

A PR delivers **one completed, nameable component**, and it is opened on the user's word. Before anything below: (1) name the component — the branch name says what it is; if you cannot name it, stop and report the branch ready-or-not instead. (2) Confirm it is complete. (3) The user's explicit say-so for this PR: a green commit or a finished branch is not a reason, and a different component is not a reason to reuse an open PR. A change that lands while the PR is open is a commit on it, not a second PR. No draft is opened unasked: CI (`.github/workflows/tests.yml`) runs on pull requests alone, so until the user asks for the PR the author runs `uv run ./manage.py test` and `uv run pytest` before each push.

## Every `gh` call names `zhaow-de/healthchecks`

`gh` otherwise works out its target from the clone's remotes and its `set-default` choice, and the original project, `healthchecks/healthchecks`, accepts no AI-assisted contributions (`CLAUDE.md`). So every `gh` call below carries `--repo zhaow-de/healthchecks` right after the subcommand, every API path spells out `repos/zhaow-de/healthchecks/`, and the URL a create prints must start with `https://github.com/zhaow-de/healthchecks/pull/` — if it does not, stop and tell the user at once. `git remote get-url origin` names `zhaow-de/healthchecks` before the push, or stop.

## The read before the push

A different agent from the author reads the whole branch before the push that the PR carries. The reads are the saved workflows `pre-review`, `review` and `re-review`; each takes `repo` (the absolute path of the checkout), `range`, `tip` (the full sha, `git rev-parse HEAD`) and `reportDir`, here `<repo>/.tmp/reads/<branch>` with each `/` of the branch name written `-`. Create the directory first (`mkdir -p`); `.tmp/` is ignored and disposable. The ledger in it is written and read by `scripts/review-ledger.py` alone, run from the repo root, and the workflows log the exact command for each row:

1. **`pre-review`** over `origin/develop..<tip>` (`git fetch origin develop` first). Act on its rows — a trim, cut or fix is a new commit — and pre-review the new commits until it reports ready; append each run's row with `uv run python scripts/review-ledger.py append <reportDir> --kind pre-review --range <range> --tip <tip>`.
2. **`review`** over the whole branch, `origin/develop..<tip>`, once it is complete: pass as `ledger` the array `uv run python scripts/review-ledger.py read <reportDir> --tip <tip>` prints. Save the `refutation` it returns to a file under `<reportDir>`, then `uv run python scripts/review-ledger.py append <reportDir> --kind review --range <range> --tip <tip> --refutation <that file> --report <reportDir>/behaviour-<tip>.md --report <reportDir>/guards-<tip>.md`.
3. **Fixes**: the standing Critical and Important findings are fixed in new commits, never an amend, grouped by area into a few commits rather than one per finding. `pre-review` over the fix range `<read tip>..<new tip>` and its row appended; then **`re-review`** over that range with `prior` (the standing Critical and Important findings as `{id, severity, path, line, claim}`), `left` (each one left on purpose, by `#<id>` with its reason), `reported` (the Minors) and the ledger read at the new tip; its row appended as review's is, with its one `--report <reportDir>/re-review-<tip>.md`. At most two re-reviews per branch: a Critical or Important open after the second goes to the user.

`review` and `re-review` inherit the session's model unless `model` names `opus` or `fable`; the read line names it.

## Title

A Conventional Commits header for the PR as a whole — `<type>(<scope>): <short description>`. GitHub copies the title into the merge commit's body, where `cz bump` reads its type, and the `release` skill sorts the release notes by it; a title of another shape lands under "Other Changes".

## Body

Write the body to a file under `.tmp/` and pass it with `--body-file`, mirroring `.github/pull_request_template.md`, which `--body-file` bypasses.

**Required, in order:**

1. `## Summary` — one or two sentences on what the change does and why.
2. `Read before push by: Claude Opus at <sha>` (or `Claude Fable`; the gate refuses a body without the `Claude` prefix) — one line, plain text above any fenced block, multi-line comment or `<details>`, naming the model that read the whole branch before the push and the tip it read: `review` over `origin/develop..HEAD`, or `re-review` over the fix range before the push that carries the fixes. `merge-pr`'s gate refuses a body whose sha is not the PR head, so a commit pushed after the read takes a read of the delta and an updated line; a refine round's closing commit, a re-dated head and a clean rebase onto a moved base pass without one, and a conflict resolved by hand is a delta nobody read. A Dependabot PR whose every commit is the bot's needs no line.
3. `## Guidance changes` — when `git log origin/develop..HEAD --format='%h %s' | grep '^[0-9a-f]* claude('` prints a line, that output verbatim under this heading, one commit per line; omitted when it prints nothing.
4. The flexible middle (below).
5. `## Checklist` — ``- [x] Tests pass (`uv run ./manage.py test` and `uv run pytest`)``, ticked once both ran green on the pushed head; CI runs them again on the PR.
6. The co-author line (below), after a `---` line.

**Flexible middle:** between the lines above and Checklist, add whatever sections fit the change — a *menu, not a mandate*: `## Changes`, `## Test plan`, `## Migration / compatibility`, `## Risks`, `## Screenshots`, `## Out of scope`, `## Follow-ups`. A trivial PR may add none, a large one several. Every `## Changes` bullet is derived from the file-scoped diff at write time — `git diff <base> <tip> -- <path>` — never from a working summary of the branch; and a body claim about the branch names the class it covers, never a count, because the count is false the moment the next commit lands under it. A PR description is not re-read after the merge, so a follow-up it names also lands where it will be acted on, or is dropped in so many words.

**Co-author line:** one line listing the distinct Claude models that co-authored the branch's commits, names only, joined with `; ` — `Co-Authored-By: Claude Opus 5.5; Claude Sonnet 5`. Derive it, and regenerate it whenever commits are added:

```bash
git log origin/develop..HEAD --pretty='%(trailers:key=Co-authored-by,valueonly)' | sed '/^$/d' | sed 's/ <[^>]*>//' | awk '!seen[$0]++' | paste -sd , - | sed 's/,/; /g'
```

## Creating the PR

Push the branch (`git push -u origin <branch>`), then create the PR with the head named, so `gh` neither guesses it nor offers to push:

```bash
gh pr create --repo zhaow-de/healthchecks --base develop --head <branch> --title '<title>' --body-file .tmp/pr-body.md
```

Keep the PR number from the URL it prints, after checking that URL. The turn does not end at the number: start the CI watch in the same turn — one backgrounded command re-reading the `Full test suite` check-run of the pushed sha with a per-call `timeout`, ending at that run's conclusion and exiting non-zero on anything but success, so the exit code carries the verdict:

```bash
SHA=$(git rev-parse HEAD)   # the pushed head; a later push restarts the watch on its sha
# Bounded at 40 reads, ~30 min: `gh` writes an error body to stdout, which matches no state, so an unbounded loop
# on a revoked token or a wrong sha re-reads forever. `tr` lowercases where `${R,,}` is bash alone.
for i in $(seq 1 40); do R=$(timeout 40 gh api "repos/zhaow-de/healthchecks/commits/$SHA/check-runs" --jq '.check_runs[] | select(.name == "Full test suite") | "\(.status) \(.conclusion // "")"' | tr '[:upper:]' '[:lower:]'); case "$R" in completed*) break ;; esac; sleep 45; done; echo "${R:-no reading}"; case "$R" in *success*) true ;; *) false ;; esac
```

## Editing a PR body

`gh pr edit --repo zhaow-de/healthchecks <N> --body-file …` can exit 0 without applying the change on some `gh` versions. Update through REST instead, and read the edit back — never trust the exit code:

```bash
uv run python -c 'import json, sys; print(json.dumps({"body": open(sys.argv[1]).read()}))' .tmp/pr-body.md > .tmp/pr-body.json
gh api repos/zhaow-de/healthchecks/pulls/<N> -X PATCH --input .tmp/pr-body.json
gh pr view --repo zhaow-de/healthchecks <N> --json title,body
```

A title goes the same way, as `{"title": "…"}`. A stale body matters: the `merge-pr` gate reads the read line and the boxes from it.

## Target branch

PRs target **`develop`**; PRs into `main` are the `release` skill's.
