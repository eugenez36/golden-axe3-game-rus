"""The hero stats panel of the character select, rendered at build time.

The panel (variant B: name, magic, then four stats each with a bar and a
number) is drawn here into palette-0 colour indices, cut into 8x8 tiles that
are de-duplicated, and returned with one tilemap per hero: a full-width panel
for a one-player game (40 x 8 cells) and a half panel for each player of a
two-player game (20 x 9 cells). The patch ``hero_panel`` copies the tiles to
free VRAM and writes the hero's tilemap into plane A over the title.

Colours are indices of palette 0 on the select screen: the dialogue font's own
ink and background (white 6 on blue 12), yellow 13 for the bars, black 9 for
their empty part.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from . import table

BLUE, WHITE, YELLOW, BLACK = 0x0C, 0x06, 0x0D, 0x09
PRIORITY = 0x8000  # tilemap word: high priority, palette 0

FULL = (40, 8)  # cells: one player
HALF = (20, 9)  # cells: each player of two


@dataclass
class Panel:
    tiles: bytes  # 32 bytes a tile, the first is plain blue
    full: list[list[int]]  # per hero: FULL[0] * FULL[1] tilemap words, row by row
    half: list[list[int]]  # per hero: HALF[0] * HALF[1] words
    corner: int  # the top-left word of every map (the screen still shows the panel?)


def load_data(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    heroes = doc.get("heroes") or []
    if len(heroes) != 4:
        raise ValueError(f"{path.name}: expected 4 heroes in select-cursor order")
    return doc


SOURCES = ("hp", "constants", "walk")  # files the numbers come from, relative to assets/


def _values(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    values = doc.get("values")
    if not isinstance(values, dict):
        raise ValueError(f"{path.name}: expected a values: mapping")
    return values


def resolve(doc: dict, hp: dict, constants: dict, walk: dict) -> dict:
    """The panel's numbers from the game's tables: a copy of ``doc`` with hp, hit,
    super and speed on every hero and the bars for hp, super and speed.

    ``hp`` is the HP table (``slot_0``..``slot_3``: max HP by max-HP level),
    ``constants`` the gameplay constants (``KEY_hit``, ``KEY_super``: the power
    of a hero's first combo hit and launch) and ``walk`` the walking speeds
    (``KEY_x``, signed 8.8 pixels per frame); ``KEY`` is each hero's ``key``.
    """
    try:
        heroes = []
        for hero in doc["heroes"]:
            key = hero["key"]
            heroes.append(
                {
                    **hero,
                    "hp": int(hp["slot_0"]),
                    "hit": int(constants[f"{key}_hit"]),
                    "super": int(constants[f"{key}_super"]),
                    "speed": int(int(walk[f"{key}_x"]) * 60 / 256 + 0.5),  # px per second
                }
            )
        bars = {
            **doc.get("bars", {}),
            "hp": int(hp["slot_3"]),
            "super": max(h["super"] for h in heroes),
            "speed": max(h["speed"] for h in heroes),
        }
        if "tempo" not in bars:
            raise KeyError("bars.tempo")
    except KeyError as exc:
        raise ValueError(f"hero panel: missing {exc}") from None
    return {**doc, "heroes": heroes, "bars": bars}


def source_paths(doc: dict, assets: Path) -> dict[str, Path]:
    """The files named under ``sources`` (hp, constants, walk), relative to ``assets``."""
    sources = doc.get("sources") or {}
    missing = [k for k in SOURCES if not isinstance(sources.get(k), str)]
    if missing:
        raise ValueError(f"hero panel: sources needs {', '.join(missing)}")
    return {k: assets / sources[k] for k in SOURCES}


def load_resolved(path: Path, assets: Path) -> dict:
    """``load_data`` plus ``resolve`` from the files its ``sources`` name."""
    doc = load_data(path)
    files = source_paths(doc, assets)
    for p in files.values():
        if not p.exists():
            raise ValueError(f"{path.name}: missing {p}")
    return resolve(doc, *(_values(files[k]) for k in SOURCES))


class _Canvas:
    def __init__(self, cells_w: int, cells_h: int):
        self.w, self.h = cells_w * 8, cells_h * 8
        self.px = [[BLUE] * self.w for _ in range(self.h)]

    def rect(self, x0: int, y0: int, x1: int, y1: int, colour: int) -> None:
        for x in range(x0, x1 + 1):
            self.px[y0][x] = self.px[y1][x] = colour
        for y in range(y0, y1 + 1):
            self.px[y][x0] = self.px[y][x1] = colour

    def fill(self, x0: int, y0: int, x1: int, y1: int, colour: int) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.px[y][x] = colour

    def text(self, col: int, row: int, s: str, glyphs: dict[int, bytes]) -> None:
        for k, b in enumerate(table.encode(s)):
            tile = glyphs[b]
            for y in range(8):
                for x in range(8):
                    byte = tile[y * 4 + x // 2]
                    self.px[row * 8 + y][(col + k) * 8 + x] = byte >> 4 if x % 2 == 0 else byte & 15

    def bar(self, col: int, row: int, cells: int, frac: float) -> None:
        x0, x1 = col * 8, (col + cells) * 8 - 1
        y0, y1 = row * 8 + 1, row * 8 + 6
        self.rect(x0, y0, x1, y1, WHITE)
        self.fill(x0 + 1, y0 + 1, x1 - 1, y1 - 1, BLACK)
        n = round(max(0.0, min(1.0, frac)) * (x1 - x0 - 1))
        if n:
            self.fill(x0 + 1, y0 + 1, x0 + n, y1 - 1, YELLOW)

    def tiles(self) -> list[bytes]:
        out = []
        for cy in range(self.h // 8):
            for cx in range(self.w // 8):
                t = bytearray()
                for y in range(8):
                    row = self.px[cy * 8 + y][cx * 8 : cx * 8 + 8]
                    t += bytes(row[i] << 4 | row[i + 1] for i in range(0, 8, 2))
                out.append(bytes(t))
        return out


def _stats(hero: dict, labels: dict, bars: dict) -> list[tuple[str, float, str]]:
    return [
        (labels["hp"], hero["hp"] / bars["hp"], str(hero["hp"])),
        (labels["hit"], hero["super"] / bars["super"], f"{hero['hit']}/{hero['super']}"),
        (labels["tempo"], bars["tempo"] / hero["tempo"], f"{hero['tempo']:.2f}"),
        (labels["speed"], hero["speed"] / bars["speed"], str(hero["speed"])),
    ]


def _full(hero: dict, doc: dict, glyphs: dict[int, bytes]) -> _Canvas:
    c = _Canvas(*FULL)
    c.rect(1, 1, c.w - 2, c.h - 2, WHITE)
    c.text(1, 1, hero["name"], glyphs)
    magic = doc["labels"]["magic"] + hero["magic"]
    c.text(FULL[0] - 1 - len(magic), 1, magic, glyphs)
    for i, (label, frac, value) in enumerate(_stats(hero, doc["labels"], doc["bars"])):
        col, row = 1 + (i % 2) * 19, 3 + (i // 2) * 2  # two blocks of 18 cells
        c.text(col, row, label, glyphs)
        c.bar(col + 9, row, 4, frac)
        c.text(col + 18 - len(value), row, value, glyphs)
    return c


def _half(hero: dict, doc: dict, glyphs: dict[int, bytes]) -> _Canvas:
    c = _Canvas(*HALF)
    c.rect(1, 1, c.w - 2, c.h - 2, WHITE)
    c.text(1, 1, hero["name"], glyphs)
    c.text(1, 2, doc["labels"]["magic"] + hero["magic"], glyphs)
    for i, (label, frac, value) in enumerate(_stats(hero, doc["labels"], doc["bars"])):
        row = 3 + i
        c.text(1, row, label, glyphs)
        c.bar(10, row, 4, frac)
        c.text(18 - len(value) + 1, row, value, glyphs)
    return c


def render(doc: dict, glyphs: dict[int, bytes], vram_tile: int, max_tiles: int) -> Panel:
    """Tiles and tilemaps of every panel; ``vram_tile`` is the first tile's VRAM index."""
    unique: dict[bytes, int] = {bytes([BLUE << 4 | BLUE]) * 32: 0}

    def words(canvas: _Canvas) -> list[int]:
        out = []
        for t in canvas.tiles():
            idx = unique.setdefault(t, len(unique))
            out.append(PRIORITY | (vram_tile + idx))
        return out

    full, half = [], []
    for hero in doc["heroes"]:
        if not all(k in hero for k in ("hp", "hit", "super", "speed")):
            raise ValueError("hero panel: the numbers are not resolved (see resolve)")
        if len(table.encode(hero["name"])) > HALF[0] - 2:
            raise ValueError(f"name {hero['name']!r} is longer than {HALF[0] - 2} characters")
        full.append(words(_full(hero, doc, glyphs)))
        half.append(words(_half(hero, doc, glyphs)))
    if len(unique) > max_tiles:
        raise ValueError(f"the panel needs {len(unique)} tiles, VRAM holds {max_tiles}")
    tiles = b"".join(sorted(unique, key=unique.get))
    return Panel(tiles, full, half, full[0][0])
