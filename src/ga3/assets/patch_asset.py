"""Generated code: a routine placed in its own segment plus a ``jmp`` hook into it.

A ``patch`` segment owns the bytes of its routine (carved out of verified free
space) and names one instruction pair elsewhere that it replaces with
``jmp start.l``. The map entry carries every address:

* ``routine``    which builder in ``ga3.patches`` produces the body
* ``hook``       where the six replaced bytes live; ``hook_bytes`` is what the
                 base ROM holds there (hex), checked before anything is written
* ``fill``       the free-space byte the unused tail of the slot keeps

plus the routine's own parameters. Nothing is extracted: the source of truth
is ``ga3.patches`` and the package version.
"""

from __future__ import annotations

from pathlib import Path

from .. import patches
from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths

HOOK_SIZE = 6


def _hook(seg: Segment) -> tuple[int, bytes]:
    hook = seg.get("hook")
    raw = seg.get("hook_bytes")
    if not isinstance(hook, int) or not isinstance(raw, str):
        raise BuildError(f"{seg}: patch needs hook (0x address) and hook_bytes (hex string)")
    try:
        expect = bytes.fromhex(raw)
    except ValueError:
        raise BuildError(f"{seg}: hook_bytes {raw!r} is not hex") from None
    if len(expect) != HOOK_SIZE:
        raise BuildError(f"{seg}: hook_bytes must be {HOOK_SIZE} bytes, got {len(expect)}")
    if seg.start - HOOK_SIZE < hook < seg.end:
        raise BuildError(f"{seg}: hook 0x{hook:06X} overlaps the patch's own slot")
    return hook, expect


def _body(seg: Segment) -> bytes:
    name = seg.get("routine")
    if name == "menu_version":
        try:
            return patches.menu_version(
                vram_end=seg.get("vram_end"),
                attr=seg.get("attr"),
                return_to=seg.get("return_to"),
                text=patches.version_text(),
            )
        except (TypeError, ValueError) as exc:
            raise BuildError(f"{seg}: {exc}") from None
    raise BuildError(f"{seg}: unknown routine {name!r}")


def _hook_problem(rom: Rom, seg: Segment, hook: int, expect: bytes) -> str | None:
    found = bytes(rom.data[hook : hook + HOOK_SIZE])
    if found == expect:
        return None
    return f"{seg}: hook 0x{hook:06X} holds {found.hex(' ')}, expected {expect.hex(' ')}"


class PatchHandler(Handler):
    def sources(self, seg: Segment, paths: Paths) -> list[Path]:
        return []  # generated from code; nothing under assets/

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        return []

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        hook, expect = _hook(seg)
        problem = _hook_problem(rom, seg, hook, expect)
        if problem:
            raise BuildError(problem)
        body = _body(seg)
        self.place(rom, seg, body, pad=seg.get("fill", 0xFF))
        rom.data[hook : hook + HOOK_SIZE] = patches.jmp_abs(seg.start)
        return f"{seg.get('routine')}: {len(body)} B, hook at {hook:06X}"

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        try:
            hook, expect = _hook(seg)
        except BuildError as exc:
            return [str(exc)]
        problems = []
        problem = _hook_problem(rom, seg, hook, expect)
        if problem:
            problems.append(problem)
        fill = seg.get("fill")
        if fill is None:
            problems.append(f"{seg}: patch without the fill byte of the space it occupies")
        elif any(b != fill for b in rom.data[seg.start : seg.end]):
            problems.append(f"{seg}: slot is not free space (expected fill 0x{fill:02X})")
        return problems
