---
name: refine-rules
description: Use before editing CLAUDE.md, a rule under .claude/rules/, a skill file or a saved workflow, and for `/refine-rules round`, the guidance round.
model: fable
---

# refine-rules

## Before you write guidance

The always-loaded set — `CLAUDE.md`, `.claude/rules/*.md`, every skill's `name:` and `description:` lines, and every saved workflow's `name`, `description` and `whenToUse` strings — is paid by every session on every turn; a skill's body, and a workflow's, is paid only when it loads. Measure it, never recall it: `wc -c CLAUDE.md .claude/rules/*.md`, plus those name, description and workflow strings.

A line lands on one of four grounds, or it does not land:

1. a mechanical check enforces it — a test, a hook, a gate arm, a script's refusal — and the line names the check;
2. it is safety-critical: it keeps anything from being opened in the original project, or guards stored data or a secret;
3. it is a recurring cross-session failure with an existing check;
4. the user kept it by name.

Net ambient growth is the user's word, in a round or outside one: a session cannot grant its own. A guidance change rides its own `claude(<scope>)` commit and may share the payload's branch.

**The protected set** — `CLAUDE.md`'s lines that nothing is ever opened in `healthchecks/healthchecks`, that every `gh` command names `--repo zhaow-de/healthchecks`, and that `main` is release-only and never rewritten. An edit to one of them takes the user's explicit word for that edit, in a round or outside one; the round's dispositions and Step 5's classification do not stand in for it, and no condensing weakens them: the round must not be able to quietly loosen the rules that police it.

Three tests on the line as written:

- **The universal test.** A bullet that says *every*, *never*, *always*, *only*, *any* or *cannot* names its set and its count — `(set: …; count: `scripts/count-list.sh <entry>`)` — or declares `(no count command: <why nothing in the tree records it>)`. The test applies to every list item of `CLAUDE.md` and `.claude/rules/*.md`, code set aside; the word counts whole, so `read-only` carries *only*. An entry is a `c_<name>` function in `scripts/count-list.sh` plus its `emit "<entry>"` line.
- **The trade.** The ambient set grows only for a stated reason, which the commit message gives with the measured growth in bytes; a deletion of equal size in the same commit is the cheaper trade. A growth with no reason worth one line is a line that does not belong.
- **Placement.** A numbered skill step is its own command in its own shell, so a name one step defines is gone in the next: a step hands its successor a printed value or a file, never a variable. What every session must do on every turn goes to `CLAUDE.md`; what it must do in the application code goes to `.claude/rules/hc-code.md`; a procedure goes to the skill step where it runs; a claim a check can make goes to the check, and the sentence goes. A ruling on how work is performed lands its imperative on the surface that performs it — the skill step, the hook, the script — in the same change; a ruling that lives only in a conversation or a memory item is invisible at execution time. A skill's description is ambient — write it as the trigger and nothing else.

A lesson goes to the inbox through `scripts/append-lesson.py`, never straight into a rule: the round below is where a lesson becomes guidance, under the trade above.

## The round — `/refine-rules round`

A joint session, the user's word closing every disposition; undecided is the default. One open decision set at a time: fact-collection may run ahead, but the next step's findings are held until the previous step's dispositions close. Any "later" outcome — a deferred hook, a parked finding, a postponed graduation — is written in the same step as a standing memory item in Step 1's shape, never only in the round's report. A hook is proposed case-by-case and shown to the user before it lands.

### Step 1 — Harvest

The candidate set is the inbox records themselves: every `<session>.jsonl` directly under `.local/agent-lessons/` in the main checkout — the first row of `git worktree list`, where `scripts/append-lesson.py` writes from a worktree too; `main.jsonl` is this repository's one session. List them with `find <main checkout>/.local/agent-lessons -maxdepth 1 -name '*.jsonl'` (a bare glob that matches nothing is an error in zsh), and run `scripts/check-agent-lessons.py` on each first, a malformed line being a finding, not a skip. Read per session and grouped by class into the round's table, id `<session>:<ts>`. A harvested inbox rotates to `.local/agent-lessons/harvested/<round-date>/` in the same step — that rotation is the archive — so the next round starts from empty inboxes and no record is harvested twice.

- **Watermark**: `git log -1 --grep='^Refine-Round-Closed:' --format=%cI` — the previous round's closing commit, found by its `Refine-Round-Closed:` trailer. The commit's date is the boundary, not the trailer's value, which is stamped before the commit lands. No match ⇒ first round: harvest every inbox whole plus the trailing two weeks.
- **Other sources since the watermark**: `git log` over `CLAUDE.md` and `.claude/`; merged PR bodies (`gh pr list --repo zhaow-de/healthchecks --state merged --base develop --json number,title,body,mergedAt`); lessons either party names in the session.
- **The memory walk** is the standing items the memory dir holds — `MEMORY.md`'s index — the only files Step 2 stages and Step 5 deletes. An item that stays there keeps the memory-file shape: frontmatter `name`/`description`/`metadata.type`, body with **Why** and **How to apply**; a memory that CONFERS a capability names whom it belongs to — read by a session it does not describe, it hands over an authority nobody granted; a prohibition is safe subjectless.
- A candidate that duplicates a standing memory item updates that item instead.

### Step 2 — Graduate (joint)

Walk every candidate in the round's table and every standing memory item alike. Per item, exactly one disposition, the user's word closing each:

| Disposition | Action |
|---|---|
| → CLAUDE.md or a rule | The shortest imperative form lands there, under the edit contract above — the guard takes the trade and the universal test at the commit |
| → an existing skill | Lands at the step where it applies |
| → a new skill | Only with the description-is-ambient cost measured and acknowledged |
| → a hook proposal | Shown to the user; on approval, lands with the settings change |
| stays in memory | Personal or session-scoped — not repo-worthy; the default when undecided. An inbox record that stays is written as a memory file in Step 1's shape |
| dropped | With the user's word; a standing item's file is deleted at Step 5, an inbox record rests in the archive |

A graduated standing item's file is **staged** — moved to `graduated/<round-date>/` under the memory dir — never deleted here: memory is unversioned, and an unverified landing must not be the only copy's obituary; a graduated inbox record is already archived by Step 1's rotation. Record every graduation in a table: *item → disposition → landing path*. Deletion is Step 5's last action.

### Step 3 — Count list

Run `scripts/count-list.sh`, with the local `develop` fast-forwarded first (`git fetch origin develop:develop` while another branch is checked out): `non-pr-commits-on-develop` reads that ref by name. It prints one line per entry — the entry's name and today's value; a surviving universal in `CLAUDE.md` and `.claude/rules/` names its set in prose and its entry as `count: `scripts/count-list.sh <entry>``, and the script's `c_` function behind that entry is the command; a counter that names its hits does so on stderr.

- **A non-zero count is a finding.** Resolve a finding in the round: fix the practice, narrow the rule, or delete the rule.
- **An `ERROR` line is its own finding** — the script exits 2 and names the entries that errored on stderr; a count that cannot run is not a count of 0.
- **A universal with no entry beside it is the finding**: it is given a set and an entry in this round, or it goes.

Output is a findings table, resolved jointly; the values live in that table, never in the corpus lines.

### Step 4 — Condense

**Load `references/principles.md` now** — the principles there govern every edit in this step. Work the biggest always-loaded offenders first (`wc -c CLAUDE.md .claude/rules/*.md | sort -n`, then the skill descriptions and the workflows' listed strings by length). The protected set's per-edit word applies throughout.

### Step 5 — Verify

In order, all five before anything is deleted:

- **(a) Cold read** — the `review` workflow over the round's range at the tip the PR body names, after its `pre-review`, as `open-pr`'s read section runs them, read for weakened or lost invariants on every changed line, not only removals: rewording can weaken a `Never` without deleting it. A commit made after that read re-opens it, save the closing commit below, which `merge-pr`'s gate admits past the read: no read line covers its message, so it takes a `pre-review` over itself alone before the push.
- **(b) Modal floor** — `grep -cE 'Never|never|MUST|must|only|refuse|explicit' CLAUDE.md .claude/rules/*.md` before vs after; any decrease itemized and justified line by line, never summarized.
- **(c) Graduation table check** — every row's content verified present at its named landing path, staged files included.
- **(d) Net measurement** — the always-loaded bytes (see above) before vs after; the delta goes in the closeout.
- **(e) Commit gate** — `uv run pre-commit run -a` until clean.

Then, and only then, delete the staged memory files and update `MEMORY.md`.

### Closing

The round closes with one commit that changes no file (`git commit --allow-empty`), typed `claude(refine)`: Step 5 (d)'s delta in its body as prose; then the watermark trailer, `Refine-Round-Closed: <ISO-8601 UTC>`, below `Co-Authored-By:`, which opens the trailer block. Verify end-to-end before reporting done:

```bash
test "$(git log -1 --grep='^Refine-Round-Closed:' --format=%H)" = "$(git rev-parse HEAD)"
```
