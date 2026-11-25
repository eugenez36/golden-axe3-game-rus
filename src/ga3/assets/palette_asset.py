"""Palettes in ROM as ``.pal`` text: back-to-back runs of 16 CRAM words.

With ``script: true`` every palette is a whole-line palette script (the format
the game reads at 0112A2): a header byte ``F0 | line`` (16 words, the line to
load), a byte 00 (from colour 0), then the 16 words. The ``.pal`` keeps the
line in the palette's header, ``[palette N line L]``, so the round trip is
exact. ``labels`` (one per palette) become comments after the headers.
"""

from __future__ import annotations

import struct
from pathlib import Path

from ..palette import format_pal, parse_pal_words
from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths, write_text


def _stride(seg: Segment) -> int:
    return 34 if seg.get("script") else 32


class PaletteHandler(Handler):
    committed = True

    def _decode(self, data: bytes, seg: Segment) -> tuple[list[int] | None, bytes]:
        stride, lines, words = _stride(seg), [], bytearray()
        for o in range(seg.start, seg.end, stride):
            if seg.get("script"):
                lines.append(data[o] & 0x0F)
                o += 2
            words += data[o : o + 32]
        return (lines if seg.get("script") else None), bytes(words)

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        lines, words = self._decode(bytes(rom.data), seg)
        n = seg.size // _stride(seg)
        comments = [
            f"{seg.name}: {n} palettes at {seg.start:06X}-{seg.end:06X} (rom_map.yml)",
            "each colour: #RRGGBB as Genesis Plus GX shows it, then the CRAM word;",
            "to change a colour, edit one of them and delete the other (or edit both alike)",
        ]
        if lines is not None:
            comments.append("each palette is a palette script: 'line L' is the CRAM line it loads")
        text = format_pal(words, comments, lines, seg.get("labels"))
        return [write_text(paths.asset(seg.path), text)]

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        path = paths.asset(seg.path)
        if not path.exists():
            raise BuildError(f"{seg}: missing asset file {path}")
        try:
            pals = parse_pal_words(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise BuildError(f"{seg}: {path.name}: {exc}") from None
        n = seg.size // _stride(seg)
        if len(pals) != n:
            raise BuildError(f"{seg}: {path.name} has {len(pals)} palettes, the slot holds {n}")
        out = bytearray()
        for i, (line, words) in enumerate(pals):
            if seg.get("script"):
                if line is None:
                    raise BuildError(f"{seg}: {path.name}: palette {i} needs 'line L'")
                out += bytes([0xF0 | line, 0x00])
            elif line is not None:
                raise BuildError(f"{seg}: {path.name}: palette {i}: these palettes have no line")
            out += struct.pack(">16H", *words)
        changed = bytes(out) != bytes(rom.data[seg.start : seg.end])
        self.place(rom, seg, bytes(out), pad=None)
        return "changed" if changed else None

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        stride, problems = _stride(seg), []
        if seg.size % stride:
            return [f"{seg}: size {seg.size} is not a multiple of {stride}"]
        n = seg.size // stride
        labels = seg.get("labels")
        if labels is not None and len(labels) != n:
            problems.append(f"{seg}: {len(labels)} labels for {n} palettes")
        data = bytes(rom.data)
        for i, o in enumerate(range(seg.start, seg.end, stride)):
            if seg.get("script"):
                if data[o] & 0xF0 != 0xF0 or data[o + 1] != 0:
                    problems.append(
                        f"{seg}: palette {i}: header {data[o : o + 2].hex()} is not F_ 00"
                    )
                o += 2
            bad = [k for k in range(16) if struct.unpack_from(">H", data, o + 2 * k)[0] & 0xF111]
            if bad:
                problems.append(f"{seg}: palette {i}: colours {bad} are not CRAM words")
        return problems
