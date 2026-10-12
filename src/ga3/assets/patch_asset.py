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

``fill`` is the free-space byte the unused tail of the slot keeps. Every edit
is checked against the image before anything is written, so a map that drifted
from the code fails the build instead of corrupting it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .. import patches, table, text
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


def edits(seg: Segment) -> list[Edit]:
    """The edits a patch segment makes outside its slot, validated against the slot."""
    found = _routine(seg)[0](seg)
    for e in found:
        if e.at < seg.end and seg.start < e.end:
            raise BuildError(f"{seg}: edit at 0x{e.at:06X} overlaps the patch's own slot")
    return found


def _edit_problem(rom: Rom, seg: Segment, e: Edit) -> str | None:
    found = bytes(rom.data[e.at : e.end])
    if found == e.expect:
        return None
    return f"{seg}: 0x{e.at:06X} holds {found.hex(' ')}, expected {e.expect.hex(' ')}"


class PatchHandler(Handler):
    def sources(self, seg: Segment, paths: Paths) -> list[Path]:
        if seg.get("strings_path") is None:
            return []  # generated from code; nothing under assets/
        return [_strings_path(seg, paths)]

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        return []  # the slot is free space in the base ROM; the sources are committed

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        todo = edits(seg)
        problems = [p for e in todo if (p := _edit_problem(rom, seg, e))]
        if problems:
            raise BuildError("\n".join(problems))
        body = _routine(seg)[1](seg, paths)
        self.place(rom, seg, body, pad=seg.get("fill", 0xFF))
        for e in todo:
            rom.data[e.at : e.end] = e.new
        where = ", ".join(f"{e.at:06X}" for e in todo)
        return f"{seg.get('routine')}: {len(body)} B, edits at {where}"

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        try:
            todo = edits(seg)
        except BuildError as exc:
            return [str(exc)]
        problems = [p for e in todo if (p := _edit_problem(rom, seg, e))]
        fill = seg.get("fill")
        if fill is None:
            problems.append(f"{seg}: patch without the fill byte of the space it occupies")
        elif any(b != fill for b in rom.data[seg.start : seg.end]):
            problems.append(f"{seg}: slot is not free space (expected fill 0x{fill:02X})")
        return problems
