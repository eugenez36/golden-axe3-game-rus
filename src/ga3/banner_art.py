"""The menu art drawn from docs/branding/banner.svg, as indexed PNGs for ``ga3.screen``.

The banner is pixel art: every shape is a list of ``Mx yhWvHh-Wz`` squares, so
it is read directly, without an SVG renderer. Its logo squares are 16 px on an
8 px grid and become 2x2 Mega Drive pixels on a 2 px grid (a quarter of the
banner's scale); the "III" squares (12 px on 6 px) the same 2 px per step.

The game's logo map is 38 x 6 cells at plane column 2, each letter in its own
4-cell column (G O L D E N, two blank cells, A X E): the title slides those
columns in four at a time, the 2x intro scroller and the ending copy letters by
that grid, so the banner's letters are spread onto it.

Palette line 1 (the logo's): 0 transparent, 1 the cursor's gold, 2..9 the gold
gradient top to bottom, rotated by SHADE_SHIFT (the title rotates 2..9 for its
shine, so only their order matters; gold text in the font's ink 6 gets the
gradient's bright gold), 10 a pale gold, 11 the black outline.

Palette line 0 (the sky): 0..5 a navy ramp, dithered down the banner's
dark-light-dark gradient (0 is also the backdrop), 4, 6 and 7 the cloud
blues, 8 the bottom bar, 9 its gold line.
"""

from __future__ import annotations

import re
from pathlib import Path

from .palette import RGB, VDP_LEVELS, rgb_to_word, word_to_rgb

H = 224
SKY_W = 256  # the sky map is 32 cells wide, written twice across the 64-cell plane
LOGO_COLS, LOGO_ROWS = 38, 6
LETTERS = "GOLDENAXE"
LETTER_COL = [0, 4, 8, 12, 16, 20, 26, 30, 34]  # first cell of each letter (the game's grid)
III_COLS, III_ROWS = 10, 6
TH_COLS = 8  # the ending's "TH" of THE END: two letters of the logo's grid, from its tiles
BAR_TOP = 207  # the gold line; the black bar below it holds the text row 26
CLOUD_PERIOD = 64

GOLD_SHADES = 8
SHADE_SHIFT = 2  # shade k at index 2 + (k + 2) % 8: index 6, the font's ink, is the bright gold
CURSOR, PALE, OUTLINE = 1, 10, 11
NAVY = [(0, 0, 1), (0, 1, 2), (0, 1, 3), (1, 2, 3), (1, 2, 4), (1, 3, 5)]  # VDP levels r, g, b
CLOUDS = [(2, 3, 5), (2, 4, 6)]
BAR, LINE = 8, 9


def _hex(s: str) -> RGB:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _md(c: RGB) -> RGB:
    return word_to_rgb(rgb_to_word(c))


def _levels(t: tuple[int, int, int]) -> RGB:
    return VDP_LEVELS[t[0]], VDP_LEVELS[t[1]], VDP_LEVELS[t[2]]


class Banner:
    def __init__(self, svg: str):
        self.svg = svg
        self.paths = [
            (fill, [tuple(map(int, r)) for r in re.findall(r"M(\d+) (\d+)h(\d+)v(\d+)", d)])
            for fill, d in re.findall(r'<path fill="([^"]+)" d="([^"]+)"', svg)
        ]

    def gradient(self, name: str) -> list[tuple[float, RGB]]:
        m = re.search(rf'<linearGradient id="{name}".*?</linearGradient>', self.svg, re.S)
        if not m:
            raise ValueError(f"banner: no gradient {name!r}")
        stops = re.findall(r'offset="([\d.]+)" stop-color="(#[0-9a-f]+)"', m.group(0))
        return [(float(o), _hex(c)) for o, c in stops]

    def shape(self, index: int) -> tuple[list, list]:
        """Black and gold squares of the index-th gold shape (0 the logo, 1 "III")."""
        pairs = [
            (self.paths[i][1], self.paths[i + 1][1])
            for i in range(len(self.paths) - 1)
            if self.paths[i][0] == "#000" and self.paths[i + 1][0] == "url(#gold)"
        ]
        return pairs[index]

    def cursor(self) -> list:
        """The gold cursor's squares: the first solid gold path (at 0,0; its group moves it)."""
        return next(r for f, r in self.paths if f == "#f5b301")


def _lerp(stops: list[tuple[float, RGB]], t: float) -> RGB:
    t = min(1.0, max(0.0, t))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:], strict=False):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * f) for a, b in zip(c0, c1, strict=True))  # type: ignore[return-value]
    return stops[-1][1]


def logo_palette(banner: Banner) -> list[RGB]:
    gold = banner.gradient("gold")
    pal: list[RGB] = [(0, 0, 0)] * 12
    pal[CURSOR] = _md(_hex("#f5b301"))
    for k in range(GOLD_SHADES):
        pal[2 + (k + SHADE_SHIFT) % GOLD_SHADES] = _md(_lerp(gold, (k + 0.5) / GOLD_SHADES))
    pal[PALE] = _md(_hex("#fff3b0"))
    return pal


def title_gold(banner: Banner) -> list[RGB]:
    """Seven golds, light to dark, for a stone-grey ramp (the duel select's ВЫБОР ГЕРОЯ, 1-7)."""
    golds = sorted((c for _t, c in banner.gradient("gold")), key=lambda c: -sum(c))
    ramp = [(i / (len(golds) - 1), c) for i, c in enumerate(golds)]
    return [(0, 0, 0)] + [_md(_lerp(ramp, k / 6)) for k in range(7)]


def sky_palette() -> list[RGB]:
    return [_levels(t) for t in NAVY + CLOUDS] + [_md(_hex("#05090f")), _md(_hex("#f5b301"))]


def _blank(w: int, h: int) -> list[list[int]]:
    return [[0] * w for _ in range(h)]


def _draw(px, black, gold, x0: int, y0: int, grid: int, ox: int, oy: int) -> None:
    """Squares at 2 MD px per banner grid step; the gold shaded by its row within the shape."""
    top = min(y for _x, y, _w, _h in gold)
    bottom = max(y + h for _x, y, _w, h in gold)
    for rects, is_gold in ((black, False), (gold, True)):
        for x, y, w, h in rects:
            X = ox + (x - x0) * 2 // grid
            Y = oy + (y - y0) * 2 // grid
            for yy in range(h * 2 // grid):
                by = y + yy * grid / 2
                shade = min(GOLD_SHADES - 1, int((by - top) / (bottom - top) * GOLD_SHADES))
                c = 2 + (shade + SHADE_SHIFT) % GOLD_SHADES if is_gold else OUTLINE
                for xx in range(w * 2 // grid):
                    if 0 <= Y + yy < len(px) and 0 <= X + xx < len(px[0]):
                        px[Y + yy][X + xx] = c


def _letters(black: list, gold: list) -> list[tuple[list, list, int, int]]:
    """Split the logo into letters: the gold of neighbours never touches, the outlines do.

    Each letter is its gold span plus the outline squares starting within one grid
    step of it (an outline square is 16 px wide: 8 px out on each side).
    """
    cover = sorted({c for x, _y, w, _h in gold for c in range(x, x + w)})
    spans, start = [], cover[0]
    for a, b in zip(cover, cover[1:], strict=False):
        if b != a + 1:
            spans.append((start, a + 1))
            start = b
    spans.append((start, cover[-1] + 1))
    if len(spans) != len(LETTERS):
        raise ValueError(f"banner logo: found {len(spans)} letters, expected {len(LETTERS)}")
    return [
        ([r for r in black if a - 8 <= r[0] < b], [r for r in gold if a <= r[0] < b], a - 8, b + 8)
        for a, b in spans
    ]


# The banner's letters are a 5 x 7 bitmap font: a pixel is a 16 px gold square
# every 16 px, and the outline is a 16 px black square at each of these grid
# steps (8 px) around a gold one -- a ring plus a drop shadow. That rule
# redraws the banner's own letters (23 of 1058 squares more), and draws the two
# letters the ending needs that the banner lacks.
GLYPHS = {
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
}
RING = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
    (1, 2),
    (2, 1),
    (2, 2),
]


def _glyph(rows: list[str], x0: int, y0: int) -> tuple[list, list]:
    gold = [
        (x0 + 8 + 16 * c, y0 + 8 + 16 * r, 16, 16)
        for r, row in enumerate(rows)
        for c, ch in enumerate(row)
        if ch == "#"
    ]
    black = sorted({(x + dx * 8, y + dy * 8, 16, 16) for x, y, _w, _h in gold for dx, dy in RING})
    return black, gold


def the_th(banner: Banner) -> list[list[int]]:
    """T and H for the ending's THE END, each in a logo column, as tall as the logo's letters."""
    black, _gold = banner.shape(0)
    y0 = min(y for _x, y, _w, _h in black)
    height = (max(y + h for _x, y, _w, h in black) - y0) * 2 // 8
    px = _blank(TH_COLS * 8, LOGO_ROWS * 8)
    for k, ch in enumerate("TH"):
        gb, gg = _glyph(GLYPHS[ch], -8, y0)
        _draw(px, gb, gg, -8, y0, 8, k * 32, (LOGO_ROWS * 8 - height) // 2)
    return px


def logo(banner: Banner) -> list[list[int]]:
    black, gold = banner.shape(0)
    y0 = min(y for _x, y, _w, _h in black)
    height = (max(y + h for _x, y, _w, h in black) - y0) * 2 // 8
    oy = (LOGO_ROWS * 8 - height) // 2
    px = _blank(LOGO_COLS * 8, LOGO_ROWS * 8)
    for (lb, lg, a, _b), col in zip(_letters(black, gold), LETTER_COL, strict=True):
        ox = col * 8  # left in its column: 16 px of screen left of the logo, 8 right of it
        _draw(px, lb, lg, a, y0, 8, ox, oy)
    return px


def iii(banner: Banner) -> list[list[int]]:
    black, gold = banner.shape(1)
    x0 = min(x for x, _y, _w, _h in black)
    y0 = min(y for _x, y, _w, _h in black)
    width = (max(x + w for x, _y, w, _h in black) - x0) * 2 // 6
    height = (max(y + h for _x, y, _w, h in black) - y0) * 2 // 6
    px = _blank(III_COLS * 8, III_ROWS * 8)
    _draw(px, black, gold, x0, y0, 6, (III_COLS * 8 - width) // 2, (III_ROWS * 8 - height) // 2)
    return px


def sky(
    bar: bool = True, banded: bool = False, cloud_bands: int = 1, width: int = SKY_W
) -> list[list[int]]:
    """Navy ramp down the banner's gradient, checker dither, cloud strips, the bar.

    ``banded`` takes the ramp at the middle of each 8-pixel row, so a row of
    cells repeats one tile between the clouds, and ``cloud_bands`` = n keeps
    every n-th band of clouds: fewer tiles, for screens with less VRAM to
    spare. Without ``bar`` the sky goes on to the bottom.
    """
    ramp = len(NAVY)
    bottom = BAR_TOP if bar else H
    px = _blank(width, H)
    for y in range(H):
        t = (y // 8 * 8 + 4 if banded else y) / H
        pos = (t / 0.55 if t < 0.55 else (1 - t) / 0.45) * (ramp - 1.5) + 0.25
        for x in range(width):
            v = pos + (0.25 if (x + y) % 2 else -0.25)
            px[y][x] = max(0, min(ramp - 1, round(v)))
    # the banner's cloud pattern (160 x 64 px) at 64 x 32 px, strips 2 px high,
    # each band of strips shifted against the one above; opacity picks the blue
    strips = [(0, 16, 48, 6), (8, 8, 24, 6), (72, 40, 64, 7), (88, 32, 24, 7), (120, 0, 32, 4)]
    for band, ty in enumerate(range(0, bottom - 8, 32)):
        if band % cloud_bands:
            continue
        shift = (band * 37) % CLOUD_PERIOD
        for x, y, w, c in strips:
            for yy in range(y // 2, y // 2 + 2):
                if ty + yy >= bottom - 4:
                    continue
                for xx in range(x * CLOUD_PERIOD // 160, (x + w) * CLOUD_PERIOD // 160):
                    for rep in range(0, width, CLOUD_PERIOD):
                        px[ty + yy][(rep + xx + shift) % width] = c
    if bar:
        for y in range(BAR_TOP, H):
            px[y] = [LINE if y == BAR_TOP else BAR] * width
    return px


def cursor(banner: Banner) -> list[list[int]]:
    """Tile 10, the cursor, and tile 11 blank: the game uploads both (32 words, 015850)."""
    px = _blank(16, 8)
    for x, y, _w, _h in banner.cursor():
        px[y // 4][1 + x // 4] = CURSOR
    return px


def save(px: list[list[int]], palette: list[RGB], path: Path) -> None:
    from PIL import Image

    img = Image.new("P", (len(px[0]), len(px)))
    flat = [c for rgb in palette for c in rgb]
    img.putpalette(flat + [0] * (48 - len(flat)))
    img.putdata([c for row in px for c in row])
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=False)


def generate(svg_path: Path, out_dir: Path) -> list[Path]:
    banner = Banner(svg_path.read_text(encoding="utf-8"))
    gold = logo_palette(banner)
    files = {
        "title_logo.png": (logo(banner), gold),
        "title_iii.png": (iii(banner), gold),
        "ending_th.png": (the_th(banner), gold),
        "title_cursor.png": (cursor(banner), gold),
        "title_sky.png": (sky(), sky_palette()),
        # the character select: 40 x 28 cells, no bar, in 52 tiles (its free VRAM holds 67)
        "select_sky.png": (
            sky(bar=False, banded=True, cloud_bands=2, width=320),
            sky_palette()[:8],
        ),
        # carries a palette only: the duel select's title in gold
        "select_title.png": ([list(range(8))] * 8, title_gold(banner)),
    }
    for name, (px, pal) in files.items():
        save(px, pal, out_dir / name)
    return [out_dir / name for name in files]


def animate(shots: list[Path], out: Path, scale: int = 2, fps: int = 10) -> int:
    """Emulator screenshots -> one looping animated PNG (APNG) at ``scale``; returns its size.

    GitHub shows APNG in a README; Pillow writes only the changed part of each
    frame, so the clouds' drift costs little.
    """
    from PIL import Image

    if not shots:
        raise ValueError("no screenshots to animate (run emu/scenes/banner.txt first)")
    rgb = []
    for path in shots:
        with Image.open(path) as img:
            rgb.append(
                img.convert("RGB").resize((img.width * scale, img.height * scale), Image.NEAREST)
            )
    # One palette for every frame: a later frame is stored as the change from the
    # one before, so per-frame palettes would recolour everything after a cut.
    colours: set = set()
    for img in rgb:
        found = img.getcolors(256)
        if found is None:
            raise ValueError(f"{len(colours)}+ colours in the shots, an indexed PNG holds 256")
        colours.update(c for _n, c in found)
    if len(colours) > 256:
        raise ValueError(f"the shots hold {len(colours)} colours, an indexed PNG 256")
    colours = sorted(colours)
    index = {c: i for i, c in enumerate(colours)}
    palette = [v for c in colours for v in c]
    frames = []
    for img in rgb:
        frame = Image.new("P", img.size)
        frame.putpalette(palette)
        frame.putdata([index[c] for c in img.get_flattened_data()])
        frames.append(frame)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out, save_all=True, append_images=frames[1:], duration=1000 // fps, loop=0, optimize=True
    )
    return out.stat().st_size
