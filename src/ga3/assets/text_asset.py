"""Text segments: one strings file per ROM region.

Also strings embedded in code: a ``code``/``data`` segment may declare
``strings`` (a list of ``[offset, length]``) and ``strings_path``. Those exact
spans are extracted to a committed strings file and written back on build; the
rest of the segment stays a passthrough of the base ROM.
"""

from __future__ import annotations

import itertools
from pathlib import Path

from .. import text
from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths, write_text
from .raw_asset import RawHandler


class TextHandler(Handler):
    committed = True

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        min_len = seg.get("min_len", text.DEFAULT_MIN_LEN)
        prose = seg.get("prose")
        if prose is None:
            rows = text.find_strings(rom.data, seg.start, seg.end, min_len)
        else:
            # only real text: printable runs clipped to the prose spans, so no
            # record ever covers code that merely decodes as text
            rows = [
                row for start, end in prose for row in text.find_strings(rom.data, start, end, 1)
            ]
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


def embedded_spans(seg: Segment) -> list[tuple[int, int]]:
    """The ``strings`` of a code/data segment as ``(offset, length)``, validated against it."""
    raw = seg.get("strings")
    if not isinstance(raw, list) or not raw:
        raise BuildError(f"{seg}: strings must be a non-empty list of [offset, length]")
    spans = []
    for item in raw:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in item)
        ):
            raise BuildError(f"{seg}: bad strings entry {item!r}; expected [0xOFFSET, length]")
        off, ln = item
        if ln < 1 or not (seg.start <= off and off + ln <= seg.end):
            raise BuildError(f"{seg}: string {off:06X}:{ln} lies outside the segment")
        spans.append((off, ln))
    spans.sort()
    for (a, la), (b, _lb) in itertools.pairwise(spans):
        if a + la > b:
            raise BuildError(f"{seg}: strings {a:06X}:{la} and {b:06X} overlap")
    return spans


class EmbeddedTextHandler(RawHandler):
    """Passthrough code/data whose declared strings live in a committed strings file."""

    def __init__(self):
        super().__init__(committed=False)

    def _text_path(self, seg: Segment, paths: Paths) -> Path:
        rel = seg.get("strings_path")
        if not isinstance(rel, str):
            raise BuildError(f"{seg}: strings needs strings_path (relative to assets/)")
        return paths.asset(rel)

    def sources(self, seg: Segment, paths: Paths) -> list[Path]:
        return [self._text_path(seg, paths)]

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        files = super().extract(rom, seg, paths)
        rows = text.records_at(rom.data, embedded_spans(seg))
        body = text.format_strings_file(rows, seg.name, seg.start, seg.end)
        return [*files, write_text(self._text_path(seg, paths), body)]

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        note = super().build(rom, seg, paths)
        path = self._text_path(seg, paths)
        if not path.exists():
            raise BuildError(f"{seg}: missing text file {path}")
        rows = text.parse_strings_file(str(path))
        spans = embedded_spans(seg)
        stray = [f"{off:06X}:{ln}" for off, ln, _t in rows if (off, ln) not in spans]
        if stray:
            raise BuildError(
                f"{seg}: {path.name} has records the map does not declare: {', '.join(stray)}"
            )
        try:
            changed = text.insert_strings(rom.data, rows, seg.start, seg.end)
        except ValueError as exc:
            raise BuildError(str(exc)) from None
        notes = [n for n in (note, f"{changed} string(s) changed" if changed else None) if n]
        return ", ".join(notes) or None

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        try:
            spans = embedded_spans(seg)
        except BuildError as exc:
            return [str(exc)]
        return [
            f"{seg}: string {off:06X}:{ln} holds bytes with no glyph"
            for off, ln in spans
            if any(b not in text.TEXT_BYTES for b in rom.data[off : off + ln])
        ]
