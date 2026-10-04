#!/usr/bin/env bash
# claude-kind files (.claude/, CLAUDE.md) never share a commit with another kind
set -euo pipefail
export LC_ALL=C  # one collation for sort and comm
git() { command git -c core.quotePath=false "$@"; }
set_of() { printf '%s\n' "$1" | sed '/^$/d' | sort -u; }
staged=$(git diff --cached --name-only --no-renames)
[ -z "$staged" ] && exit 0
own="$staged" brought=""
# A merge brings what git's own merge of the heads makes, a conflicted path's resolution included: the author can
# neither choose nor split it, so only what the index holds beyond that result is judged as the author's own.
mergehead="$(git rev-parse --git-path MERGE_HEAD)"
if [ -f "$mergehead" ]; then
    result=HEAD merged=(HEAD) conflicted=""
    while read -r line || [ -n "$line" ]; do  # one line per merged head; an octopus merges each onto the result so far
        if ! theirs="$(git rev-parse --verify -q --end-of-options "$line^{commit}" 2>/dev/null)"; then
            printf 'staged-kind: git merge-tree cannot rebuild the merge of %s: it names no commit\n' "$line"
            exit 2
        fi
        args=("$result" "$theirs")
        if [ "$result" != HEAD ]; then
            base="$(git merge-base "$theirs" "${merged[@]}")" || base="$(git hash-object -t tree /dev/null)"
            args=("--merge-base=$base" "${args[@]}")
        fi
        rc=0
        out="$(git merge-tree --write-tree --name-only --no-messages --allow-unrelated-histories "${args[@]}")" || rc=$?
        result="$(head -n 1 <<<"$out")"
        # Exit 1 is a merge with conflicts only when the merged tree's id comes first: git also exits 1, printing
        # nothing, for a head it cannot merge.
        if [ "$rc" -gt 1 ] || ! [[ $result =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] ||
            [ "$(git cat-file -t "$result" 2>/dev/null)" != tree ]; then
            printf 'staged-kind: git merge-tree cannot rebuild the merge of %s\n' "$theirs"
            exit 2
        fi
        conflicted="$conflicted$(tail -n +2 <<<"$out")"$'\n'
        merged+=("$theirs")
    done <"$mergehead"
    conflicted="$(set_of "$conflicted")"
    brought="$(set_of "$(git diff --name-only --no-renames HEAD "$result")"$'\n'"$conflicted")"
    own="$(comm -23 <(set_of "$(git diff --cached --name-only --no-renames "$result")") <(printf '%s\n' "$conflicted"))"
    [ -z "$own" ] && exit 0
fi
claude=$(grep -cE '^(\.claude/|CLAUDE\.md$)' <<<"$own" || true)
other=$(grep -cvE '^(\.claude/|CLAUDE\.md$)' <<<"$own" || true)
merge_claude=0 merge_other=0
if [ -n "$brought" ]; then
    merge_claude=$(grep -cE '^(\.claude/|CLAUDE\.md$)' <<<"$brought" || true)
    merge_other=$(grep -cvE '^(\.claude/|CLAUDE\.md$)' <<<"$brought" || true)
fi
if { [ "$claude" -gt 0 ] && [ "$other" -gt 0 ]; } ||
    { [ "$claude" -gt 0 ] && [ "$merge_other" -gt 0 ] && [ "$merge_claude" -eq 0 ]; } ||
    { [ "$other" -gt 0 ] && [ "$merge_claude" -gt 0 ] && [ "$merge_other" -eq 0 ]; }; then
    printf 'claude-kind files mixed with another kind — split the commit (one kind per commit):\n'
    while IFS= read -r path; do printf '  %s\n' "$path"; done <<<"$own"
    if [ -n "$brought" ]; then
        printf 'beside what the merge brings, which is excused: commit these before or after the merge\n'
    fi
    exit 1
fi
