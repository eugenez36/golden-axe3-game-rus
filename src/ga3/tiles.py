"""4bpp planar tiles: decode, encode, render to PNG, import from PNG.

A Mega Drive tile is 8x8 pixels at 4 bits per pixel = 32 bytes. Within a byte
the high nibble is the left pixel. Pillow is imported lazily so the codec
modules stay usable without it.
"""

from __future__ import annotations

TILE_SIZE = 32
TILE_W = TILE_H = 8

# Placeholder palette for viewing tiles whose real palette is unknown:
# index 0 black, then a linear grey ramp.
GRAY16 = [(0, 0, 0)] + [(i * 17, i * 17, i * 17) for i in range(1, 16)]

Palette = list[tuple[int, int, int]]


def tile_decode(data: bytes, off: int = 0) -> list[list[int]]:
    """32 bytes -> 8x8 palette indices. High nibble = left pixel."""
    rows = []
    for y in range(TILE_H):
        row = []
        for x in range(4):
            b = data[off + y * 4 + x]
            row.append(b >> 4)
            row.append(b & 0x0F)
        rows.append(row)
    return rows


def tile_encode(rows: list[list[int]]) -> bytes:
    """8x8 palette indices -> 32 bytes."""
    if len(rows) != TILE_H or any(len(r) != TILE_W for r in rows):
        raise ValueError("tile_encode(): expected an 8x8 array")
    out = bytearray(TILE_SIZE)
    for y in range(TILE_H):
        for x in range(4):
            hi, lo = rows[y][x * 2] & 0x0F, rows[y][x * 2 + 1] & 0x0F
            out[y * 4 + x] = (hi << 4) | lo
    return bytes(out)


def _require_pil():
    try:
        from PIL import Image

        return Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required: pip install pillow") from exc


def render_tiles(
    data: bytes,
    off: int,
    count: int,
    palette: Palette | None = None,
    cols: int = 16,
    scale: int = 3,
    grid: bool = False,
):
    """Render ``count`` tiles starting at ``off`` into an RGB ``PIL.Image``."""
    Image = _require_pil()
    palette = palette or GRAY16
    rows_n = (count + cols - 1) // cols
    img = Image.new("RGB", (cols * TILE_W, rows_n * TILE_H), palette[0])
    px = img.load()
    for i in range(count):
        t = off + i * TILE_SIZE
        if t + TILE_SIZE > len(data):
            break
        tx, ty = (i % cols) * TILE_W, (i // cols) * TILE_H
        for y, row in enumerate(tile_decode(data, t)):
            for x, idx in enumerate(row):
                px[tx + x, ty + y] = palette[idx]
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    if grid:
        from PIL import ImageDraw

        dr = ImageDraw.Draw(img)
        for c in range(cols + 1):
            dr.line([(c * TILE_W * scale, 0), (c * TILE_W * scale, img.height)], fill=(255, 0, 0))
        for r in range(rows_n + 1):
            dr.line([(0, r * TILE_H * scale), (img.width, r * TILE_H * scale)], fill=(255, 0, 0))
    return img


def dump_tiles(data: bytes, off: int, count: int, path: str, **kw) -> str:
    render_tiles(data, off, count, **kw).save(path)
    return path


def import_tiles(path: str, palette: Palette | None = None) -> bytes:
    """RGB PNG -> tile bytes. Colours snap to the nearest palette entry."""
    Image = _require_pil()
    palette = palette or GRAY16
    img = Image.open(path).convert("RGB")
    if img.width % TILE_W or img.height % TILE_H:
        raise ValueError(f"PNG size {img.width}x{img.height} is not a multiple of 8")
    px = img.load()
    cols, rows_n = img.width // TILE_W, img.height // TILE_H

    def nearest(c):
        return min(
            range(len(palette)),
            key=lambda i: sum((a - b) ** 2 for a, b in zip(palette[i], c, strict=True)),
        )

    cache: dict = {}
    out = bytearray()
    for ty in range(rows_n):
        for tx in range(cols):
            tile = []
            for y in range(TILE_H):
                row = []
                for x in range(TILE_W):
                    c = px[tx * TILE_W + x, ty * TILE_H + y]
                    if c not in cache:
                        cache[c] = nearest(c)
                    row.append(cache[c])
                tile.append(row)
            out += tile_encode(tile)
    return bytes(out)


# -- indexed PNG sheets (lossless round trip) ----------------------------------


def render_indexed(data: bytes, off: int, count: int, cols: int, palette: Palette | None = None):
    """Render tiles into a palette-mode (``P``) image with exactly 16 entries.

    Unlike ``render_tiles`` this keeps the raw indices, so ``import_indexed``
    gets the original nibbles back regardless of the display palette.
    """
    Image = _require_pil()
    palette = palette or GRAY16
    rows_n = (count + cols - 1) // cols
    img = Image.new("P", (cols * TILE_W, rows_n * TILE_H), 0)
    flat = []
    for c in palette[:16]:
        flat.extend(c)
    flat.extend([0] * (768 - len(flat)))
    img.putpalette(flat)
    px = img.load()
    for i in range(count):
        t = off + i * TILE_SIZE
        if t + TILE_SIZE > len(data):
            break
        tx, ty = (i % cols) * TILE_W, (i // cols) * TILE_H
        for y, row in enumerate(tile_decode(data, t)):
            for x, idx in enumerate(row):
                px[tx + x, ty + y] = idx
    return img


def import_indexed(path: str, count: int | None = None) -> bytes:
    """Palette-mode PNG -> tile bytes, reading indices directly.

    RGB images are rejected: an editor that flattens the palette has already
    destroyed the information we need.
    """
    Image = _require_pil()
    img = Image.open(path)
    if img.mode != "P":
        raise ValueError(f"{path}: expected an indexed (mode P) PNG, got mode {img.mode}")
    if img.width % TILE_W or img.height % TILE_H:
        raise ValueError(f"{path}: size {img.width}x{img.height} is not a multiple of 8")
    px = img.load()
    cols, rows_n = img.width // TILE_W, img.height // TILE_H
    total = cols * rows_n if count is None else count
    out = bytearray()
    for i in range(total):
        tx, ty = (i % cols) * TILE_W, (i // cols) * TILE_H
        rows = []
        for y in range(TILE_H):
            row = []
            for x in range(TILE_W):
                v = px[tx + x, ty + y]
                if v > 15:
                    raise ValueError(f"{path}: palette index {v} at ({tx + x},{ty + y}) exceeds 15")
                row.append(v)
            rows.append(row)
        out += tile_encode(rows)
    return bytes(out)


def render_ascii(data: bytes, off: int, count: int, cols: int = 16) -> str:
    """Tiles as ASCII art, for a quick look in the terminal without files."""
    shades = " .:-=+*#%@ABCDEF"
    lines = []
    for r in range((count + cols - 1) // cols):
        band = [""] * TILE_H
        for c in range(cols):
            i = r * cols + c
            if i >= count:
                break
            t = off + i * TILE_SIZE
            if t + TILE_SIZE > len(data):
                break
            for y, row in enumerate(tile_decode(data, t)):
                band[y] += "".join(shades[v] for v in row) + "|"
        lines += band + ["." * (cols * (TILE_W + 1))]
    return "\n".join(lines)
