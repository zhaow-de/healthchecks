"""The merge-pr gate: every reason a pull request is not ready to merge, or GATE PASSED."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = "zhaow-de/healthchecks"
URL_PREFIX = f"https://github.com/{REPO}/pull/"
DEPENDABOT = "dependabot[bot]"
FIELDS = "number,url,headRefName,baseRefName,state,mergeable,mergeStateStatus,reviewDecision,isDraft,statusCheckRollup,body,headRefOid,commits"
READ_LINE = re.compile(r"^Read before push by: *(.+?) +at +([0-9a-f]{7,40}) *$", re.M)
FLOOR = re.compile(r"Claude (Opus|Fable)\b", re.I)


# CommonMark's fence opener: four spaces of indent is an indented code block, and only a backtick fence's info string
# bars backticks (`” ```gh pr view``` ”` is a paragraph).
_FENCE_OPEN = re.compile(r"^ {0,3}(?:(?P<run>`{3,})[^`]*|(?P<trun>~{3,}).*)$")
_FENCE_CLOSE = re.compile(r"^ {0,3}(?P<run>`{3,}|~{3,}) *$")
# A checkbox is a list item whose text opens with `[ ]`. `(?:> *)*` admits a box behind a quote marker the walk left in
# place: loud where the page draws no box, never silent where it draws one.
_UNCHECKED_BOX = re.compile(r"^\s*(?:> *)*(?:[-*+]|\d+[.)]) +\[ \]", re.M)
# A marker may be indented at most three spaces, and only spaces -- the first from column 0, a nested one from the end
# of the marker containing it, as the page measures each: this walk tracks no list item, so a marker further in opens
# nothing (see `_UNCHECKED_BOX` for what it still counts).
_QUOTE_MARKERS = re.compile(r"^(?: {0,3}> ?)+")


def _quote_depth(raw: str) -> int:
    """How many blockquotes a line sits in, by its leading markers."""
    m = _QUOTE_MARKERS.match(raw)
    return m.group(0).count(">") if m else 0


def _at_depth(raw: str, depth: int) -> str:
    """The line as the blockquote `depth` levels deep sees it: that many markers, and the indent before them, off."""
    return re.sub(rf"^(?: {{0,3}}> ?){{{depth}}}", "", raw)


# What CommonMark's condition 6 admits after the tag name; `\b` would open a block on `<details-x> text`, a paragraph.
_TAG_END = r"(?=[ \t>]|/>|$)"
_HTML_BLOCK_TAG = re.compile(r"</?(?:details|summary)" + _TAG_END)
_OPENERS = ("<!--", "<details", "</details", "<summary", "</summary")
# An inline code span renders its content as text, so a `<!--` or a `</details>` inside one is neither an opener
# nor a closer. Masking keeps the line's length, so an index found in the masked line slices the real one.
_CODE_SPAN = re.compile(r"(?P<ticks>`+)(?:(?!(?P=ticks)).)*(?P=ticks)", re.S)
_COMMENT_CLOSE = re.compile(r"--!?>")


def _outside_code_spans(line: str) -> str:
    """The line with each inline code span blanked to spaces -- same length, so offsets still line up."""
    return _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def _as_a_reader_sees_it(body: str, *, keep_collapsed: bool = False) -> str:
    """The body with everything a rendered PR hides removed: comments (terminated or not, `--!>` included), fenced
    blocks (nested or not), `<details>` blocks, and quoted lines.

    `keep_collapsed` keeps what a renderer still shows, `<details>` content and quoted lines: the read line must be plainly
    visible, so it is judged without them, and the checklist is judged with them, as GitHub draws a box inside either.

    Two rules keep this close to a renderer without becoming one: a fence is decided before inline markup is masked, as a
    renderer settles fences first (under `keep_collapsed`, with the quote markers off); and a comment or `<details>` hides
    what follows only when it opens the line and does not close on it.
    """
    visible: list[str] = []
    fence: str | None = None  # the opening run, when inside a fenced block
    in_comment = False
    in_details = False
    html_block = False  # keep_collapsed only: inside a details/summary HTML block, up to its blank line
    open_depth = 0  # keep_collapsed only: the quote depth the open fence or comment began at; 0 when not quoted
    html_depth = 0  # keep_collapsed only: the same for the open HTML block
    for raw in body.splitlines():
        # A construct opened inside a blockquote ends with it: no lazy continuation. Under keep_collapsed, columns are
        # measured with tabs expanded from the line's start, as the page counts them.
        src = raw.expandtabs(4) if keep_collapsed else raw
        depth = _quote_depth(src) if keep_collapsed else 0
        if open_depth and depth < open_depth:
            fence, in_comment, open_depth = None, False, 0
        # Every closer is read at the depth its construct opened under: a quoted fence sees a deeper-quoted line as
        # literal content, and nothing open sees every depth, so an opener is found wherever it sits.
        if not keep_collapsed or (fence is not None and not open_depth):
            line = raw
        elif open_depth:
            line = _at_depth(src, open_depth)
        else:
            line = _QUOTE_MARKERS.sub("", src)
        if html_block:
            if html_depth and depth < html_depth:
                html_block, html_depth = False, 0  # the blockquote ended: this line is read
            elif not _at_depth(src, html_depth).strip():
                html_block, html_depth = False, 0
                continue
            else:
                continue
        if fence is not None:
            run = _FENCE_CLOSE.match(line)
            if run and run.group("run")[0] == fence[0] and len(run.group("run")) >= len(fence):
                fence, open_depth = None, 0
            continue
        if in_comment or in_details:
            # Inside a comment BLOCK a renderer parses no markdown, so a `-->` written in backticks still
            # closes it; inside a `<details>` element markdown resumes after the blank line, so a span there
            # is content.
            masked = line if in_comment else _outside_code_spans(line)
            if in_comment:
                m = _COMMENT_CLOSE.search(masked)
                if not m:
                    continue
                if keep_collapsed:
                    # What follows `-->` on the HTML block's last line is raw text, never a list item: the checklist
                    # skips it, the read line's walk keeps it.
                    in_comment, open_depth = False, 0
                    continue
                line, in_comment, open_depth = line[m.end() :], False, 0
            else:
                at = masked.find("</details>")
                if at < 0:
                    continue
                line, in_details = line[at + len("</details>") :], False
        opener = _FENCE_OPEN.match(line)
        if opener:
            fence = opener.group("run") or opener.group("trun")
            open_depth = depth
            continue
        # An inline comment or details element, opened and closed on this line, takes its own span and nothing
        # more. Code spans are masked so a `<!--` written as prose about this gate is not read as markup.
        while True:
            masked = _outside_code_spans(line)
            pairs = []
            at = masked.find("<!--")
            if at >= 0:
                closer = _COMMENT_CLOSE.search(masked, at)
                if closer:
                    pairs.append((at, closer.end()))
            at = masked.find("<details")
            if at >= 0:
                close_at = masked.find("</details>", at)
                if close_at >= 0:
                    pairs.append((at, close_at + len("</details>")))
            if not pairs:
                break
            a, b = min(pairs)
            line = line[:a] + line[b:]
        # A block-level opener -- first non-space text on the line -- hides every line until its closer, or to the
        # end of the document when it has none; opened on a quoted line, it ends with the blockquote instead.
        stripped = line.lstrip()
        # An HTML block or comment admits at most three columns of indent (CommonMark, the bound `_FENCE_OPEN` spells
        # as `{0,3}`); four is an indented code block on the page, literal, hiding nothing and drawing no box. `line`
        # already has its tabs expanded and its markers off; only spaces are stripped here, since `lstrip()` would
        # take a non-breaking space, which is content.
        if keep_collapsed and stripped.startswith(_OPENERS):
            bare = line.lstrip(" ")
            if not bare.startswith(_OPENERS) or len(line) - len(bare) > 3:
                continue
        if stripped.startswith("<!--"):
            in_comment = True
            open_depth = depth
            continue
        if keep_collapsed and _HTML_BLOCK_TAG.match(stripped):
            html_block, html_depth = True, depth
            continue
        if stripped.startswith("<details") and not keep_collapsed:
            # Not under keep_collapsed: the arm above took every `<details` spelling that opens a block, so what reaches
            # here (`<detailsx>`, `<details-x> text`) ends at a blank line or a paragraph, and the checklist counts a box below it.
            in_details = True
            continue
        if stripped.startswith(">") and not keep_collapsed:
            continue
        visible.append(line)
    return "\n".join(visible)


def _before_anything_that_can_hide(body: str) -> str:
    """The body up to the first line that opens a fence, a `<details>` element, or a comment that does not close on that line.

    The read line counts only here: this cut does not rest on out-parsing a renderer, which the walk above does.
    """
    out: list[str] = []
    for raw in body.splitlines():
        stripped = raw.lstrip()
        # A comment closed on its own line hides nothing below it, and the pull-request template ships one above the read
        # line; a one-line `<details>` still breaks, since it can comment out its own closer.
        if stripped.startswith("<!--") and _COMMENT_CLOSE.search(stripped):
            out.append(raw)
            continue
        if _FENCE_OPEN.match(raw) or stripped.startswith("<!--") or stripped.startswith("<details"):
            break
        out.append(raw)
    return "\n".join(out)


def _hidden_hint(body: str, pattern: re.Pattern[str]) -> str:
    """A clause for the refusal when the line IS in the body and is hidden from the rendered page."""
    if pattern.search(body) and not pattern.search(_as_a_reader_sees_it(body)):
        return (
            " — the line is in the body but hidden from the rendered page: an HTML comment (terminated or not), a "
            "fenced block, a `<details>` block, or a quoted line"
        )
    return ""


def _prefix_hint(body: str, pattern: re.Pattern[str]) -> str:
    """A clause for the refusal when the line is visible but sits below a fence or a multi-line comment."""
    visible = _as_a_reader_sees_it(body)
    if pattern.search(visible) and not pattern.search(_as_a_reader_sees_it(_before_anything_that_can_hide(body))):
        return (
            " — the line is below a fenced block, a `<details>` block or a multi-line comment; it counts in the "
            "body's plain prefix, above any of those"
        )
    return ""


_DONE = ("SUCCESS", "NEUTRAL", "SKIPPED")
_BAD = ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "STARTUP_FAILURE")
# Commit statuses, by `context`, printed beside the verdict and never part of it: .github/settings.yml leaves them
# unrequired.
INFORMATIONAL = ("coverage/coveralls",)


def _state(check: dict) -> str:
    return (check.get("conclusion") or check.get("state") or "").upper()


def _informational(check: dict) -> bool:
    return check.get("context") in INFORMATIONAL


def informational(pr: dict) -> list[str]:
    """Each informational status in the rollup as one line with its state, for main to print; `evaluate` skips them."""
    return [
        f"{c['context']} is {_state(c) or 'without a state'}, never a stop or a wait"
        for c in pr.get("statusCheckRollup") or []
        if _informational(c)
    ]


def read_line_fails(pr: dict, kept: bool | str | None = None) -> list[str]:
    """The read is at the floor and names the head, unless the dependabot arm below exempts the PR; `kept` is
    `head_is_the_read`'s answer for the read's tip against the head, None when it was not asked."""
    if (pr.get("headRefName") or "").startswith("dependabot/"):
        commits = pr.get("commits")
        if commits is None:
            return ["the PR's commit list was not fetched, so the dependabot exemption cannot be scoped to a PR with no fix commit"]

        def _bot_only(commit: dict) -> bool:
            authors = [a.get("login") for a in (commit.get("authors") or [])]
            return bool(authors) and all(a == DEPENDABOT for a in authors)

        if commits and all(_bot_only(c) for c in commits):
            return []
    body = pr.get("body") or ""
    head = pr.get("headRefOid") or ""
    m = READ_LINE.search(_as_a_reader_sees_it(_before_anything_that_can_hide(body)))
    if not m or m.group(1).strip().startswith("<"):
        return [
            "no 'Read before push by: <model> at <sha>' line in the body: the whole-branch read is unrecorded"
            + (_hidden_hint(body, READ_LINE) or _prefix_hint(body, READ_LINE))
        ]
    model, sha = m.group(1).strip(), m.group(2)
    if not FLOOR.match(model):
        return [f"the read named in the body was by {model!r}; the floor is Claude Opus or Claude Fable"]
    # One reader. The template's placeholder names both floors; strip its markers and `Claude Opus or Claude
    # Fable` still matches the prefix, so a body that was never filled in would pass naming nobody.
    if len(FLOOR.findall(model)) > 1 or re.search(r"\bor\b", model):
        return [f"the read line names more than one reader ({model!r}): it records who read the branch, one model"]
    if head.startswith(sha):
        return []
    if kept is True:
        return []  # the read's own commits and nothing more: no delta to read
    why = f": {kept}" if isinstance(kept, str) else ""
    return [
        f"the read named in the body covers {sha[:8]}, not the head {head[:8]}{why}; read the delta or re-read, then update the line"
    ]


def evaluate(pr: dict, fetched: list[str] | None = None, kept: bool | str | None = None) -> list[str]:
    """fetched is fetch_branches()'s refusals, [] when both branches were fetched; None means the fetch was not run."""
    fails: list[str] = []
    url = pr.get("url") or ""
    base = pr.get("baseRefName")
    state = pr.get("state")
    mergeable = pr.get("mergeable")
    rollup = pr.get("statusCheckRollup") or []
    body = pr.get("body") or ""
    if not url.startswith(URL_PREFIX):
        fails.append(f"url is {url!r}, not a pull request of {REPO}: this gate judges that repository's pull requests only")
    if base != "develop":
        fails.append(f"base branch is {base!r}, not develop (feature PRs never merge to main)")
    if state != "OPEN":
        fails.append(f"state is {state!r}, expected OPEN")
    if pr.get("isDraft"):
        fails.append("PR is a draft")
    if mergeable == "CONFLICTING":
        fails.append("mergeable=CONFLICTING (conflicts) — update the branch and resolve first")
    elif mergeable != "MERGEABLE":
        fails.append(f"mergeable={mergeable!r} — GitHub is still computing; re-run in a moment, never merge on UNKNOWN")
    if pr.get("mergeStateStatus") == "BLOCKED":
        fails.append("mergeStateStatus=BLOCKED (branch protection: a required review or required check is unsatisfied)")
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        fails.append("reviewDecision=CHANGES_REQUESTED (a reviewer requested changes)")
    gating = [c for c in rollup if not _informational(c)]
    bad = [c for c in gating if _state(c) in _BAD]
    if bad:
        fails.append(f"{len(bad)} CI check(s) failing")
    pending = [c for c in gating if _state(c) not in _DONE + _BAD]
    if pending:
        fails.append(f"{len(pending)} CI check(s) still running — wait")
    if not rollup:  # the whole rollup: an informational status is still a sign that CI registered
        fails.append("no CI checks reported yet — wait for tests.yml to register")
    if _UNCHECKED_BOX.search(_as_a_reader_sees_it(body, keep_collapsed=True)):
        fails.append(
            "PR description has unchecked checklist item(s): a `- [ ]`, `* [ ]` or `1. [ ]` box, inside `<details>` or a quote too"
        )
    fails.extend(read_line_fails(pr, kept))
    if fetched is None:
        fails.append("the base and head branches were not fetched, so the read cannot be checked against them")
    fails.extend(fetched or [])
    return fails


def _git(cwd: pathlib.Path | None, *args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, timeout=120, cwd=cwd).stdout.strip()


# A refine round closes with one commit that changes no file and carries this trailer. It moves nothing a read graded,
# so it is the one empty commit admitted above the read.
REFINE_CLOSED = re.compile(r"^Refine-Round-Closed:", re.M)


def _is_refine_closing(cwd: pathlib.Path | None, sha: str) -> bool:
    """A commit above the read that cannot move what it graded: a refine round's closing commit."""
    if len(_git(cwd, "rev-list", "--parents", "-n", "1", sha).split()) != 2:
        return False
    touched = _git(cwd, "diff-tree", "--no-commit-id", "--name-only", "-r", sha).split()
    return touched == [] and bool(REFINE_CLOSED.search(_git(cwd, "log", "-1", "--format=%B", sha)))


def head_is_the_read(read: str, head: str, base: str, cwd: pathlib.Path | None = None) -> bool | str:
    """True when `head` carries the read's own commits and nothing more, by the checks below — one refine closing
    commit set aside — on the base they were read on, or on one that moved under them; otherwise a string naming
    the check that failed, or what the arm could not compare."""
    try:
        try:
            read = _git(cwd, "rev-parse", "--verify", "--quiet", f"{read}^{{commit}}")
        except subprocess.CalledProcessError:
            _git(cwd, "fetch", "-q", "origin", read)
            read = _git(cwd, "rev-parse", "--verify", "--quiet", f"{read}^{{commit}}")
        old_base = _git(cwd, "merge-base", base, read)
        new_base = _git(cwd, "merge-base", base, head)
        # A merge of the base carries no patch of its own; the tree check reads it.
        read_msgs = [
            m.strip() for m in _git(cwd, "log", "--no-merges", "--format=%B%x00", f"{old_base}..{read}").split("\x00") if m.strip()
        ]
        cells = _git(cwd, "log", "--no-merges", "--format=%H%x00%B%x00", f"{new_base}..{head}").split("\x00")
        head_msgs = [(cells[i].strip(), cells[i + 1].strip()) for i in range(0, len(cells) - 1, 2)]
        extra = [sha for sha, msg in head_msgs if msg not in read_msgs]
        admitted = set(extra) if len(extra) == 1 and _is_refine_closing(cwd, extra[0]) else set()
        if [msg for sha, msg in head_msgs if sha not in admitted] != read_msgs:
            return (
                "the messages from the base to the head are not the read's, a commit reworded, added or dropped: a reword "
                "takes `pre-review` over the amended commits and `re-review` over `<read>..<head>`"
            )
        if old_base == new_base:
            same = subprocess.run(["git", "diff", "--quiet", read, head], capture_output=True, text=True, timeout=120, cwd=cwd)
            if same.returncode == 1:
                return "the head's tree is not the read's"
            if same.returncode != 0:
                return f"`git diff` exited {same.returncode}: {same.stderr.strip() or 'no stderr'}"
            return True  # re-dated, re-signed or re-created on the same base: the tree and the messages the read graded
        merged = subprocess.run(
            ["git", "merge-tree", "--write-tree", f"--merge-base={old_base}", read, new_base],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
        )
        if merged.returncode not in (0, 1) or not merged.stdout.strip():
            return "`git merge-tree` could not merge the read onto the moved base"
        tree = merged.stdout.splitlines()[0].strip()  # exit 1 is a conflict: the tree still prints first, its markers inside
        # A conflict resolved by hand is a delta nobody read, so any path that differs is a refusal.
        differs = _git(cwd, "diff", "--name-only", tree, head).splitlines()
        if differs:
            return f"the head is not the read's patches on the moved base: {differs[0]} differs"
    except subprocess.TimeoutExpired as exc:
        return f"`git {exc.cmd[1]}` timed out"
    except subprocess.CalledProcessError as exc:
        return f"`git {exc.cmd[1]}` exited {exc.returncode}: {(exc.stderr or '').strip() or 'no stderr'}"
    return True


def _gh(argv: list[str]) -> str:
    """Run one `gh` command line, written out whole at its call site so the repository it names is visible there."""
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=60).stdout


def fetch_branches(base_ref: str, head_ref: str) -> list[str]:
    """Fetch both branches, which head_is_the_read reads; a branch that cannot be fetched is one refusal, never a crash."""
    try:
        subprocess.run(
            ["git", "fetch", "-q", "origin", base_ref, head_ref], check=True, capture_output=True, text=True, timeout=120
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = ((getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or "") or "").strip()
        return [f"the branch could not be fetched: {detail or str(exc)}"]
    return []


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not (argv[1].isascii() and argv[1].isdigit()):
        print("usage: merge-gate.py <pull request number>", file=sys.stderr)
        return 2
    pr = json.loads(_gh(["gh", "pr", "view", argv[1], "--repo", REPO, "--json", FIELDS]))
    m = READ_LINE.search(_as_a_reader_sees_it(pr.get("body") or ""))
    head = pr.get("headRefOid") or ""
    fetched = fetch_branches(pr["baseRefName"], pr["headRefName"])  # first: head_is_the_read reads origin's base and head
    kept = None
    if m and head and not head.startswith(m.group(2)):
        try:
            read = json.loads(_gh(["gh", "api", f"repos/{REPO}/commits/{m.group(2)}"])).get("sha") or m.group(2)
        except subprocess.CalledProcessError, subprocess.TimeoutExpired:
            read = m.group(2)  # a tip GitHub never saw, or a fetch that failed or timed out: the clone is asked by the prefix
        kept = head_is_the_read(read, head, f"origin/{pr['baseRefName']}")
    fails = evaluate(pr, fetched, kept)
    if fails:
        print("GATE FAILED:")
        for fail in fails:
            print("  - " + fail)
    else:
        print("GATE PASSED — ready to merge")
    for note in informational(pr):
        print("  informational: " + note)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
