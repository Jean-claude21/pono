"""Reading the lines a change adds, with their line numbers in the new file."""

import re
from collections.abc import Iterator

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_lines(patch: str) -> Iterator[tuple[int, str]]:
    """Yield (line number, text) for every line the patch adds."""

    line = 0
    for raw in patch.splitlines():
        hunk = _HUNK.match(raw)
        if hunk:
            line = int(hunk.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            yield line, raw[1:]
            line += 1
        elif raw.startswith("-"):
            continue
        else:
            line += 1


__all__ = ["added_lines"]
