"""Segments of type ``palette``: ``.pal`` text read word for word (pal_lines, pal_pool)."""

from __future__ import annotations

import struct

import pytest

from ga3 import palette
from ga3.assets import Paths
from ga3.assets.base import BuildError
from ga3.assets.palette_asset import PaletteHandler
from ga3.rom import Rom
from ga3.rom_map import Segment

WORDS = [(k * 0x0222) & 0x0EEE for k in range(16)]  # sixteen real CRAM colours
PAL = struct.pack(">16H", *WORDS)


def _setup(tmp_path, script=False, **attrs):
    body = b"".join((bytes([0xF0 | line, 0]) if script else b"") + PAL for line in (1, 3))
    seg = Segment(
        "pals", 0x10, 0x10 + len(body), "palette", "palettes/pals.pal",
        ({"script": True} if script else {}) | attrs,
    )  # fmt: skip
    rom = Rom(bytes(0x10) + body + bytes(0x10))
    paths = Paths(tmp_path, tmp_path / "assets", tmp_path / "build")
    PaletteHandler().extract(rom, seg, paths)
    return seg, rom, paths, paths.asset(seg.path)


@pytest.mark.parametrize("script", [False, True])
def test_round_trip_is_exact(tmp_path, script):
    seg, rom, paths, path = _setup(tmp_path, script, labels=["first", "second"])
    text = path.read_text(encoding="utf-8")
    head = "[palette 1 line 3]  ; second" if script else "[palette 1]  ; second"
    assert head in text
    before = bytes(rom.data)
    assert PaletteHandler().build(rom, seg, paths) is None
    assert bytes(rom.data) == before
    assert PaletteHandler().check(rom, seg) == []
    # the captures' reader still understands the file (tiles4bpp's palette: pals/1)
    assert palette.parse_pal(text)[1] == palette.pal_decode(PAL)


def test_a_colour_edited_by_word_or_by_rgb_lands_in_the_rom(tmp_path):
    seg, rom, paths, path = _setup(tmp_path, script=True)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    first = lines.index("[palette 1 line 3]") + 1
    lines[first] = "0x000E"  # colour 0 of palette 1: the word alone
    lines[first + 1] = "#0000FF"  # colour 1: the RGB alone, snapped to the VDP's levels
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert PaletteHandler().build(rom, seg, paths) == "changed"
    at = seg.start + 34 + 2
    assert struct.unpack_from(">2H", rom.data, at) == (0x000E, 0x0E00)
    assert rom.data[seg.start + 34] == 0xF3  # the line stays


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda t: t.replace("#000000  0x0000  ; 0", "#FF0000  0x0000  ; 0", 1), "change both"),
        (lambda t: t.replace("0x0000  ; 0", "0x0001  ; 0", 1), "not a CRAM colour"),
        (lambda t: t.replace("[palette 1 line 3]", "[palette 1]"), "needs 'line L'"),
        (lambda t: t[: t.index("[palette 1")], "has 1 palettes, the slot holds 2"),
        (lambda t: t.replace("[palette 1 line 3]", "[palette 2 line 3]"), "expected 1"),
    ],
)
def test_bad_files_are_refused(tmp_path, edit, message):
    seg, rom, paths, path = _setup(tmp_path, script=True)
    path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(BuildError, match=message):
        PaletteHandler().build(rom, seg, paths)


def test_plain_palettes_take_no_line(tmp_path):
    seg, rom, paths, path = _setup(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("[palette 0]", "[palette 0 line 2]"))
    with pytest.raises(BuildError, match="have no line"):
        PaletteHandler().build(rom, seg, paths)


def test_check_reports_what_is_not_a_palette(tmp_path):
    seg, rom, _paths, _path = _setup(tmp_path, script=True, labels=["only one"])
    rom.data[seg.start] = 0x31  # a script of 4 words, not a whole line
    rom.data[seg.start + 2] = 0x80  # a skip word where a colour should be
    problems = PaletteHandler().check(rom, seg)
    assert any("1 labels for 2 palettes" in p for p in problems)
    assert any("header 3100" in p for p in problems)
    assert any("colours [0] are not CRAM words" in p for p in problems)
    odd = Segment("odd", 0x10, 0x30, "palette", "palettes/odd.pal", {"script": True})
    assert PaletteHandler().check(rom, odd) == [
        "odd [000010-000030] palette: size 32 is not a multiple of 34"
    ]
