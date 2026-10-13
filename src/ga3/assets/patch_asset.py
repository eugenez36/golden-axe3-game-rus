"""Generated code and relocated data: a body in its own segment plus small edits elsewhere.

A ``patch`` segment owns the bytes of its body (carved out of verified free
space) and lists a few edits to code outside it, each with the bytes the base
ROM must hold there. The map entry carries every address; ``routine`` picks
the builder:

``menu_version``
    a routine from ``ga3.patches`` and a ``jmp start.l`` over the six bytes at
    ``hook`` (``hook_bytes`` is what the base ROM holds there, hex); parameters
    ``return_to``, ``vram_end``, ``attr``.
``menu_items``
    the main menu's item strings, ``items`` x ``item_width`` characters, from
    the strings file at ``strings_path``; edits point the ``lea`` whose
    displacement word sits at ``items_lea`` (was ``items_was``) and the one at
    ``header_lea`` (was ``header_was``, now item ``header_item``) at the new
    table, and set the immediate of ``moveq #width-1,d7`` at ``width_imm``
    (was ``width_was`` characters).

Assembled patches (``patch: NAME`` + ``section: SECTION``, defined under the
top-level ``patches:`` key) are written in ``assets/patches/*.s`` and built by
``ga3.m68k``: every section lands at the start of its segment, and the hooks
listed for a section become ``jmp label.l`` over the six bytes they name.
``strings: {section, path, label}`` puts the records of a strings file
(``OFFSET:LENGTH | text``, the usual format) at ``label`` in their own section:
the offsets are the records' addresses in that section's slot, in order from
its start, each padded with spaces to its length.

``fill`` is the free-space byte the unused tail of the slot keeps. Every edit
is checked against the image before anything is written, so a map that drifted
from the code fails the build instead of corrupting it; after the whole build
the pipeline checks again that no later segment overwrote a patch.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .. import font as fontlib
from .. import m68k, patches, table, text
from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths

HOOK_SIZE = 6


@dataclass(frozen=True)
class Edit:
    """Bytes outside the slot: ``expect`` must be there before ``new`` replaces them."""

    at: int
    expect: bytes
    new: bytes

    @property
    def end(self) -> int:
        return self.at + len(self.expect)


def _int(seg: Segment, key: str) -> int:
    value = seg.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BuildError(f"{seg}: {seg.get('routine')} needs {key} (a 0x integer)")
    return value


# ---------------------------------------------------------------- menu_version


def _version_edits(seg: Segment) -> list[Edit]:
    hook = _int(seg, "hook")
    raw = seg.get("hook_bytes")
    if not isinstance(raw, str):
        raise BuildError(f"{seg}: patch needs hook (0x address) and hook_bytes (hex string)")
    try:
        expect = bytes.fromhex(raw)
    except ValueError:
        raise BuildError(f"{seg}: hook_bytes {raw!r} is not hex") from None
    if len(expect) != HOOK_SIZE:
        raise BuildError(f"{seg}: hook_bytes must be {HOOK_SIZE} bytes, got {len(expect)}")
    return [Edit(hook, expect, patches.jmp_abs(seg.start))]


def _version_body(seg: Segment, paths: Paths) -> bytes:
    try:
        return patches.menu_version(
            vram_end=seg.get("vram_end"),
            attr=seg.get("attr"),
            return_to=seg.get("return_to"),
            text=patches.version_text(),
        )
    except (TypeError, ValueError) as exc:
        raise BuildError(f"{seg}: {exc}") from None


# ---------------------------------------------------------------- menu_items


def _lea_edit(seg: Segment, at: int, was: int, now: int) -> Edit:
    """The displacement word of a ``lea d16(pc),An``: relative to its own address."""
    old, new = was - at, now - at
    for d in (old, new):
        if not -0x8000 <= d < 0x8000:
            raise BuildError(f"{seg}: lea at {at:06X} cannot reach {at + d:06X} (pc-relative)")
    return Edit(at, struct.pack(">h", old), struct.pack(">h", new))


def _items_edits(seg: Segment) -> list[Edit]:
    width, items = _int(seg, "item_width"), _int(seg, "items")
    header_item = _int(seg, "header_item")
    if not 1 <= width <= 128 or not 0 <= header_item < items:
        raise BuildError(f"{seg}: item_width must be 1..128 and header_item < items")
    was = _int(seg, "width_was")
    return [
        _lea_edit(seg, _int(seg, "items_lea"), _int(seg, "items_was"), seg.start),
        _lea_edit(
            seg, _int(seg, "header_lea"), _int(seg, "header_was"), seg.start + header_item * width
        ),
        # moveq #n,d7 is 7E nn: the opcode byte stays, the immediate changes
        Edit(_int(seg, "width_imm") - 1, bytes([0x7E, was - 1]), bytes([0x7E, width - 1])),
    ]


def _strings_path(seg: Segment, paths: Paths) -> Path:
    rel = seg.get("strings_path")
    if not isinstance(rel, str):
        raise BuildError(f"{seg}: menu_items needs strings_path (relative to assets/)")
    return paths.asset(rel)


def _items_body(seg: Segment, paths: Paths) -> bytes:
    width, items = _int(seg, "item_width"), _int(seg, "items")
    path = _strings_path(seg, paths)
    if not path.exists():
        raise BuildError(f"{seg}: missing text file {path}")
    rows = sorted(text.parse_strings_file(str(path)))
    want = [(seg.start + i * width, width) for i in range(items)]
    if [(off, ln) for off, ln, _t in rows] != want:
        layout = ", ".join(f"{o:06X}:{n}" for o, n in want)
        raise BuildError(f"{seg}: {path.name} must hold exactly the records {layout}")
    body = b""
    for off, ln, txt in rows:
        try:
            enc = table.encode(txt)
        except ValueError as exc:
            raise BuildError(f"{seg}: {off:06X}: {exc}") from None
        if len(enc) > ln:
            raise BuildError(f"{seg}: {off:06X}: {txt!r} is longer than {ln} characters")
        body += enc.ljust(ln, b" ")
    return body


# ---------------------------------------------------------------- handler

_ROUTINES = {
    "menu_version": (_version_edits, _version_body),
    "menu_items": (_items_edits, _items_body),
}


def _routine(seg: Segment):
    try:
        return _ROUTINES[seg.get("routine")]
    except KeyError:
        raise BuildError(f"{seg}: unknown routine {seg.get('routine')!r}") from None


# ---------------------------------------------------------------- assembled patches


def _hooks(seg: Segment) -> list[tuple[int, bytes, str]]:
    """``(address, expected bytes, label)`` for the hooks of this segment's section."""
    pdef, section = seg.get("patch_def"), seg.get("section")
    out = []
    for item in (pdef.get("hooks") or {}).get(section, []):
        if not (isinstance(item, list) and len(item) == 3 and isinstance(item[0], int)):
            raise BuildError(f"{seg}: hook {item!r} must be [0xADDRESS, 'hex bytes', label]")
        try:
            expect = bytes.fromhex(item[1])
        except (TypeError, ValueError):
            raise BuildError(f"{seg}: hook bytes {item[1]!r} are not hex") from None
        if len(expect) != HOOK_SIZE:
            raise BuildError(f"{seg}: a hook replaces {HOOK_SIZE} bytes, got {len(expect)}")
        out.append((item[0], expect, str(item[2])))
    return out


def _glyph_tables(seg: Segment, paths: Paths) -> tuple[str, dict[str, int]]:
    """GLYPHS (1bpp rows) and NIBBLES (4bpp words) from the font art, as source text."""
    spec = seg.get("patch_def").get("glyphs")
    if not spec:
        return "", {}
    glyphs = fontlib.parse_art_file(str(paths.asset(spec["art"])))
    ink, bg = spec["ink"], spec["bg"]
    rows = []
    for ch in spec["chars"]:
        tile = glyphs[table.encode(ch)[0]]
        for y in range(8):
            bits = 0
            for x in range(8):
                byte = tile[y * 4 + x // 2]
                px = byte >> 4 if x % 2 == 0 else byte & 0xF
                if px not in (ink, bg):
                    raise BuildError(f"{seg}: glyph {ch!r} uses colour {px}, not ink/bg")
                bits = bits << 1 | (px == ink)
            rows.append(bits)
    nibbles = []
    for n in range(16):
        word = 0
        for bit in (8, 4, 2, 1):
            word = word << 4 | (ink if n & bit else bg)
        nibbles.append(word)
    src = [f"        section {spec['section']}", "GLYPHS:"]
    src += [
        f"        dc.b    {', '.join(f'${b:02X}' for b in rows[i : i + 8])}"
        for i in range(0, len(rows), 8)
    ]
    src += ["NIBBLES:"]
    src += [
        f"        dc.w    {', '.join(f'${w:04X}' for w in nibbles[i : i + 8])}"
        for i in range(0, 16, 8)
    ]
    return "\n".join(src) + "\n", {"BLANK_GLYPH": spec["chars"].index(" ")}


def _string_tables(seg: Segment, paths: Paths) -> str:
    """The records of the patch's strings file as ``dc.b`` lines in their own section."""
    spec = seg.get("patch_def").get("strings")
    if not spec:
        return ""
    path = paths.asset(spec["path"])
    try:
        rows = text.parse_strings_file(str(path))
    except (OSError, ValueError) as exc:
        raise BuildError(f"{seg}: strings: {exc}") from None
    at = seg.get("sections")[spec["section"]]
    src = [f"        section {spec['section']}", f"{spec['label']}:"]
    for off, ln, txt in rows:
        if off != at:
            raise BuildError(f"{seg}: {path.name}: record {off:06X} should start at {at:06X}")
        try:
            enc = table.encode(txt)
        except ValueError as exc:
            raise BuildError(f"{seg}: {path.name}: {off:06X}: {exc}") from None
        if len(enc) > ln:
            raise BuildError(f"{seg}: {path.name}: {off:06X}: {txt!r} is longer than {ln}")
        enc += table.encode(" ") * (ln - len(enc))
        src.append(f"        dc.b    {', '.join(f'${b:02X}' for b in enc)}")
        at += ln
    return "\n".join(src) + "\n"


def _vdp(addr: int, write: bool) -> int:
    """VDP control longword for a VRAM access at ``addr`` (CD0 = 1 for a write)."""
    return (0x4000 if write else 0) << 16 | (addr & 0x3FFF) << 16 | addr >> 14


def _words(label: str, words: list[int]) -> list[str]:
    src = [f"{label}:"]
    src += [
        f"        dc.w    {', '.join(f'${w:04X}' for w in words[i : i + 10])}"
        for i in range(0, len(words), 10)
    ]
    return src


def _panel_tables(seg: Segment, paths: Paths) -> tuple[str, dict[str, int]]:
    """PANEL_TILES, PANEL_FULL and PANEL_HALF (src/ga3/hero_panel.py), as source text."""
    from .. import hero_panel

    spec = seg.get("patch_def").get("panel")
    if not spec:
        return "", {}
    glyphs = fontlib.parse_art_file(str(paths.asset(spec["art"])))
    vram, max_tiles = spec["vram"], spec["max_tiles"]
    try:
        doc = hero_panel.load_data(paths.asset(spec["data"]))
        panel = hero_panel.render(doc, glyphs, vram // 32, max_tiles)
    except (ValueError, KeyError) as exc:
        raise BuildError(f"{seg}: hero panel: {exc}") from None
    tile_words = [
        int.from_bytes(panel.tiles[i : i + 2], "big") for i in range(0, len(panel.tiles), 2)
    ]
    src = [f"        section {spec['section']}", "        even"]
    src += _words("PANEL_TILES", tile_words)
    src += _words("PANEL_FULL", [w for m in panel.full for w in m])
    src += _words("PANEL_HALF", [w for m in panel.half for w in m])
    fw, fh = hero_panel.FULL
    hw, hh = hero_panel.HALF
    return "\n".join(src) + "\n", {
        "PANEL_TILE_WORDS": len(tile_words),
        "PANEL_SIG": tile_words[0],
        "PANEL_CORNER": panel.corner,
        "PANEL_WRITE": _vdp(vram, True),
        "PANEL_READ": _vdp(vram, False),
        "FULL_W": fw, "FULL_H": fh, "FULL_SIZE": fw * fh * 2,
        "HALF_W": hw, "HALF_H": hh, "HALF_SIZE": hw * hh * 2,
    }  # fmt: skip


def assembled(seg: Segment, paths: Paths) -> tuple[bytes, list[Edit], dict[str, int]]:
    """Assemble the patch this segment belongs to: its section's bytes, its hooks, the labels."""
    pdef = seg.get("patch_def")
    source = paths.asset(pdef["source"])
    if not source.exists():
        raise BuildError(f"{seg}: missing patch source {source}")
    extra, derived = _glyph_tables(seg, paths)
    panel_src, panel_syms = _panel_tables(seg, paths)
    extra += panel_src + _string_tables(seg, paths)
    symbols = {**(pdef.get("symbols") or {}), **derived, **panel_syms}
    try:
        out, labels = m68k.assemble_sections(
            source.read_text(encoding="utf-8") + "\n" + extra, seg.get("sections"), symbols
        )
    except m68k.AsmError as exc:
        raise BuildError(f"{seg}: {source.name}: {exc}") from None
    todo = []
    for at, expect, label in _hooks(seg):
        if label not in labels:
            raise BuildError(f"{seg}: hook at {at:06X} names unknown label {label!r}")
        todo.append(Edit(at, expect, patches.jmp_abs(labels[label])))
    return out[seg.get("section")], todo, labels


def touched(seg: Segment) -> list[tuple[int, int]]:
    """Every byte range a patch segment writes outside its own slot (no assembly needed)."""
    if seg.get("patch_def") is not None:
        return [(at, at + len(expect)) for at, expect, _l in _hooks(seg)]
    return [(e.at, e.end) for e in edits(seg)]


def _expected(seg: Segment) -> list[tuple[int, bytes]]:
    if seg.get("patch_def") is not None:
        return [(at, expect) for at, expect, _l in _hooks(seg)]
    return [(e.at, e.expect) for e in edits(seg)]


def edits(seg: Segment) -> list[Edit]:
    """The edits a routine patch segment makes outside its slot, validated against the slot."""
    found = _routine(seg)[0](seg)
    for e in found:
        if e.at < seg.end and seg.start < e.end:
            raise BuildError(f"{seg}: edit at 0x{e.at:06X} overlaps the patch's own slot")
    return found


def _edit_problem(rom: Rom, seg: Segment, at: int, expect: bytes) -> str | None:
    found = bytes(rom.data[at : at + len(expect)])
    if found == expect:
        return None
    return f"{seg}: 0x{at:06X} holds {found.hex(' ')}, expected {expect.hex(' ')}"


class PatchHandler(Handler):
    def __init__(self):
        self._applied: dict[str, tuple[bytes, list[Edit]]] = {}

    def sources(self, seg: Segment, paths: Paths) -> list[Path]:
        pdef = seg.get("patch_def")
        if pdef is not None:
            found = [paths.asset(pdef["source"])]
            if pdef.get("glyphs"):
                found.append(paths.asset(pdef["glyphs"]["art"]))
            if pdef.get("panel"):
                found += [paths.asset(pdef["panel"]["art"]), paths.asset(pdef["panel"]["data"])]
            if pdef.get("strings"):
                found.append(paths.asset(pdef["strings"]["path"]))
            return found
        if seg.get("strings_path") is None:
            return []  # generated from code; nothing under assets/
        return [_strings_path(seg, paths)]

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        return []  # the slot is free space in the base ROM; the sources are committed

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        if seg.get("patch_def") is not None:
            body, todo, _labels = assembled(seg, paths)
        else:
            todo = edits(seg)
            body = None
        problems = [p for e in todo if (p := _edit_problem(rom, seg, e.at, e.expect))]
        if problems:
            raise BuildError("\n".join(problems))
        if body is None:
            body = _routine(seg)[1](seg, paths)
        self.place(rom, seg, body, pad=seg.get("fill", 0xFF))
        for e in todo:
            rom.data[e.at : e.end] = e.new
        self._applied[seg.name] = (bytes(rom.data[seg.start : seg.end]), todo)
        where = ", ".join(f"{e.at:06X}" for e in todo) or "none"
        what = seg.get("routine") or f"{seg.get('patch')}/{seg.get('section')}"
        return f"{what}: {len(body)} B, edits at {where}"

    def verify_built(self, rom: Rom, seg: Segment) -> list[str]:
        """After the whole build: the slot and every edit still hold what this patch wrote."""
        if seg.name not in self._applied:
            return []
        slot, todo = self._applied[seg.name]
        problems = []
        if bytes(rom.data[seg.start : seg.end]) != slot:
            problems.append(f"{seg}: a later segment overwrote the patch's slot")
        for e in todo:
            if bytes(rom.data[e.at : e.end]) != e.new:
                problems.append(f"{seg}: a later segment overwrote the edit at 0x{e.at:06X}")
        return problems

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        try:
            expected = _expected(seg)
        except BuildError as exc:
            return [str(exc)]
        problems = [p for at, exp in expected if (p := _edit_problem(rom, seg, at, exp))]
        fill = seg.get("fill")
        if fill is None:
            problems.append(f"{seg}: patch without the fill byte of the space it occupies")
        elif any(b != fill for b in rom.data[seg.start : seg.end]):
            problems.append(f"{seg}: slot is not free space (expected fill 0x{fill:02X})")
        return problems
