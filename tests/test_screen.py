"""Indexed PNG art -> tiles, maps, sprite tiles, palettes (ga3.screen)."""

from __future__ import annotations

import pytest

from ga3 import screen, tiles


def _art(w: int, h: int, pixel) -> screen.Art:
    return screen.Art(w, h, [[pixel(x, y) for x in range(w)] for y in range(h)], [(0, 0, 0)] * 16)


def test_plane_shares_cells_across_images():
    a = _art(16, 8, lambda x, y: 1 if x < 8 else 2)
    b = _art(16, 8, lambda x, y: 2 if x < 8 else 3)
    data, maps = screen.plane([a, b], first_tile=0x10, attr=0x2000)
    assert len(data) == 3 * tiles.TILE_SIZE
    assert maps == [[0x2010, 0x2011], [0x2011, 0x2012]]


def test_plane_keeps_mirrored_cells_apart():
    a = _art(16, 8, lambda x, y: 1 if (x % 8) < 4 else 2)
    b = _art(16, 8, lambda x, y: 2 if (x % 8) < 4 else 1)
    data, _maps = screen.plane([a, b], 0)
    assert len(data) == 2 * tiles.TILE_SIZE  # the scaler cannot flip a cell


def test_sprite_pieces_go_column_by_column():
    art = _art(16, 16, lambda x, y: 1 + x // 8 + 2 * (y // 8))  # cells 1 2 / 3 4
    data = screen.sprite(art, [(0, 0, 2, 2)])
    firsts = [data[i * 32] >> 4 for i in range(4)]
    assert firsts == [1, 3, 2, 4]


def test_sprite_piece_limits():
    art = _art(48, 8, lambda x, y: 1)
    with pytest.raises(ValueError, match="1..4 cells"):
        screen.sprite(art, [(0, 0, 5, 1)])
    with pytest.raises(ValueError, match="leaves"):
        screen.sprite(art, [(4, 0, 4, 1)])


def test_load_checks_mode_size_and_indices(tmp_path):
    from PIL import Image

    Image.new("RGB", (8, 8)).save(tmp_path / "rgb.png")
    with pytest.raises(ValueError, match="paletted"):
        screen.load(tmp_path / "rgb.png")
    Image.new("P", (12, 8)).save(tmp_path / "odd.png")
    with pytest.raises(ValueError, match="8x8 cells"):
        screen.load(tmp_path / "odd.png")
    img = Image.new("P", (8, 8))
    img.putpalette([0, 0, 0] * 17)
    img.putpixel((0, 0), 16)
    img.save(tmp_path / "many.png")
    with pytest.raises(ValueError, match="index 16"):
        screen.load(tmp_path / "many.png")


def test_palette_words_snap_to_the_vdp():
    art = _art(8, 8, lambda x, y: 0)
    art.palette = [(0, 0, 0), (255, 255, 255), (255, 0, 0)]
    assert screen.palette_words(art, 3) == [0x0000, 0x0EEE, 0x000E]
    with pytest.raises(ValueError, match="entries"):
        screen.palette_words(art, 4)
