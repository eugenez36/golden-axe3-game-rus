"""Verbatim byte ranges: PCM, raw blobs, code, data, free space, unknown.

* ``pcm`` / ``raw`` are committed sources: the file is written back on build.
* ``code`` / ``data`` / ``unknown`` are extracted for browsing (gitignored) and
  taken from the base ROM on build unless the local file exists, in which case
  the local file wins -- that is how a hand-patched routine gets in.
* ``free`` regions are never extracted; the map records their fill byte and
  ``check`` confirms the base ROM really holds it.
"""

from __future__ import annotations

from pathlib import Path

from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths, write_bytes

CHUNK = 0x10000  # unknown regions are split into 64 KiB files


class RawHandler(Handler):
    def __init__(self, committed: bool, is_free: bool = False):
        self.committed = committed
        self.is_free = is_free

    def _files(self, seg: Segment, paths: Paths) -> list[tuple[Path, int, int]]:
        if seg.path:
            return [(paths.asset(seg.path), seg.start, seg.end)]
        # synthetic unknown segment: assets/raw/unknown_XXXXXX.raw, chunked
        out = []
        pos = seg.start
        while pos < seg.end:
            end = min(pos + CHUNK, seg.end)
            out.append((paths.asset(f"raw/unknown_{pos:06X}.raw"), pos, end))
            pos = end
        return out

    def sources(self, seg: Segment, paths: Paths) -> list[Path]:
        if not self.committed:
            return []  # passthrough files are optional overrides
        return [path for path, _s, _e in self._files(seg, paths)]

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        if self.is_free:
            return []
        written = []
        for path, s, e in self._files(seg, paths):
            written.append(write_bytes(path, bytes(rom.data[s:e])))
        return written

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        if self.is_free:
            return None
        applied = 0
        for path, s, e in self._files(seg, paths):
            if not path.exists():
                if self.committed:
                    raise BuildError(f"{seg}: missing asset file {path}")
                continue  # passthrough from the base ROM
            blob = path.read_bytes()
            if len(blob) != e - s:
                raise BuildError(f"{seg}: {path.name} is {len(blob)} bytes, slot is {e - s}")
            rom.data[s:e] = blob
            applied += 1
        return f"{applied} file(s)" if applied and not self.committed else None

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        if not self.is_free:
            return []
        fill = seg.get("fill")
        if fill is None:
            return [f"{seg}: free segment without a fill byte"]
        bad = {b for b in rom.data[seg.start : seg.end] if b != fill}
        if bad:
            return [f"{seg}: expected fill 0x{fill:02X}, found bytes {sorted(bad)[:8]}"]
        return []
