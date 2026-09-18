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
            rows.append((int(off_s, 16), int(len_s), txt[1:] if txt.startswith(" ") else txt))
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
