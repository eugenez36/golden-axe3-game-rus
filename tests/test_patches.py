"""Generated 68000 routines (``ga3.patches``) and the ``patch`` segment handler. No ROM needed."""

import pytest

from ga3 import __version__, patches, table
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
    assert "hook at 000100" in handler.build(rom, seg, _paths(tmp_path))
    body = patches.menu_version(VRAM_END, ATTR, RETURN_TO, patches.version_text())
    assert rom.data[HOOK : HOOK + 6] == patches.jmp_abs(0x200)
    assert rom.data[0x200 : 0x200 + len(body)] == body
    assert set(rom.data[0x200 + len(body) : 0x240]) == {0xFF}
    assert handler.sources(seg, _paths(tmp_path)) == []


def test_handler_refuses_a_hook_that_is_not_the_expected_code(tmp_path):
    seg, rom = _segment(), _image()
    rom.data[HOOK] = 0x4E
    with pytest.raises(BuildError, match="hook 0x000100 holds"):
        handler_for(seg).build(rom, seg, _paths(tmp_path))
    assert any("hook" in p for p in handler_for(seg).check(rom, seg))


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
