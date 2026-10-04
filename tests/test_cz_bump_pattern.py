"""`.cz.toml`'s bump rule: a type counts on any line shaped as a Conventional Commits header.

commitizen is not a dev dependency, so this reads the pattern and the map with tomllib and applies them the way
`cz bump` does: the pattern searched in every line of every message, its group matched against the map's keys in order.
"""

import pathlib
import re
import tomllib

import pytest

_CUSTOM = tomllib.loads((pathlib.Path(__file__).resolve().parents[1] / ".cz.toml").read_text())["tool"]["commitizen"]["customize"]
_ORDER = (None, "PATCH", "MINOR", "MAJOR")


def _increment(message: str) -> str | None:
    found = None
    for line in message.split("\n"):
        hit = re.search(_CUSTOM["bump_pattern"], line)
        if not hit:
            continue
        kind = next((v for k, v in _CUSTOM["bump_map"].items() if re.match(k, hit.group(1))), None)
        if kind and _ORDER.index(kind) > _ORDER.index(found):
            found = kind
    return found


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("fix: a", "PATCH"),
        ("feat(api): a", "MINOR"),
        ("fix(api)!: a", "MAJOR"),
        ("feat!: a", "MAJOR"),
        ("fix: a\n\nBREAKING CHANGE: x", "MAJOR"),
        ("fix: a\n\nBREAKING-CHANGE: x", "MAJOR"),
        ("fix: a\n\nbuilding lazily", "PATCH"),
        ("docs: a\n\nperformance is unchanged", "PATCH"),
        ("fix: a\n\nfeature flags stay off", "PATCH"),
        ("fix(x): crash on (empty)!", "PATCH"),
        ("Fix the thing", None),
        ("featuring: x", None),
        ("Merge pull request #1 from zhaow-de/x\n\nfeat(api): a", "MINOR"),
        ("claude(config): a", "PATCH"),
        ("revert: a", "MINOR"),
    ],
)
def test_a_type_counts_on_a_header_shaped_line(message: str, expected: str | None):
    assert _increment(message) == expected
