"""Game text: locate strings, export to a text file, verify and re-insert.

Text is stored as plain bytes in the font's "Latin" layout (see ``table``),
strings separated by 0xFF. Edits are strictly in place: a string may not grow
beyond its original length or it would overwrite neighbouring data. The
tools check this and refuse.

File format (one record per string)::

    # comment
    HEXOFFSET:DECLENGTH | text

Only the text right of ``|`` is meant to be edited. ``{XX}`` is a byte with no
character in the font (or one that would not round-trip).
"""

from __future__ import annotations

from . import table

TEXT_BYTES = frozenset(table.BYTE_TO_CHAR)
DEFAULT_MIN_LEN = 4  # shorter runs are noise

Row = tuple[int, int, str]  # (offset, length, text)


def _padded(txt: str, ln: int) -> bytes:
    """A record encoded and space-padded to its slot. Raises ValueError on unknown characters."""
    enc = table.encode(txt)
    return enc + b"\x20" * (ln - len(enc))


def find_strings(data: bytes, lo: int, hi: int, min_len: int = DEFAULT_MIN_LEN) -> list[Row]:
    """Runs of printable bytes inside ``[lo, hi)`` as ``(offset, length, text)``.

    A heuristic scan: some records capture neighbouring data bytes that happen
    to be printable. Edit only the meaningful part of such records.
    """
    found: list[Row] = []
    i = lo
    while i < hi:
        if data[i] in TEXT_BYTES:
            j = i
            while j < hi and data[j] in TEXT_BYTES:
                j += 1
            if j - i >= min_len:
                found.append((i, j - i, table.decode_lossless(data[i:j])))
            i = j
        else:
            i += 1
    return found


def format_strings_file(rows: list[Row], title: str, start: int, end: int) -> str:
    lines = [
        f"# {title}: game text, ROM range {start:06X}-{end:06X}",
        "# Format: OFFSET:LENGTH | text. Edit only the text right of '|'.",
        "# A string may not grow: the ROM is full and edits are in place.",
        "# {XX} is a byte with no glyph in the font (or one that does not round-trip).",
        "# In-game strings are separated by 0xFF; here each string is one record.",
        "",
    ]
    for off, ln, txt in rows:
        lines.append("%06X:%d | %s" % (off, ln, txt))
    return "\n".join(lines) + "\n"


def parse_strings_file(path: str) -> list[Row]:
    rows: list[Row] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "|" not in line:
                raise ValueError(f"{path}:{lineno}: missing '|' separator")
            head, txt = line.split("|", 1)
            head = head.strip()
            if ":" not in head:
                raise ValueError(f"{path}:{lineno}: header must be OFFSET:LENGTH")
            off_s, len_s = head.split(":", 1)
            rows.append((int(off_s, 16), int(len_s), txt.removeprefix(" ")))
    return rows


def check(rows: list[Row], start: int | None = None, end: int | None = None) -> list[str]:
    """Problems that would make insertion unsafe: unknown characters, overflow, out of range."""
    problems = []
    for off, ln, txt in rows:
        if start is not None and end is not None and not (start <= off and off + ln <= end):
            problems.append("%06X: record lies outside the segment %06X-%06X" % (off, start, end))
            continue
        try:
            enc = table.encode(txt)
        except ValueError as exc:
            problems.append("%06X: %s" % (off, exc))
            continue
        if len(enc) > ln:
            problems.append(
                "%06X: string is %d byte(s) longer than the original (%d > %d): %r"
                % (off, len(enc) - ln, len(enc), ln, txt)
            )
    return problems


def count_changed(rows: list[Row], data: bytes) -> int:
    """How many records differ from what the image holds.

    A record that cannot be encoded counts as changed: whatever it says, it is
    not what the image holds (``check`` reports the reason separately).
    """
    changed = 0
    for off, ln, txt in rows:
        try:
            enc = _padded(txt, ln)
        except ValueError:
            changed += 1
            continue
        if enc != bytes(data[off : off + ln]):
            changed += 1
    return changed


def insert_strings(data: bytearray, rows: list[Row], start: int, end: int) -> int:
    """Write records into ``data``, padding shorter strings with spaces.

    Returns the number of records that changed the image.
    """
    problems = check(rows, start, end)
    if problems:
        raise ValueError("text insertion refused:\n  " + "\n  ".join(problems))
    changed = 0
    for off, ln, txt in rows:
        enc = _padded(txt, ln)
        if enc != bytes(data[off : off + ln]):
            data[off : off + ln] = enc
            changed += 1
    return changed


def records_at(data: bytes, spans: list[tuple[int, int]]) -> list[Row]:
    """Records for exactly the given ``(offset, length)`` spans (strings embedded in code)."""
    return [(off, ln, table.decode_lossless(bytes(data[off : off + ln]))) for off, ln in spans]


def in_spans(off: int, ln: int, spans: list[tuple[int, int]]) -> bool:
    """Whether the record ``[off, off + ln)`` lies inside one of the ``[start, end)`` spans."""
    return any(start <= off and off + ln <= end for start, end in spans)


# ---------------------------------------------------------------- lint
#
# Mechanical checks for real game text. They catch what an eye skims over in a
# fixed-width strings file; wording and spelling stay a human review.

_UPPER = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
_LOWER = _UPPER.lower()

LINT_RULES: dict[str, tuple[str, str]] = {
    # rule: (regex, what it means)
    "capital-inside-word": (
        rf"[{_LOWER}][{_UPPER}]",
        "a capital after a small letter inside a word",
    ),
    "e-for-quote": (
        r"^ +Э|[.!?]Э\s*$",
        "byte 0x22 draws «Э», not a quotation mark: a reply opens with a space and ', "
        "and closes with '",
    ),
    "double-space": (r"\S {2,}(?=\S)", "two or more spaces between words"),
    "space-before-punctuation": (r"\S [,.!?:)](?=\s|$|')", "a space before punctuation"),
    "no-space-after-punctuation": (
        rf"[{_LOWER}][,.!?:](?=[{_UPPER}{_LOWER}])",
        "no space after punctuation",
    ),
}


def lint_text(txt: str) -> list[tuple[str, str]]:
    """``(rule, excerpt)`` for every rule ``txt`` breaks. Trailing padding is ignored."""
    import re

    body = txt.rstrip(" ")
    found = []
    for rule, (pattern, _why) in LINT_RULES.items():
        for m in re.finditer(pattern, body):
            lo, hi = max(0, m.start() - 6), min(len(body), m.end() + 6)
            found.append((rule, body[lo:hi]))
    return found


def lint(rows: list[Row], allow: dict[int, list[str]] | None = None) -> list[str]:
    """Findings as ``OFFSET rule: «excerpt»`` lines, minus the ``allow``-ed (offset -> rules)."""
    allow = allow or {}
    out = []
    for off, _ln, txt in rows:
        for rule, excerpt in lint_text(txt):
            if rule not in allow.get(off, ()):
                out.append(f"{off:06X} {rule}: «{excerpt}»")
    return out
