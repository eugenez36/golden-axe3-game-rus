"""Menus in the banner's style (patch menus): the art, its limits and the patch's edits."""

from __future__ import annotations

from pathlib import Path

import pytest

from ga3 import banner_art, screen, table, text
from ga3.pipeline import open_project

from .conftest import ROOT

SCREENS = ROOT / "assets" / "gfx" / "screens"
BANNER = ROOT / "docs" / "branding" / "banner.svg"


def _segs():
    proj = open_project(ROOT)
    segs = {s.get("section"): s for s in proj.map.by_type("patch") if s.get("patch") == "menus"}
    return proj, segs


def _sym():
    return _segs()[1]["code"].get("patch_def")["symbols"]


def test_banner_letters_follow_the_outline_rule():
    """The 5 x 7 bitmap + ring rule that draws T and H redraws the banner's letters."""
    banner = banner_art.Banner(BANNER.read_text(encoding="utf-8"))
    black, gold = banner.shape(0)
    drawn = {(x + dx * 8, y + dy * 8) for x, y, _w, _h in gold for dx, dy in banner_art.RING}
    have = {(x, y) for x, y, _w, _h in black}
    assert have <= drawn and len(drawn - have) == 23
    assert len(banner_art._letters(black, gold)) == len(banner_art.LETTERS)


def test_generator_is_deterministic(tmp_path):
    a = banner_art.generate(BANNER, tmp_path / "a")
    b = banner_art.generate(BANNER, tmp_path / "b")
    for x, y in zip(a, b, strict=True):
        ax, by = screen.load(x), screen.load(y)
        assert (ax.pixels, ax.palette) == (by.pixels, by.palette)


def test_committed_art_fits_the_game():
    logo = screen.load(SCREENS / "title_logo.png")
    th = screen.load(SCREENS / "ending_th.png")
    assert (logo.cols, logo.rows) == (38, 6)  # the logo map every consumer copies
    assert (th.cols, th.rows) == (8, 6)  # the ending's TH, 8 x 6 at 01741E
    tiles, _maps = screen.plane([logo, th], 0)
    assert len(tiles) // 32 <= 120  # the intro's 2x scaler takes 120 tiles
    sky = screen.load(SCREENS / "title_sky.png")
    assert (sky.cols, sky.rows) == (32, 28)
    select = screen.load(SCREENS / "select_sky.png")
    assert (select.cols, select.rows) == (40, 28)
    tiles, _maps = screen.plane([select], 0)
    assert len(tiles) // 32 <= 67  # VRAM 9DE0-A640
    assert max(max(r) for r in select.pixels) < 8  # palette 3 keeps 8-11 for the 1P/2P markers
    iii = screen.load(SCREENS / "title_iii.png")
    assert (iii.cols, iii.rows) == (10, 6)


def test_bar_text_fits_and_cells_are_row_26():
    sym = _sym()
    _proj, segs = _segs()
    rows = text.parse_strings_file(str(ROOT / "assets" / "text" / "menus.txt"))
    assert [(off, ln) for off, ln, _t in rows] == [
        (segs["text"].start, sym["LEFT_WIDTH"]),
        (segs["text"].start + sym["LEFT_WIDTH"], sym["RIGHT_WIDTH"]),
    ]
    for _off, ln, txt in rows:
        assert len(table.encode(txt)) <= ln
    row = 0xC000 + 26 * 0x80
    assert sym["BAR_LEFT"] == row + 1 * 2
    assert sym["BAR_MIDDLE"] == row + 14 * 2
    assert sym["BAR_RIGHT"] == row + 27 * 2
    assert 27 + sym["RIGHT_WIDTH"] <= 40
    menu = text.parse_strings_file(str(ROOT / "assets" / "text" / "menu.txt"))
    [blink] = [t for off, _ln, t in menu if off == 0x014EDA]
    assert len(table.encode(blink.rstrip())) <= sym["MIDDLE_WIDTH"]


def test_patch_assembles_with_hooks_and_pointers():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, todo, labels = assembled(segs["code"], proj.paths)
    assert 0 < len(body) <= segs["code"].size
    edits = {e.at: e.new for e in todo}
    assert edits[0x0155BC] == b"\x4e\xf9" + labels["drift"].to_bytes(4, "big")
    assert edits[0x0158B8] == labels["LOGO_TILES"].to_bytes(4, "big")
    assert edits[0x0158BC] == _sym()["SKY_TILE"].to_bytes(2, "big")
    assert edits[0x014D4A] == b"\x4e\x71"  # the sky is no longer halved
    art, _todo, _labels = assembled(segs["art"], proj.paths)
    assert len(art) <= segs["art"].size
    for name in ("LOGO_MAP", "TH_MAP", "SKY_MAP", "SELECT_MAP", "LOGO_PAL", "SKY_PAL"):
        assert labels[name] % 2 == 0, name  # Enigma and palette copies read words


def test_iii_mapping_covers_its_tiles():
    """The III sprite's six pieces use the 60 tiles of III_TILES in order."""
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, _todo, labels = assembled(segs["code"], proj.paths)
    at = labels["III_SPRITE"] - segs["code"].start
    pieces = body[at] + 1
    tile = 0
    for k in range(pieces):
        size = body[at + 2 + 8 * k + 1]
        first = int.from_bytes(body[at + 2 + 8 * k + 2 : at + 2 + 8 * k + 4], "big")
        assert first == tile
        tile += ((size >> 2) + 1) * ((size & 3) + 1)
    iii = screen.load(SCREENS / "title_iii.png")
    assert tile == iii.cols * iii.rows


def test_pointer_values():
    from ga3.assets.base import BuildError
    from ga3.assets.patch_asset import _value

    assert _value("A+2", {"A": 0x10}, "x") == 0x12
    assert _value("SKY-1", {"SKY": 10}, "x") == 9
    assert _value("0x6000+B", {"B": 1}, "x") == 0x6001
    with pytest.raises(BuildError, match="unknown name"):
        _value("NOPE", {}, "x")


def test_screens_are_listed_as_sources():
    proj, segs = _segs()
    from ga3.assets import handler_for

    files = {Path(p).name for p in handler_for(segs["art"]).sources(segs["art"], proj.paths)}
    assert {
        "title_logo.png",
        "ending_th.png",
        "title_sky.png",
        "select_sky.png",
    } <= files


def test_animation_decodes_to_the_shots_across_a_cut(tmp_path):
    """Every APNG frame equals its shot, also after a scene cut that changes the colours."""
    from PIL import Image, ImageSequence

    shots = []
    for k, colour in enumerate([(0, 0, 52)] * 3 + [(0, 0, 0)] + [(206, 172, 0)] * 2):
        img = Image.new("RGB", (16, 8), colour)
        img.putpixel((k, 0), (255, 255, 255))
        shots.append(tmp_path / f"f{k:03d}.png")
        img.save(shots[-1])
    out = tmp_path / "anim.png"
    banner_art.animate(shots, out, scale=2, fps=10)
    want = [Image.open(p).convert("RGB").resize((32, 16), Image.NEAREST).tobytes() for p in shots]
    got = []
    for frame in ImageSequence.Iterator(Image.open(out)):
        got += [frame.convert("RGB").tobytes()] * round(frame.info["duration"] / 100)
    assert got == want


def test_cursor_art_is_two_tiles_the_second_blank():
    """The game uploads 32 words from the cursor's address: tile 10 and tile 11."""
    art = screen.load(SCREENS / "title_cursor.png")
    assert (art.cols, art.rows) == (2, 1)
    assert any(any(r[:8]) for r in art.pixels)
    assert not any(any(r[8:]) for r in art.pixels)
