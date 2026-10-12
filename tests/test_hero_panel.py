"""The hero stats panel of the character select (patch hero_panel)."""

from __future__ import annotations

import struct

import pytest

from ga3 import font, hero_panel

from .conftest import ROOT

DATA = ROOT / "assets" / "data" / "hero_panel.yml"
ART = ROOT / "assets" / "gfx" / "font" / "font.txt"
VRAM_TILE = 0x3C40 // 32

# select cursor -> class id (object +0x131), and the attack records of each
# hero's first combo hit and close finisher with Fwd (docs/heroes.md)
CLASS = [3, 2, 4, 0]
BLOCK = {3: 0x0EEDEC, 2: 0x0EED5E, 4: 0x0EED8C, 0: 0x0EEDBE}
RECORDS = {3: (4, 7), 2: (6, 9), 4: (2, 5), 0: (2, 6)}


@pytest.fixture(scope="module")
def panel():
    doc = hero_panel.load_data(DATA)
    return doc, hero_panel.render(doc, font.parse_art_file(str(ART)), VRAM_TILE, 118)


def test_tiles_and_maps_fit(panel):
    _doc, p = panel
    assert len(p.tiles) % 32 == 0 and len(p.tiles) // 32 <= 118
    assert p.tiles[:32] == b"\xcc" * 32  # tile 0 is plain blue: the VRAM signature
    fw, fh = hero_panel.FULL
    hw, hh = hero_panel.HALF
    assert [len(m) for m in p.full] == [fw * fh] * 4
    assert [len(m) for m in p.half] == [hw * hh] * 4
    count = len(p.tiles) // 32
    for m in p.full + p.half:
        assert m[0] == p.corner  # every panel starts with the same corner
        assert all(w & 0x8000 and VRAM_TILE <= (w & 0x7FF) < VRAM_TILE + count for w in m)
    assert len({tuple(m) for m in p.full}) == 4  # each hero's panel differs


def test_bad_data_is_refused(panel):
    doc, _p = panel
    glyphs = font.parse_art_file(str(ART))
    with pytest.raises(ValueError, match="tiles"):
        hero_panel.render(doc, glyphs, VRAM_TILE, 10)
    long = {**doc, "heroes": [{**doc["heroes"][0], "name": "Х" * 19}, *doc["heroes"][1:]]}
    with pytest.raises(ValueError, match="longer"):
        hero_panel.render(long, glyphs, VRAM_TILE, 118)


@pytest.mark.rom
def test_numbers_match_the_rom_tables(baserom, panel):
    """hp, hit, super and speed come from the game's own tables, not from memory."""
    doc, _p = panel
    rom = bytes(baserom.data)
    hp0 = rom[0x00E492]  # max-HP level 0: every hero starts there
    for cursor, hero in enumerate(doc["heroes"]):
        cls = CLASS[cursor]
        hit_rec, super_rec = RECORDS[cls]
        power = [rom[BLOCK[cls] + 2 + 2 * r + 1] for r in (hit_rec, super_rec)]
        walk = struct.unpack(">H", rom[0x337E6 + 4 * cls : 0x337E8 + 4 * cls])[0]
        assert hero["hp"] == hp0
        assert [hero["hit"], hero["super"]] == power, hero["name"]
        assert hero["speed"] == int(walk * 60 / 256 + 0.5), hero["name"]  # px per second
    assert rom[0x160FA:0x160FE] == bytes(c + 1 for c in CLASS)  # cursor -> class + 1


def test_patch_assembles_and_hooks_the_cursor_routine():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled
    from ga3.pipeline import open_project

    proj = open_project(ROOT)
    seg = next(s for s in proj.map.by_type("patch") if s.get("patch") == "hero_panel")
    body, todo, labels = assembled(seg, proj.paths)
    assert 0 < len(body) <= seg.size
    assert labels["cursor"] == seg.start
    assert [(e.at, e.expect.hex()) for e in todo] == [(0x016278, "31400014c0fc")]
    assert todo[0].new == b"\x4e\xf9" + seg.start.to_bytes(4, "big")  # jmp cursor.l
