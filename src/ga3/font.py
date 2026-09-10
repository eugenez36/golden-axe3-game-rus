"""Font glyphs as editable text art.

The font is one Nemesis block of 96 8x8 tiles; text bytes index it directly
(byte ``first_byte`` = tile 0). The menu reuses the same array with a swapped
background index, so editing the block changes the font on every screen.

Glyphs use background colour 12 and ink colour 6 with no transparent pixels
(which is why a naive "two-colour tile" search never found the font).

Text-art format::

    ; comment
    @ 4F  'Ъ'
    ..####..
    ...

A header line per glyph (byte, current character), then 8 rows of 8 marks:
``#`` ink, ``.`` background, a hex digit for any other palette index. Comments
start with ``;`` -- a ``#`` at the start of a line is a pixel, not a comment.
"""

from __future__ import annotations

from . import table
from .tiles import TILE_SIZE, tile_decode, tile_encode

DEFAULT_FIRST_BYTE = 0x20
DEFAULT_BG = 0x0C
DEFAULT_INK = 0x06


def tile_to_art(raw: bytes, index: int, bg: int = DEFAULT_BG, ink: int = DEFAULT_INK) -> list[str]:
    art = []
    for row in tile_decode(raw, index * TILE_SIZE):
        line = ""
        for v in row:
            if v == bg:
                line += "."
            elif v == ink:
                line += "#"
            else:
                line += "%X" % v
        art.append(line)
    return art


def art_to_tile(art: list[str], bg: int = DEFAULT_BG, ink: int = DEFAULT_INK) -> bytes:
    if len(art) != 8:
        raise ValueError(f"expected 8 rows, got {len(art)}")
    rows = []
    for y, line in enumerate(art):
        if len(line) != 8:
            raise ValueError(f"row {y + 1}: expected 8 marks, got {len(line)}")
        row = []
        for ch in line:
            if ch == ".":
                row.append(bg)
            elif ch == "#":
                row.append(ink)
            else:
                try:
                    row.append(int(ch, 16))
                except ValueError:
                    raise ValueError(f"row {y + 1}: unknown mark {ch!r}") from None
        rows.append(row)
    return tile_encode(rows)


def is_blank(raw: bytes, index: int, bg: int = DEFAULT_BG) -> bool:
    fill = (bg << 4) | bg
    return all(b == fill for b in raw[index * TILE_SIZE : (index + 1) * TILE_SIZE])


def free_slots(raw: bytes, first_byte: int = DEFAULT_FIRST_BYTE, bg: int = DEFAULT_BG) -> list[int]:
    """Bytes whose glyph is blank and which have no character in the table."""
    tiles = len(raw) // TILE_SIZE
    return [
        first_byte + i
        for i in range(tiles)
        if is_blank(raw, i, bg) and (first_byte + i) not in table.BYTE_TO_CHAR
    ]


def font_to_art(
    raw: bytes,
    first_byte: int = DEFAULT_FIRST_BYTE,
    bg: int = DEFAULT_BG,
    ink: int = DEFAULT_INK,
) -> str:
    tiles = len(raw) // TILE_SIZE
    lines = [
        f"; Golden Axe III (RUS) font: {tiles} glyphs, 8x8 pixels each.",
        "; '#' = ink, '.' = background, hex digit = another palette index.",
        "; Comments start with ';'. A '#' at the start of a line is a pixel, not a comment.",
        "; Do not edit the '@' header lines, only the drawing under them.",
        "; Free slots are marked FREE: draw a glyph there, then add it to ga3/table.py.",
        "; The block must still fit its ROM slot after recompression;",
        "; `ga3 font info` shows the margin.",
        "",
    ]
    for i in range(tiles):
        b = first_byte + i
        ch = table.BYTE_TO_CHAR.get(b)
        art = tile_to_art(raw, i, bg, ink)
        note = ("FREE" if is_blank(raw, i, bg) else "not in table") if ch is None else repr(ch)
        lines.append("@ %02X  %s" % (b, note))
        lines.extend(art)
        lines.append("")
    return "\n".join(lines) + "\n"


def parse_art(
    text: str, bg: int = DEFAULT_BG, ink: int = DEFAULT_INK, name: str = "<art>"
) -> dict[int, bytes]:
    glyphs: dict[int, bytes] = {}
    cur = None
    art: list[str] = []
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.rstrip("\n")
        if line.startswith(";"):
            continue
        if line.startswith("@"):
            if cur is not None:
                glyphs[cur] = art_to_tile(art, bg, ink)
            head = line[1:].strip().split()
            cur = int(head[0], 16)
            art = []
            continue
        if not line.strip():
            continue
        if cur is None:
            raise ValueError(f"{name}:{lineno}: drawing before the first '@' header")
        art.append(line)
        if len(art) > 8:
            raise ValueError(f"{name}:{lineno}: glyph 0x{cur:02X} has more than 8 rows")
    if cur is not None:
        glyphs[cur] = art_to_tile(art, bg, ink)
    return glyphs


def parse_art_file(path: str, bg: int = DEFAULT_BG, ink: int = DEFAULT_INK) -> dict[int, bytes]:
    with open(path, encoding="utf-8") as fh:
        return parse_art(fh.read(), bg, ink, name=path)


def art_to_font(
    glyphs: dict[int, bytes], tiles: int, first_byte: int = DEFAULT_FIRST_BYTE
) -> bytes:
    """Assemble the full tile array from parsed glyphs; every slot must be present."""
    raw = bytearray()
    for i in range(tiles):
        b = first_byte + i
        if b not in glyphs:
            raise ValueError(f"glyph 0x{b:02X} is missing from the art file")
        raw += glyphs[b]
    extra = sorted(set(glyphs) - {first_byte + i for i in range(tiles)})
    if extra:
        raise ValueError(
            "glyph bytes outside the font: "
            + " ".join("0x%02X" % b for b in extra)
            + f" (valid 0x{first_byte:02X}..0x{first_byte + tiles - 1:02X})"
        )
    return bytes(raw)
