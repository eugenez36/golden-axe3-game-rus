"""CRAM palettes: decode, encode, heuristic search, ``.pal`` text files.

A CRAM word is ``----BBB-GGG-RRR-``: three 3-bit components, bits 0, 4, 8 and
12..15 always zero. Brightness levels follow Genesis Plus GX in "normal" mode.

The DMA log shows CRAM is always filled from Work RAM (FFE51A / FFF200); the
routine at 01209E copies palettes there from ROM (the title's at 0EB200,
0EB278, 0EB2A2 -- patch ``menus`` points the game at new ones). The stages'
palettes sit in 031E16-032934 (tables, palette scripts, colour cycles; see
rom_map.yml); segments of type ``palette`` are built from ``.pal`` files read
word for word by ``parse_pal_words``. The other ``.pal`` files under
``assets/palettes/`` are emulator CRAM captures, a rendering reference only.
"""

from __future__ import annotations

import os
import re
import struct
from pathlib import Path

VDP_LEVELS = (0, 52, 87, 116, 144, 172, 206, 255)

RGB = tuple[int, int, int]
_HEX = frozenset("0123456789abcdefABCDEF")


def pal_decode(data: bytes, off: int = 0, count: int = 16) -> list[RGB]:
    """CRAM words -> RGB888."""
    out = []
    for i in range(count):
        w = struct.unpack_from(">H", data, off + i * 2)[0]
        out.append(word_to_rgb(w))
    return out


def word_to_rgb(w: int) -> RGB:
    return (VDP_LEVELS[(w >> 1) & 7], VDP_LEVELS[(w >> 5) & 7], VDP_LEVELS[(w >> 9) & 7])


def rgb_to_word(c: RGB) -> int:
    def level(v: int) -> int:
        return min(range(8), key=lambda i: abs(VDP_LEVELS[i] - v))

    r, g, b = c
    return (level(b) << 9) | (level(g) << 5) | (level(r) << 1)


def gpgx_cram_to_words(dump: bytes) -> bytes:
    """Convert a Genesis Plus GX CRAM dump into standard big-endian CRAM words.

    GPGX keeps CRAM as 64 little-endian 9-bit words packed ``BBBGGGRRR``
    (core/vdp_ctrl.c: ``data = ((data & 0xE00) >> 3) | ((data & 0x0E0) >> 2) |
    ((data & 0x00E) >> 1)``). The headless dumper writes that array as is.
    """
    if len(dump) % 2:
        raise ValueError("CRAM dump must have an even length")
    out = bytearray()
    for i in range(0, len(dump), 2):
        p = dump[i] | (dump[i + 1] << 8)
        w = ((p & 0x1C0) << 3) | ((p & 0x038) << 2) | ((p & 0x007) << 1)
        out += struct.pack(">H", w)
    return bytes(out)


def pal_encode(colors: list[RGB]) -> bytes:
    """RGB888 -> CRAM words; each component snaps to the nearest VDP level."""
    return b"".join(struct.pack(">H", rgb_to_word(c)) for c in colors)


def looks_like_palette(data: bytes, off: int, count: int = 16) -> bool:
    """A genuine CRAM palette has bits 0, 4, 8 and 12..15 clear in every word."""
    if off + count * 2 > len(data):
        return False
    return all(not struct.unpack_from(">H", data, off + i * 2)[0] & 0xF111 for i in range(count))


def find_palettes(data: bytes, start: int = 0x200, count: int = 16) -> list[int]:
    """Offsets of every non-overlapping run of ``count`` palette-shaped words.

    Heuristic and slow (pure Python over the whole image); the 0xF111 mask
    matches plenty of code, so treat the hits as leads, not facts.
    """
    out, o, end = [], start, len(data) - count * 2
    step = count * 2
    while o <= end:
        if looks_like_palette(data, o, count):
            out.append(o)
            o += step
        else:
            o += 2
    return out


# -- .pal text format ----------------------------------------------------------
#
#   ; header comments
#   ; source: emu/scenes/title.txt frame 2100, CRAM dump
#   [palette 0]
#   #000000  0x0000  ; 0
#   ...
#
# One line per colour: RGB as seen by GPGX, the raw CRAM word, and the index.
# The word is authoritative; the RGB is a convenience for humans and editors.


def format_pal(
    cram: bytes,
    comments: list[str] | None = None,
    lines_of: list[int] | None = None,
    labels: list[str] | None = None,
) -> str:
    """``lines_of`` puts ``line L`` into each header (palette scripts, see
    ``parse_pal_words``); ``labels`` adds a comment after each header."""
    if len(cram) % 32:
        raise ValueError("CRAM data must be a multiple of 32 bytes (16 words per palette)")
    lines = [f"; {c}" for c in (comments or [])]
    for p in range(len(cram) // 32):
        head = f"[palette {p}]" if lines_of is None else f"[palette {p} line {lines_of[p]}]"
        if labels and p < len(labels) and labels[p]:  # a short list: ga3 map --check says so
            head += f"  ; {labels[p]}"
        lines.append(head)
        for i in range(16):
            w = struct.unpack_from(">H", cram, p * 32 + i * 2)[0]
            r, g, b = word_to_rgb(w)
            lines.append(f"#{r:02X}{g:02X}{b:02X}  0x{w:04X}  ; {i}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def parse_pal(text: str) -> list[list[RGB]]:
    """Parse a ``.pal`` file into a list of 16-colour palettes."""
    pals: list[list[RGB]] = []
    cur: list[RGB] | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[palette"):
            cur = []
            pals.append(cur)
            continue
        if cur is None:
            raise ValueError(f"line {lineno}: colour before the first [palette N] header")
        parts = line.split()
        if len(parts) >= 2 and parts[1].lower().startswith("0x"):
            cur.append(word_to_rgb(int(parts[1], 16)))
        elif parts[0].startswith("#") and len(parts[0]) == 7:
            h = parts[0][1:]
            cur.append((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
        else:
            raise ValueError(f"line {lineno}: cannot parse colour {raw!r}")
    for i, p in enumerate(pals):
        if len(p) != 16:
            raise ValueError(f"palette {i} has {len(p)} colours, expected 16")
    return pals


_HEAD = re.compile(r"\[palette\s+(\d+)(?:\s+line\s+([0-3]))?\]$")


def parse_pal_words(text: str) -> list[tuple[int | None, list[int]]]:
    """Parse a ``.pal`` file exactly: ``(line, 16 CRAM words)`` per palette.

    ``line`` is the ``line L`` of a ``[palette N line L]`` header, else None.
    A colour may be given as the word, as ``#RRGGBB`` (snapped to the nearest
    VDP level) or as both; when both are there they must agree, so an edit to
    one of them alone is refused instead of silently ignored. Words must be
    real CRAM colours (bits 0, 4, 8 and 12-15 clear).
    """
    pals: list[tuple[int | None, list[int]]] = []
    cur: list[int] | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            m = _HEAD.match(line)
            if not m:
                raise ValueError(f"line {lineno}: expected [palette N] or [palette N line L]")
            if int(m.group(1)) != len(pals):
                raise ValueError(f"line {lineno}: palette {m.group(1)}, expected {len(pals)}")
            cur = []
            pals.append((None if m.group(2) is None else int(m.group(2)), cur))
            continue
        if cur is None:
            raise ValueError(f"line {lineno}: colour before the first [palette N] header")
        word = rgb = None
        for part in line.split():
            if part.lower().startswith("0x") and word is None:
                word = int(part, 16)
            elif part.startswith("#") and len(part) == 7 and rgb is None:
                rgb = (int(part[1:3], 16), int(part[3:5], 16), int(part[5:7], 16))
            else:
                raise ValueError(f"line {lineno}: cannot parse colour {raw.strip()!r}")
        if word is None:
            word = rgb_to_word(rgb)  # type: ignore[arg-type]
        elif rgb is not None and word_to_rgb(word) != rgb:
            raise ValueError(
                f"line {lineno}: #{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X} is not 0x{word:04X} "
                f"(#{'%02X%02X%02X' % word_to_rgb(word)}); change both or delete one"
            )
        if word & 0xF111:
            raise ValueError(f"line {lineno}: 0x{word:04X} is not a CRAM colour")
        cur.append(word)
    for i, (_line, p) in enumerate(pals):
        if len(p) != 16:
            raise ValueError(f"palette {i} has {len(p)} colours, expected 16")
    return pals


def load_pal(path: str) -> list[list[RGB]]:
    with open(path, encoding="utf-8") as fh:
        return parse_pal(fh.read())


def resolve_ref(
    ref: str | None,
    pal_dir: str | os.PathLike | None,
    data: bytes | None = None,
    missing_ok: bool = False,
) -> list[RGB] | None:
    """Turn a palette reference into 16 colours.

    ``NAME[/INDEX]`` names ``<pal_dir>/NAME.pal`` (INDEX picks one of its
    palettes, default 0). Otherwise the reference is a hex ROM offset into
    ``data`` (``0x``/``$`` prefix, or bare hex digits when no such ``.pal``
    exists -- a file always wins over a look-alike such as ``cafe``). ``None``,
    ``""`` and ``gray`` mean "no palette". With ``missing_ok`` an unresolvable
    reference yields ``None`` instead of raising ``ValueError``.
    """
    if not ref or ref == "gray":
        return None
    name, _, idx = ref.partition("/")
    if pal_dir is not None:
        pal_file = Path(pal_dir) / f"{name}.pal"
        if pal_file.exists():
            pals = load_pal(str(pal_file))
            i = int(idx or 0)
            if not 0 <= i < len(pals):
                raise ValueError(
                    f"{pal_file.name} has {len(pals)} palette(s); index {i} is out of range"
                )
            return pals[i]
    if ref.lower().startswith("0x"):
        digits = ref[2:]
    elif ref.startswith("$"):
        digits = ref[1:]
    else:
        digits = ref
    if digits and set(digits) <= _HEX:
        if data is None:
            if missing_ok:
                return None
            raise ValueError(f"palette {ref!r}: an image is needed to read a palette by offset")
        off = int(digits, 16)
        if off + 32 > len(data):
            raise ValueError(f"palette offset {off:06X} lies past the end of the image")
        return pal_decode(data, off)
    if missing_ok:
        return None
    where = f" in {pal_dir}" if pal_dir is not None else ""
    raise ValueError(f"palette {ref!r}: no {name}.pal{where} and not a hex ROM offset")
