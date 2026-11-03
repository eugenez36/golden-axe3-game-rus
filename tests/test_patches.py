"""Generated 68000 routines (``ga3.patches``) and the ``patch`` segment handler. No ROM needed."""

import pytest

from ga3 import __version__, patches, table, text
from ga3.assets import BuildError, Paths, handler_for
from ga3.rom import Rom
from ga3.rom_map import Segment

VRAM_END = 0xCD4C
ATTR = 0xE000
RETURN_TO = 0x015010


def _game_vdp_helper(addr: int) -> int:
    """The game's own conversion at 01202E: andi.l #$ffff; lsl.l #2; lsr.w #2; bset #14; swap."""
    d0 = addr & 0xFFFF
    d0 = (d0 << 2) & 0xFFFFFFFF
    d0 = (d0 & 0xFFFF0000) | ((d0 & 0xFFFF) >> 2)
    d0 |= 1 << 14
    return ((d0 << 16) | (d0 >> 16)) & 0xFFFFFFFF


@pytest.mark.parametrize("addr", [0x0000, 0x4000, 0xC8A0, 0xC996, 0xCD3E, 0xFFFE])
def test_vdp_write_vram_matches_the_game(addr):
    assert patches.vdp_write_vram(addr) == _game_vdp_helper(addr)


def test_vdp_write_vram_rejects_odd_addresses():
    with pytest.raises(ValueError):
        patches.vdp_write_vram(0xCD3F)


def test_version_text_uses_the_package_version_and_the_font():
    assert patches.version_text() == f"V {__version__}"
    assert table.encode("V 0.3.6") == bytes([0x40, 0x20, 0x30, 0x2E, 0x33, 0x2E, 0x36])


def test_menu_version_disassembles_to_the_intended_routine():
    pytest.importorskip("capstone")
    from ga3 import disasm

    origin = 0x0116B6
    body = patches.menu_version(VRAM_END, ATTR, RETURN_TO, "V 0.3.6")
    glyphs = table.encode("V 0.3.6")
    assert body.endswith(glyphs)
    code_end = origin + len(body) - len(glyphs)
    rows = disasm.disasm(bytes(origin) + body, origin, end=code_end)
    loop = origin + 16
    assert [(mn, ops) for _a, _b, mn, ops in rows] == [
        ("move.l", "#$4d3e0003, (a6)"),  # VRAM write at CD3E = CD4C - 2 * 7
        ("lea.l", f"${code_end:x}(pc), a0"),
        ("move.w", "#$e000, d1"),
        ("moveq", "#$6, d7"),
        ("move.w", "d1, d2"),
        ("add.b", "(a0)+, d2"),
        ("move.w", "d2, -$4(a6)"),
        ("dbra", f"d7, ${loop:x}"),
        ("moveq", "#$0, d1"),
        ("jmp", "$15010.l"),
    ]


def test_menu_version_refuses_characters_the_font_lacks():
    with pytest.raises(ValueError, match="not in the game font"):
        patches.menu_version(VRAM_END, ATTR, RETURN_TO, "V 0.3.6~rc1")  # no '~' glyph


# ---------------------------------------------------------------- handler

HOOK = 0x100
HOOK_BYTES = bytes.fromhex("72 00 60 00 00 86")


def _segment(start: int = 0x200, end: int = 0x240, **over) -> Segment:
    attrs = {
        "routine": "menu_version",
        "hook": HOOK,
        "hook_bytes": HOOK_BYTES.hex(" "),
        "return_to": RETURN_TO,
        "vram_end": VRAM_END,
        "attr": ATTR,
        "fill": 0xFF,
    } | over
    return Segment("menu_version", start, end, "patch", None, attrs)


def _image() -> Rom:
    data = bytearray(0x400)
    data[HOOK : HOOK + 6] = HOOK_BYTES
    data[0x200:0x240] = b"\xff" * 0x40
    return Rom(bytes(data))


def _paths(tmp_path) -> Paths:
    return Paths(tmp_path, tmp_path / "assets", tmp_path / "build")


def test_handler_places_body_and_hook(tmp_path):
    seg, rom = _segment(), _image()
    handler = handler_for(seg)
    assert handler.check(rom, seg) == []
    assert "edits at 000100" in handler.build(rom, seg, _paths(tmp_path))
    body = patches.menu_version(VRAM_END, ATTR, RETURN_TO, patches.version_text())
    assert rom.data[HOOK : HOOK + 6] == patches.jmp_abs(0x200)
    assert rom.data[0x200 : 0x200 + len(body)] == body
    assert set(rom.data[0x200 + len(body) : 0x240]) == {0xFF}
    assert handler.sources(seg, _paths(tmp_path)) == []


def test_handler_refuses_a_hook_that_is_not_the_expected_code(tmp_path):
    seg, rom = _segment(), _image()
    rom.data[HOOK] = 0x4E
    with pytest.raises(BuildError, match="0x000100 holds"):
        handler_for(seg).build(rom, seg, _paths(tmp_path))
    assert any("0x000100 holds" in p for p in handler_for(seg).check(rom, seg))


def test_check_reports_a_slot_that_is_not_free():
    seg, rom = _segment(), _image()
    rom.data[0x220] = 0x00
    assert any("not free space" in p for p in handler_for(seg).check(rom, seg))


@pytest.mark.parametrize(
    "over, match",
    [
        ({"routine": "nope"}, "unknown routine"),
        ({"hook_bytes": "72 00"}, "must be 6 bytes"),
        ({"hook": 0x1FE}, "overlaps"),
        ({"vram_end": None}, "menu_version"),
    ],
)
def test_handler_rejects_bad_map_entries(tmp_path, over, match):
    seg, rom = _segment(**over), _image()
    with pytest.raises(BuildError, match=match):
        handler_for(seg).build(rom, seg, _paths(tmp_path))


def test_handler_refuses_a_routine_larger_than_its_slot(tmp_path):
    seg = _segment(end=0x210)
    with pytest.raises(BuildError, match="overflow"):
        handler_for(seg).build(_image(), seg, _paths(tmp_path))


# ---------------------------------------------------------------- menu_items

ITEMS_LEA, HEADER_LEA, WIDTH_IMM = 0x10A, 0x112, 0x119
OLD_ITEMS, OLD_HEADER = 0x130, 0x150


def _items_segment(**over) -> Segment:
    attrs = {
        "routine": "menu_items",
        "strings_path": "text/menu_items.txt",
        "item_width": 8,
        "items": 4,
        "items_lea": ITEMS_LEA,
        "items_was": OLD_ITEMS,
        "header_lea": HEADER_LEA,
        "header_was": OLD_HEADER,
        "header_item": 1,
        "width_imm": WIDTH_IMM,
        "width_was": 7,
        "fill": 0xFF,
    } | over
    return Segment("menu_items", 0x200, 0x220, "patch", None, attrs)


def _items_image() -> Rom:
    data = bytearray(0x400)
    data[0x108:0x10C] = bytes.fromhex("41FA") + (OLD_ITEMS - ITEMS_LEA).to_bytes(2, "big")
    data[0x110:0x114] = bytes.fromhex("41FA") + (OLD_HEADER - HEADER_LEA).to_bytes(2, "big")
    data[0x118:0x11A] = bytes.fromhex("7E06")  # moveq #6,d7: seven characters
    data[0x200:0x220] = b"\xff" * 0x20
    return Rom(bytes(data))


def _write_items(tmp_path, names) -> None:
    path = tmp_path / "assets" / "text" / "menu_items.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [(0x200 + 8 * i, 8, n) for i, n in enumerate(names)]
    path.write_text(text.format_strings_file(rows, "menu_items", 0x200, 0x220), encoding="utf-8")


ITEM_NAMES = ["1 ИГРОК", "2 ИГРОКА", "ДУЭЛЬ", "ОПЦИИ"]


def test_menu_items_places_the_table_and_retargets_the_code(tmp_path):
    seg, rom = _items_segment(), _items_image()
    _write_items(tmp_path, ITEM_NAMES)
    h = handler_for(seg)
    assert h.check(rom, seg) == []
    assert h.sources(seg, _paths(tmp_path)) == [tmp_path / "assets/text/menu_items.txt"]
    h.build(rom, seg, _paths(tmp_path))
    assert bytes(rom.data[0x200:0x220]) == b"".join(table.encode(n).ljust(8) for n in ITEM_NAMES)
    lea = int.from_bytes(rom.data[ITEMS_LEA : ITEMS_LEA + 2], "big", signed=True)
    assert ITEMS_LEA + lea == 0x200
    lea = int.from_bytes(rom.data[HEADER_LEA : HEADER_LEA + 2], "big", signed=True)
    assert HEADER_LEA + lea == 0x208  # item 2, redrawn grey without a second pad
    assert bytes(rom.data[0x118:0x11A]) == bytes.fromhex("7E07")


def test_menu_items_refuses_a_bad_strings_file(tmp_path):
    seg = _items_segment()
    _write_items(tmp_path, ITEM_NAMES[:3])
    with pytest.raises(BuildError, match="must hold exactly the records"):
        handler_for(seg).build(_items_image(), seg, _paths(tmp_path))
    _write_items(tmp_path, ["1 ИГРОК", "ДЛИННОЕ ИМЯ", "ДУЭЛЬ", "ОПЦИИ"])
    with pytest.raises(BuildError, match="longer than 8"):
        handler_for(seg).build(_items_image(), seg, _paths(tmp_path))


def test_menu_items_refuses_code_that_drifted(tmp_path):
    seg, rom = _items_segment(), _items_image()
    _write_items(tmp_path, ITEM_NAMES)
    rom.data[0x119] = 0x05
    assert any("0x000118 holds" in p for p in handler_for(seg).check(rom, seg))
    with pytest.raises(BuildError, match="0x000118 holds 7e 05, expected 7e 06"):
        handler_for(seg).build(rom, seg, _paths(tmp_path))
    far = _items_segment(items_was=0x9000)
    with pytest.raises(BuildError, match="cannot reach"):
        handler_for(far).build(_items_image(), far, _paths(tmp_path))


# ---------------------------------------------------------------- assembled patches (kill counter)


def _real_project():
    from ga3.pipeline import open_project

    from .conftest import ROOT

    return open_project(ROOT)


def test_kill_counter_assembles_into_its_four_slots():
    from ga3.assets.patch_asset import assembled

    proj = _real_project()
    segs = {
        s.get("section"): s for s in proj.map.by_type("patch") if s.get("patch") == "kill_counter"
    }
    assert set(segs) == {"count", "bonus", "hud", "tiles"}
    labels = None
    for section, seg in segs.items():
        body, todo, labels = assembled(seg, proj.paths)
        assert 0 < len(body) <= seg.size, f"{section}: {len(body)} B in a {seg.size} B slot"
        for e in todo:  # every hook is a jmp into this patch
            assert e.new[:2] == b"\x4e\xf9"
            target = int.from_bytes(e.new[2:], "big")
            assert any(s.start <= target < s.end for s in segs.values())
    assert labels["melee_a0"] == segs["count"].start
    assert labels["frame"] == segs["hud"].start
    assert labels["tiles"] == segs["tiles"].start
    assert labels["kill"] == segs["bonus"].start


def test_kill_counter_digits_live_where_no_sprite_art_goes():
    proj = _real_project()
    seg = next(s for s in proj.map.by_type("patch") if s.get("patch") == "kill_counter")
    sym = seg.get("patch_def")["symbols"]
    first = sym["DIGITS_VRAM"] // 32
    assert sym["DIGITS_VRAM"] % 32 == 0 and sym["COUNTER_ATTR"] & 0x07FF == first
    # six tiles in DF00-DFFF: the game DMAs objects' frames into D700-DEFF
    assert sym["DIGITS_VRAM"] >= 0xDF00 and sym["DIGITS_VRAM"] + 6 * 32 <= 0xE000
    taken = range(sym["KILLS"], sym["SHOWN"] + 4)  # both counters and both SHOWN words
    assert 0xC000 <= sym["TICK"] < 0xC766 and sym["TICK"] not in taken


def test_kill_counter_glyphs_come_from_the_font_art():
    from ga3 import font as fontlib
    from ga3.assets.patch_asset import _glyph_tables

    proj = _real_project()
    seg = next(s for s in proj.map.by_type("patch") if s.get("section") == "tiles")
    src, derived = _glyph_tables(seg, proj.paths)
    assert derived == {"BLANK_GLYPH": 10}
    rows = [
        int(b.strip("$"), 16)
        for line in src.splitlines()
        if "dc.b" in line
        for b in line.split("dc.b")[1].replace(" ", "").split(",")
    ]
    assert len(rows) == 11 * 8
    art = fontlib.parse_art_file(str(proj.paths.asset("gfx/font/font.txt")))
    one = art[table.encode("1")[0]]
    for y in range(8):
        row = "".join(
            "#" if (one[y * 4 + x // 2] >> (4 if x % 2 == 0 else 0) & 0xF) == 6 else "."
            for x in range(8)
        )
        assert row == f"{rows[8 + y]:08b}".replace("1", "#").replace("0", ".")
    assert rows[10 * 8 : 11 * 8] == [0] * 8  # the blank glyph


def test_verify_built_catches_a_later_overwrite(tmp_path):
    seg, rom = _segment(), _image()
    h = handler_for(seg)
    h.build(rom, seg, _paths(tmp_path))
    assert h.verify_built(rom, seg) == []
    rom.data[HOOK + 2] ^= 0xFF  # a later segment writes over the hook
    assert any("overwrote the edit at 0x000100" in p for p in h.verify_built(rom, seg))
    rom.data[0x201] ^= 0xFF
    assert any("overwrote the patch's slot" in p for p in h.verify_built(rom, seg))


def test_map_attaches_patch_definitions_and_rejects_bad_ones():
    from ga3 import rom_map

    def doc(segments, patches):
        return {"rom": {"size": 0x1000}, "patches": patches, "segments": segments}

    seg = lambda name, start, section: {  # noqa: E731
        "name": name,
        "start": start,
        "size": 0x10,
        "type": "patch",
        "patch": "p",
        "section": section,
    }
    m = rom_map.parse(doc([seg("a", 0x100, "x"), seg("b", 0x200, "y")], {"p": {"source": "s.s"}}))
    a = m.by_name("a")
    assert a.get("patch_def") == {"source": "s.s"} and a.get("sections") == {"x": 0x100, "y": 0x200}
    with pytest.raises(rom_map.RomMapError, match="not defined under patches"):
        rom_map.parse(doc([seg("a", 0x100, "x")], {}))
    with pytest.raises(rom_map.RomMapError, match="given twice"):
        rom_map.parse(doc([seg("a", 0x100, "x"), seg("b", 0x200, "x")], {"p": {}}))
    bad = seg("a", 0x100, "x")
    del bad["section"]
    with pytest.raises(rom_map.RomMapError, match="needs section"):
        rom_map.parse(doc([bad], {"p": {}}))


def test_kill_counter_keeps_the_games_death_test_for_any_damage():
    """After sub.b on the victim's HP every hook branches with bhi (unsigned).

    The game clears HP when sub.b leaves bit 7 set (bpl). bgt would read an
    overflow -- HP 75, damage 128 (power 0xFF plus the carried half) -- as a
    living hero with HP 203; bhi matches bpl for every HP the game allows.
    """
    pytest.importorskip("capstone")
    from ga3 import disasm
    from ga3.assets.patch_asset import assembled

    proj = _real_project()
    seg = next(
        s
        for s in proj.map.by_type("patch")
        if s.get("patch") == "kill_counter" and s.get("section") == "count"
    )
    body, _todo, _labels = assembled(seg, proj.paths)
    rows = disasm.disasm(bytes(seg.start) + body, seg.start, end=seg.start + len(body))
    subs = [i for i, r in enumerate(rows) if r[2] == "sub.b" and r[3].endswith("$142(a0)")]
    assert len(subs) == 3  # melee a0, melee a1, magic
    assert all(rows[i + 1][2] in ("bhi.b", "bhi.s") for i in subs)
