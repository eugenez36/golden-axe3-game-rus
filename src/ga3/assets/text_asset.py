"""Text segments: one strings file per ROM region."""

from __future__ import annotations

from pathlib import Path

from .. import text
from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths, write_text


class TextHandler(Handler):
    committed = True

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        rows = text.find_strings(
            rom.data, seg.start, seg.end, seg.get("min_len", text.DEFAULT_MIN_LEN)
        )
        body = text.format_strings_file(rows, seg.name, seg.start, seg.end)
        return [write_text(paths.asset(seg.path), body)]

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        path = paths.asset(seg.path)
        if not path.exists():
            raise BuildError(f"{seg}: missing text file {path}")
        rows = text.parse_strings_file(str(path))
        try:
            changed = text.insert_strings(rom.data, rows, seg.start, seg.end)
        except ValueError as exc:
            raise BuildError(str(exc)) from None
        return f"{changed} string(s) changed" if changed else None
