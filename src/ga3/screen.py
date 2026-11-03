"""Indexed PNG art -> Mega Drive tiles, plane maps, sprite tiles and palettes.

An art file is a paletted PNG whose palette indices are the CRAM indices of
one palette line, and whose sides are multiples of 8. Index 0 is transparent
on screen. The palette's first ``count`` entries become CRAM words.

``plane`` cuts one or more images into 8x8 cells, keeps each distinct cell
once (no flips: some of the game's consumers, the logo's 2x scaler among them,
cannot mirror a cell) and returns the tiles plus one map per image, each word
being ``attr + first tile + index``. ``sprite`` cuts an image into the pieces
of a sprite mapping, in the VDP's order: each piece column by column.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .palette import RGB, rgb_to_word
from .tiles import TILE_H, TILE_W, tile_encode


@dataclass
class Art:
    width: int
    height: int
    pixels: list[list[int]]
    palette: list[RGB]

    def cell(self, cx: int, cy: int) -> bytes:
        rows = [
            self.pixels[cy * TILE_H + y][cx * TILE_W : (cx + 1) * TILE_W] for y in range(TILE_H)
        ]
        return tile_encode(rows)

    @property
    def cols(self) -> int:
        return self.width // TILE_W

    @property
    def rows(self) -> int:
        return self.height // TILE_H


def load(path: str | Path) -> Art:
    from PIL import Image

    with Image.open(path) as img:
        if img.mode != "P":
            raise ValueError(f"{path}: expected a paletted PNG, got mode {img.mode}")
        w, h = img.size
        if w % TILE_W or h % TILE_H:
            raise ValueError(f"{path}: {w}x{h} is not a whole number of 8x8 cells")
        flat = list(img.get_flattened_data())
        raw = img.getpalette() or []
    if max(flat, default=0) > 15:
        raise ValueError(f"{path}: uses palette index {max(flat)}, a line has 16")
    palette = [tuple(raw[i : i + 3]) for i in range(0, min(len(raw), 48), 3)]
    pixels = [flat[y * w : (y + 1) * w] for y in range(h)]
    return Art(w, h, pixels, palette)  # type: ignore[arg-type]


def palette_words(art: Art, count: int) -> list[int]:
    if len(art.palette) < count:
        raise ValueError(f"the art has {len(art.palette)} palette entries, {count} wanted")
    return [rgb_to_word(c) for c in art.palette[:count]]


def plane(arts: list[Art], first_tile: int, attr: int = 0) -> tuple[bytes, list[list[int]]]:
    """Shared tiles for ``arts`` and their maps, row by row."""
    seen: dict[bytes, int] = {}
    tiles = bytearray()
    maps = []
    for art in arts:
        words = []
        for cy in range(art.rows):
            for cx in range(art.cols):
                cell = art.cell(cx, cy)
                if cell not in seen:
                    seen[cell] = len(seen)
                    tiles += cell
                words.append(attr + first_tile + seen[cell])
        maps.append(words)
    return bytes(tiles), maps


def sprite(art: Art, pieces: list[tuple[int, int, int, int]]) -> bytes:
    """Tiles of ``pieces`` (cell x, cell y, width, height; at most 4 x 4), each column by column."""
    out = bytearray()
    for x, y, w, h in pieces:
        if not (1 <= w <= 4 and 1 <= h <= 4):
            raise ValueError(f"sprite piece {w}x{h}: the VDP draws 1..4 cells a side")
        if x + w > art.cols or y + h > art.rows:
            raise ValueError(
                f"sprite piece at {x},{y} {w}x{h} leaves the {art.cols}x{art.rows} art"
            )
        for cx in range(x, x + w):
            for cy in range(y, y + h):
                out += art.cell(cx, cy)
    return bytes(out)
