#!/usr/bin/env bash
# One line per entry -- its name and today's value -- for every count the corpus names by entry; a universal with no entry beside it is the finding.
# Usage: count-list.sh [entry...] -- every entry, or only the named ones; a name no entry answers to is exit 2.
# Needs bash 4.4 or newer (an empty "${wanted[@]}" is an unbound variable under `set -u` before it; macOS ships 3.2 as /bin/bash).
set -uo pipefail

errors=()
wanted=()
seen=()

# The count a command printed: pytest's own summary line, else the last line it wrote.
value_of() {
  local raw="$1" summary
  summary="$(printf '%s\n' "$raw" | grep -oE '[0-9]+ passed' | tail -n 1)"
  if [ -n "$summary" ]; then
    printf '%s' "$summary"
    return 0
  fi
  printf '%s\n' "$raw" | tail -n 1 | tr -d '[:space:]'
}

# emit <name> <count-command function>... — one output line, the values joined by "; ".
# grep and the pipelines built on it exit 1 for "no matches", which is a zero count and not an
# error; 2 and above is the command itself failing, and a function that returns 2 says so too.
emit() {
  local name="$1"
  shift
  if [ "${#wanted[@]}" -gt 0 ]; then
    local w hit=0
    for w in "${wanted[@]}"; do [ "$w" = "$name" ] && hit=1; done
    [ "$hit" = 1 ] || return 0
  fi
  seen+=("$name")
  local fn raw status value joined=""
  for fn in "$@"; do
    raw="$("$fn")"
    status=$?
    if [ "$status" -ge 2 ]; then
      errors+=("${name} (exit ${status})")
      printf '%s\tERROR\n' "$name"
      return 0
    fi
    value="$(value_of "$raw")"
    if ! printf '%s' "$value" | grep -qE '^[0-9]+( passed)?$'; then
      errors+=("${name} (unreadable output)")
      printf '%s\tERROR\n' "$name"
      return 0
    fi
    if [ -z "$joined" ]; then joined="$value"; else joined="${joined}; ${value}"; fi
  done
  printf '%s\t%s\n' "$name" "$joined"
}

# A rule's window is a full INSTANT, never a bare date: `git log --since=2026-10-05` is approxidate and fills
# the missing time from the run's clock, so a bare date slides the window through the day.
# Every change reaches develop through a pull request from this instant on. The commits that set this
# repository up went to develop directly, and every one of them is older.
PR_RULE_SINCE="2026-10-05T00:00:00Z"

# develop's first-parent commits since PR_RULE_SINCE that are not a pull request's merge commit -- two parents
# or more and GitHub's `Merge pull request #<n> from ...` subject. A direct push, a fast-forward and a merge made
# locally each count. It reads the local `develop` ref by name, so fetch and fast-forward it for today's value;
# a checkout without that ref is an error, never a 0.
c_non_pr_commits_on_develop() {
  if ! git rev-parse --verify --quiet develop >/dev/null; then
    echo "count-list: this checkout has no develop ref, which non-pr-commits-on-develop reads by name" >&2
    return 2
  fi
  git log --first-parent develop --since="$PR_RULE_SINCE" --format='%P%x09%s' |
    awk -F'\t' '{ if (!(split($1, parents, " ") >= 2 && $2 ~ /^Merge pull request #[0-9]+ from /)) n++ } END { print n + 0 }'
}

# The `gh` invocations in the tracked files under .claude/ and scripts/ that do not name this repository:
# neither `--repo zhaow-de/healthchecks` (or `--repo=`) nor an api path holding `repos/zhaow-de/healthchecks/`.
# `gh auth ...` is account-scoped and exempt. An invocation is `gh <command>` in a command position, read to the
# end of its command: the first unquoted `|`, `;`, `&`, backtick or unmatched `)`, or the end of its line once
# backslash continuations are joined -- so `--repo` belongs on the command's own logical line.
#   Markdown is read as code alone, fenced blocks and inline spans; Python as list and tuple literals from their
#   `"gh"` item on and strings starting `gh <command>`; every other file line by line, a shell comment line aside.
# This script is outside the set: its own text spells the forms it counts. Each counted call is named on stderr.
c_gh_calls_without_the_repo() {
  uv run python - <<'GHCALLS'
import ast
import pathlib
import re
import subprocess
import sys

REPO = "zhaow-de/healthchecks"
COMMANDS = (
    "agent-task|alias|api|attestation|auth|browse|cache|co|codespace|completion|config|extension|gist|gpg-key|help|"
    "issue|label|org|pr|preview|project|release|repo|ruleset|run|search|secret|ssh-key|status|variable|workflow"
)
COMMAND = re.compile(rf"(?<![\w./$-])gh[ \t]+({COMMANDS})(?![\w-])")
CARRIES = re.compile(rf"--repo(?:[ \t]+|=)[\"']?{re.escape(REPO)}[\"']?(?![\w./-])|repos/{re.escape(REPO)}/")
FENCE = re.compile(r"^\s*(```|~~~)")
SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
SHELL = re.compile(r"^#!.*\b(ba|z|da|k)?sh\b")


def extent(text: str, start: int) -> str:
    """The command from `gh` to its end: the first unquoted |, ;, & (not a redirection's), unmatched ),
    newline or backtick -- a backtick or newline ends it inside quotes too, where a prompt's prose apostrophe
    would otherwise read the rest of the file as one quoted word."""
    quote, depth, i = "", 0, start
    while i < len(text):
        c = text[i]
        if c in "`\n":
            break
        if c == "\\" and text[i + 1 : i + 2] == "`":
            break  # an escaped backtick in a JavaScript template literal closes a code span all the same
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "'\"":
            quote = c
        elif c == "\\":
            i += 2
            continue
        elif c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif c in "|;":
            break
        elif c == "&" and text[i - 1 : i] != ">" and text[i + 1 : i + 2] != ">":
            break
        i += 1
    return text[start:i]


def shell_form(text: str, line: int, where: str) -> list[str]:
    """Each uncarried invocation in one logical line of text, as `path:line: command`."""
    found = []
    for m in COMMAND.finditer(text):
        command = extent(text, m.start())
        if m.group(1) != "auth" and not CARRIES.search(command):
            found.append(f"{where}:{line}: {command.strip()}")
    return found


def logical_lines(lines: list[str], first: int) -> list[tuple[int, str]]:
    """Backslash continuations joined; each logical line with the number of its first line."""
    out: list[tuple[int, str]] = []
    pending, start = "", first
    for n, line in enumerate(lines, first):
        if not pending:
            start = n
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        out.append((start, pending + line))
        pending = ""
    if pending:
        out.append((start, pending))
    return out


def markdown(path: str, text: str) -> list[str]:
    found: list[str] = []
    fence, block, block_start = "", [], 0
    for n, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if fence:
            if m and m.group(1) == fence:
                for start, logical in logical_lines(block, block_start):
                    if not logical.lstrip().startswith("#"):
                        found += shell_form(logical, start, path)
                fence, block = "", []
            else:
                block.append(line)
            continue
        if m:
            fence, block, block_start = m.group(1), [], n + 1
            continue
        for span in SPAN.finditer(line):
            found += shell_form(span.group(2), n, path)
    if fence:  # an unclosed fence runs to the end of the file, as it renders
        for start, logical in logical_lines(block, block_start):
            if not logical.lstrip().startswith("#"):
                found += shell_form(logical, start, path)
    return found


def python(path: str, text: str) -> list[str]:
    tree = ast.parse(text, path)
    constants = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }

    def render(item: ast.expr) -> str | None:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            return item.value
        if isinstance(item, ast.Name) and item.id in constants:
            return constants[item.id]
        if isinstance(item, ast.JoinedStr):
            return "".join(render(part.value) or "{}" if isinstance(part, ast.FormattedValue) else render(part) or "" for part in item.values)
        return None

    parts = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for part in node.values}
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            items = [render(item) for item in node.elts]
            if "gh" in items:
                call = items[items.index("gh") :]
                joined = " ".join(item if item is not None else "<unread>" for item in call)
                if call[1:2] != ["auth"] and not CARRIES.search(joined):
                    found.append(f"{path}:{node.lineno}: [{joined}]")
        elif isinstance(node, (ast.Constant, ast.JoinedStr)) and id(node) not in parts:
            value = render(node)
            if value and re.match(rf"\s*gh[ \t]+({COMMANDS})(?![\w-])", value):
                for start, logical in logical_lines(value.split("\n"), node.lineno):
                    found += shell_form(logical, start, path)
    return found


def other(path: str, text: str) -> list[str]:
    lines = text.split("\n")
    shell = path.endswith((".sh", ".bash")) or bool(SHELL.match(lines[0]))
    found: list[str] = []
    for start, logical in logical_lines(lines, 1):
        if shell and logical.lstrip().startswith("#"):
            continue
        found += shell_form(logical, start, path)
    return found


listed = subprocess.run(["git", "ls-files", "-z", "--", ".claude", "scripts"], capture_output=True, text=True)
if listed.returncode != 0:
    print(listed.stderr, file=sys.stderr)
    sys.exit(2)
found: list[str] = []
for path in sorted(p for p in listed.stdout.split("\0") if p and p != "scripts/count-list.sh"):
    data = pathlib.Path(path).read_bytes()
    if b"\0" in data:
        continue
    text = data.decode("utf-8", errors="replace")
    try:
        if path.endswith(".md"):
            found += markdown(path, text)
        elif path.endswith(".py"):
            found += python(path, text)
        else:
            found += other(path, text)
    except SyntaxError as exc:
        print(f"count-list: gh-calls-without-the-repo cannot parse {path}: {exc}", file=sys.stderr)
        sys.exit(2)
for hit in found:
    print(f"count-list: gh-calls-without-the-repo: {hit}", file=sys.stderr)
print(len(found))
GHCALLS
}

# The homes of the version -- `.cz.toml`, `[project].version` in pyproject.toml, the README badge and uv.lock's
# own `healthchecks` package -- as the number of distinct versions among them, minus one: 0 when the four agree.
# A home the reader cannot find is an error, never a 0.
c_version_homes_that_disagree() {
  uv run python - <<'VERSIONS'
import pathlib
import re
import sys
import tomllib

try:
    homes = {
        ".cz.toml": tomllib.loads(pathlib.Path(".cz.toml").read_text())["tool"]["commitizen"]["version"],
        "pyproject.toml": tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"],
    }
    badges = re.findall(r"img\.shields\.io/badge/version-v([^-\s)]+)-", pathlib.Path("README.md").read_text())
    locked = [p.get("version") for p in tomllib.loads(pathlib.Path("uv.lock").read_text()).get("package", []) if p.get("name") == "healthchecks"]
except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
    print(f"count-list: version-homes-that-disagree cannot read a home: {exc!r}", file=sys.stderr)
    sys.exit(2)
if len(badges) != 1 or len(locked) != 1:
    print(f"count-list: version-homes-that-disagree wants one README badge and one uv.lock entry, found {len(badges)} and {len(locked)}", file=sys.stderr)
    sys.exit(2)
homes["README.md"], homes["uv.lock"] = badges[0], locked[0]
if len(set(homes.values())) > 1:
    print("count-list: version-homes-that-disagree: " + ", ".join(f"{k} {v}" for k, v in homes.items()), file=sys.stderr)
print(len(set(homes.values())) - 1)
VERSIONS
}

# Tracked files named CHANGELOG.md, in any case and in any directory: release notes are written into the GitHub
# Release.
c_changelog_files() { git ls-files | grep -ciE '(^|/)changelog\.md$'; }

# The non-test Python under hc/ -- outside every `tests/` directory -- that imports one of CLIENTS, a submodule
# included. Exempt: hc/lib/curl.py, the one client, and apprise under hc/integrations/apprise/, the one transport that
# bypasses hc.lib.curl. A vendor SDK is not in CLIENTS, so a transport built on one reads 0.
c_http_clients_outside_hc_lib_curl() {
  uv run python - <<'HTTPCLIENTS'
import ast
import pathlib
import subprocess
import sys

CLIENTS = ("requests", "urllib3", "httpx", "http.client", "urllib.request", "pycurl", "apprise")
listed = subprocess.run(["git", "ls-files", "-z", "--", "hc/*.py"], capture_output=True, text=True)
if listed.returncode != 0:
    print(listed.stderr, file=sys.stderr)
    sys.exit(2)
found = []
for path in sorted(p for p in listed.stdout.split("\0") if p):
    if "/tests/" in path or path == "hc/lib/curl.py":
        continue
    try:
        tree = ast.parse(pathlib.Path(path).read_text(), path)
    except SyntaxError as exc:
        print(f"count-list: http-clients-outside-hc-lib-curl cannot parse {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        else:
            continue
        hits = [m for m in modules if any(m == c or m.startswith(c + ".") for c in CLIENTS)]
        if path.startswith("hc/integrations/apprise/"):
            hits = [m for m in hits if m != "apprise" and not m.startswith("apprise.")]
        if hits:
            found.append(f"{path}:{node.lineno}: {hits[0]}")
for hit in found:
    print(f"count-list: http-clients-outside-hc-lib-curl: {hit}", file=sys.stderr)
print(len(found))
HTTPCLIENTS
}

main() {
  if [ "${BASH_VERSINFO[0]}" -lt 4 ] || { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -lt 4 ]; }; then
    echo "count-list: needs bash 4.4 or newer, and this is bash ${BASH_VERSION}" >&2
    exit 2
  fi
  wanted=("$@")
  cd "$(git rev-parse --show-toplevel)" || exit 2

  emit "non-pr-commits-on-develop" c_non_pr_commits_on_develop
  emit "gh-calls-without-the-repo" c_gh_calls_without_the_repo
  emit "version-homes-that-disagree" c_version_homes_that_disagree
  emit "changelog-files" c_changelog_files
  emit "http-clients-outside-hc-lib-curl" c_http_clients_outside_hc_lib_curl

  local w
  for w in "${wanted[@]}"; do
    case " ${seen[*]} " in *" $w "*) ;; *) echo "count-list: no entry named $w" >&2; exit 2 ;; esac
  done

  if [ "${#errors[@]}" -gt 0 ]; then
    printf 'count-list: %s command(s) errored: %s\n' "${#errors[@]}" "${errors[*]}" >&2
    exit 2
  fi
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then main "$@"; fi
