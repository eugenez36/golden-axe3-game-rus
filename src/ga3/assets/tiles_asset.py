"""Uncompressed 4bpp tile art as indexed PNG sheets.

The region is cut into sheets of ``sheet_tiles`` tiles (default 512, laid out
``cols`` = 32 wide). Sheets are palette-mode PNGs carrying the raw palette
indices, so the round trip is lossless whatever display palette is attached.
Editors must keep the image indexed; RGB files are rejected on build.
"""

from __future__ import annotations

from pathlib import Path

from .. import tiles as tilemod
from ..palette import load_pal
from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths

DEFAULT_SHEET = 512
DEFAULT_COLS = 32


class TilesHandler(Handler):
    committed = True

    def _sheets(self, seg: Segment) -> list[tuple[int, int]]:
        per = seg.get("sheet_tiles", DEFAULT_SHEET)
        total = seg.size // tilemod.TILE_SIZE
        out = []
        i = 0
        while i < total:
            n = min(per, total - i)
            out.append((i, n))
            i += n
        return out

    def _sheet_path(self, seg: Segment, paths: Paths, idx: int) -> Path:
        return paths.asset(seg.path) / f"{seg.get('prefix', 'sheet')}_{idx:02d}.png"

    def _palette(self, seg: Segment, paths: Paths, rm_palettes: dict | None = None):
        ref = seg.get("palette")
        if not ref or ref == "gray":
            return None
        name, _, idx = ref.partition("/")
        pal_file = paths.asset(f"palettes/{name}.pal")
        if not pal_file.exists():
            return None
        pals = load_pal(str(pal_file))
        return pals[int(idx or 0)]

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        if seg.size % tilemod.TILE_SIZE:
            raise BuildError(f"{seg}: size {seg.size} is not a multiple of 32")
        cols = seg.get("cols", DEFAULT_COLS)
        palette = self._palette(seg, paths)
        written = []
        for idx, (first, n) in enumerate(self._sheets(seg)):
            img = tilemod.render_indexed(
                rom.data, seg.start + first * tilemod.TILE_SIZE, n, cols, palette
            )
            path = self._sheet_path(seg, paths, idx)
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, optimize=True)
            written.append(path)
        return written

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        out = bytearray()
        for idx, (_first, n) in enumerate(self._sheets(seg)):
            path = self._sheet_path(seg, paths, idx)
            if not path.exists():
                raise BuildError(f"{seg}: missing sheet {path}")
            try:
                out += tilemod.import_indexed(str(path), count=n)
            except ValueError as exc:
                raise BuildError(str(exc)) from None
        changed = bytes(out) != bytes(rom.data[seg.start : seg.end])
        self.place(rom, seg, bytes(out), pad=None)
        return "changed" if changed else None
