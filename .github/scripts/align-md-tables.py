#!/usr/bin/env python3
"""Align the columns of every Markdown table: used by the pre-commit hook.

    align-md-tables.py FILE...          rewrite files whose tables are not aligned
    align-md-tables.py --check FILE...  only list them

Each cell is padded to its column's widest cell (counted in characters, so
Cyrillic lines up like Latin) and the separator row becomes dashes of the
same width; column alignment colons are kept. Tables inside fenced code are
left alone, and an escaped pipe (``\\|``) stays inside its cell. Exit status 1
when a file was (or, with --check, would be) changed.
"""

from __future__ import annotations

import re
import sys

SEPARATOR = re.compile(r":?-+:?")


def split_row(line: str) -> list[str]:
    """The cells of ``| a | b |``, stripped; ``\\|`` does not split."""
    body = line.strip()[1:-1]
    cells, cur, i = [], "", 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            cur += body[i : i + 2]
            i += 2
            continue
        if body[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += body[i]
        i += 1
    cells.append(cur.strip())
    return cells


def _is_separator(cells: list[str]) -> bool:
    return all(SEPARATOR.fullmatch(c) for c in cells)


def _dashes(cell: str, width: int) -> str:
    left, right = cell.startswith(":"), cell.endswith(":")
    return (":" if left else "-") + "-" * width + (":" if right else "-")


def align_table(lines: list[str]) -> list[str]:
    rows = [split_row(line) for line in lines]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    widths = [max([len(r[i]) for r in rows if not _is_separator(r)] + [1]) for i in range(n)]
    out = []
    for r in rows:
        if _is_separator(r):
            out.append("|" + "|".join(_dashes(r[i], widths[i]) for i in range(n)) + "|")
        else:
            out.append("| " + " | ".join(r[i].ljust(widths[i]) for i in range(n)) + " |")
    return out


def align(text: str) -> str:
    """``text`` with every table aligned; everything else byte for byte."""
    lines = text.split("\n")
    out: list[str] = []
    fenced = False
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and lines[i].startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            block = lines[i:j]
            is_table = len(block) >= 2 and _is_separator(split_row(block[1]))
            out += align_table(block) if is_table else block
            i = j
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    status = 0
    for path in (a for a in argv if a != "--check"):
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        new = align(text)
        if new != text:
            status = 1
            print(f"{'unaligned' if check else 'aligned'} tables: {path}")
            if not check:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(new)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
