"""Character table of the NEWGAME 2003 Russian translation.

The font is one Nemesis block (96 tiles) loaded into VRAM so that the tile
index equals the text byte. The translators mapped Cyrillic onto the Latin
positions: 'D' draws as «И», '0' as «О», and so on.

The table was read off the game, not guessed: capitals are confirmed by the
menu tilemap (ИГРОК=DUH0R, ВДВОЕМ=BLB0NM, ДУЭЛЬ=LE"KV, ОПЦИИ=0GWDD), lower case
by the tilemap of the first stage's dialogue.

Pitfalls worth remembering:
  * Digits 0 and 3 are the same glyphs as «О» and «З»; there are no separate digits.
  * Ж (0x26) and ж (0x3B) are distinct upper- and lower-case glyphs; no byte of
    this table shares its character with another. Should a glyph ever get a
    second byte, the reverse table keeps the first one and ``decode_lossless``
    exports the other as {XX}, so text stays readable and edits exact
    (``test_every_byte_roundtrips_losslessly`` guards that invariant).
  * 0x29 is lower-case «ю» and 0x50 upper-case «Ю» (the menu's «МЕНЮ» uses 0x50).
    Earlier versions of this table swapped the two labels, which made correct
    text such as «следующий» read as «следуЮщий» in assets/text. 0x71 is «й»
    (the «и» glyph plus a breve).
  * Ъ (0x4F), Ё (0x51), ё (0x3C), the parentheses (0x2A, 0x2B) and Latin V
    (0x40, for the menu version) were drawn into free slots by this project;
    the original translation did not have them.
"""

from __future__ import annotations

# ROM byte -> displayed character
BYTE_TO_CHAR: dict[int, str] = {
    0x20: " ",
    0x21: "!",
    0x22: "Э",
    0x24: "◣",  # pointer / corner
    0x25: "█",  # solid block
    0x26: "Ж",  # tall «Ж»
    0x27: "э",
    0x28: "б",
    0x29: "ю",  # x-height glyph; upper-case Ю is 0x50
    0x2A: "(",  # added by this project
    0x2B: ")",  # added by this project
    0x2C: ",",
    0x2D: "-",
    0x2E: ".",
    0x2F: "Б",
    0x30: "О",  # zero doubles as «О»
    0x31: "1",
    0x32: "2",
    0x33: "З",  # tall glyph: both «З» and the digit 3
    0x34: "4",
    0x35: "5",
    0x36: "6",
    0x37: "7",
    0x38: "8",
    0x39: "9",
    0x3A: ":",
    0x3B: "ж",
    0x3D: "х",
    0x3F: "?",
    0x60: "'",
    # capitals
    0x3C: "ё",  # added by this project
    0x40: "V",  # Latin, for the menu version; added by this project
    0x41: "А", 0x42: "В", 0x43: "С", 0x44: "И", 0x45: "У", 0x46: "Ф",
    0x47: "П", 0x48: "Р", 0x49: "Ш", 0x4A: "Х", 0x4B: "Л", 0x4C: "Д",
    0x4D: "М", 0x4E: "Е", 0x4F: "Ъ", 0x50: "Ю", 0x51: "Ё", 0x52: "К",
    0x53: "Ы", 0x54: "Т", 0x55: "Г", 0x56: "Ь", 0x57: "Ц", 0x58: "Ч",
    0x59: "Н", 0x5A: "Я",
    # lower case
    0x61: "ф", 0x62: "и", 0x63: "с", 0x64: "в", 0x65: "у", 0x66: "а",
    0x67: "п", 0x68: "р", 0x69: "ш", 0x6A: "о", 0x6B: "л", 0x6C: "д",
    0x6D: "ь", 0x6E: "т", 0x6F: "щ", 0x70: "з", 0x71: "й", 0x72: "к",
    0x73: "ы", 0x74: "е", 0x75: "г", 0x76: "м", 0x77: "ц", 0x78: "ч",
    0x79: "н", 0x7A: "я",
    # Latin kept for the NEWGAME logo
    0x7C: "W", 0x7D: "N", 0x7E: "G",
}  # fmt: skip

# reverse table: first byte wins for duplicated glyphs
CHAR_TO_BYTE: dict[str, int] = {}
for _b, _c in BYTE_TO_CHAR.items():
    CHAR_TO_BYTE.setdefault(_c, _b)

# Digits 0 and 3 share glyphs with «О» and «З».
CHAR_TO_BYTE["0"] = 0x30
CHAR_TO_BYTE["3"] = 0x33


def decode(data: bytes) -> str:
    """Bytes -> readable string. Unknown bytes become {XX}."""
    out = []
    for b in data:
        ch = BYTE_TO_CHAR.get(b)
        out.append(ch if ch is not None else "{%02X}" % b)
    return "".join(out)


def decode_lossless(data: bytes) -> str:
    """Decode so that ``encode()`` returns exactly the same bytes.

    Duplicated glyphs make the reverse mapping ambiguous; any byte that would
    not round-trip is written as {XX}. The text stays readable, the edit exact.
    """
    out = []
    for b in data:
        ch = BYTE_TO_CHAR.get(b)
        if ch is None:
            out.append("{%02X}" % b)
            continue
        try:
            out.append(ch if encode(ch) == bytes([b]) else "{%02X}" % b)
        except ValueError:
            out.append("{%02X}" % b)
    return "".join(out)


_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _lookup(ch: str) -> int | None:
    """Byte for a character; upper/lower case stand in for each other where the
    font has one case only. Explicit ``None`` checks: byte 0 would be a valid hit."""
    for candidate in (ch, ch.upper(), ch.lower()):
        b = CHAR_TO_BYTE.get(candidate)
        if b is not None:
            return b
    return None


def encode(text: str) -> bytes:
    """String -> bytes. Raises ValueError for characters the font lacks or a bad {XX}."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "{":
            escape = text[i : i + 4]
            if len(escape) == 4 and escape[3] == "}" and set(escape[1:3]) <= _HEX_DIGITS:
                out.append(int(escape[1:3], 16))
                i += 4
                continue
            raise ValueError(
                f"bad escape {escape!r} at position {i}: expected {{XX}} with two hex digits"
            )
        ch = text[i]
        b = _lookup(ch)
        if b is None:
            raise ValueError(f"character {ch!r} is not in the game font (position {i})")
        out.append(b)
        i += 1
    return bytes(out)


def format_tbl() -> str:
    """Thingy-format table (``XX=char``) for WindHex, Atlas, Cartographer and friends.

    Dialect: UTF-8; one entry per line; ``#`` starts a comment; every byte
    appears exactly once. The encode-only aliases ``ga3`` knows (digits 0 and 3
    on the О and З glyphs) are listed as comments: most table readers take the
    *last* line for a byte, and a live ``30=0`` would make О dump as 0. Control
    bytes use the dumper conventions ``*FF`` (end of line) and ``/FE`` (end of
    screen).
    """
    lines = [
        "# Golden Axe III (RUS) -- NEWGAME 2003 character table",
        "# Generated by `ga3 assets refresh` from src/ga3/table.py; do not edit by hand.",
        "# Byte == VRAM tile index; the font block is described in rom_map.yml.",
        "",
    ]
    for b in sorted(BYTE_TO_CHAR):
        lines.append(f"{b:02X}={BYTE_TO_CHAR[b]}")
    lines += [
        "",
        "# encode-only aliases (ga3 accepts the digits; kept as comments so that",
        "# last-wins table readers still decode 30 as О and 33 as З)",
        "# 30=0",
        "# 33=3",
        "",
        "# control bytes",
        "*FF",
        "/FE",
    ]
    return "\n".join(lines) + "\n"
