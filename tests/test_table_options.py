"""Table segments' ``hex`` and ``range`` options (used by stage_music: song IDs 81-9B)."""

from __future__ import annotations

import pytest

from ga3 import balance
from ga3.assets import Paths
from ga3.assets.base import BuildError
from ga3.assets.table_asset import TableHandler
from ga3.rom import Rom
from ga3.rom_map import Segment


def _setup(tmp_path, **attrs):
    seg = Segment(
        "songs", 0x10, 0x13, "table", "data/songs.yml",
        {"format": "u8", "fields": ["a", "b", "c"]} | attrs,
    )  # fmt: skip
    rom = Rom(bytes(0x10) + bytes([0x86, 0x8B, 0x9B]) + bytes(0x0D))
    paths = Paths(tmp_path, tmp_path / "assets", tmp_path / "build")
    TableHandler().extract(rom, seg, paths)
    return seg, rom, paths, paths.asset(seg.path)


def test_hex_values_are_written_as_hex_and_read_back(tmp_path):
    seg, rom, paths, path = _setup(tmp_path, hex=True)
    text = path.read_text(encoding="utf-8")
    assert "  a: 0x86\n  b: 0x8B\n  c: 0x9B\n" in text
    assert balance.read_table(path) == {"a": 0x86, "b": 0x8B, "c": 0x9B}
    assert TableHandler().build(rom, seg, paths) is None  # unchanged


def test_balance_set_keeps_hex(tmp_path):
    seg, rom, paths, path = _setup(tmp_path, hex=True, range=[0x81, 0x9B])
    old, warnings = balance.set_table_field(seg, path, "b", 0x8E)
    assert (old, warnings) == (0x8B, [])
    assert "  b: 0x8E\n" in path.read_text(encoding="utf-8")
    assert TableHandler().build(rom, seg, paths) == "changed"
    assert rom.data[0x11] == 0x8E


def test_range_refuses_values_outside(tmp_path):
    seg, rom, paths, path = _setup(tmp_path, hex=True, range=[0x81, 0x9B])
    with pytest.raises(ValueError, match=r"outside 0x81\.\.0x9B"):
        balance.set_table_field(seg, path, "a", 0x9C)
    path.write_text(path.read_text(encoding="utf-8").replace("a: 0x86", "a: 0x80"), "utf-8")
    with pytest.raises(BuildError, match=r"a=128 is not an integer in 0x81\.\.0x9B"):
        TableHandler().build(rom, seg, paths)


def test_without_options_tables_stay_decimal(tmp_path):
    _seg, _rom, _paths, path = _setup(tmp_path)
    assert "  a: 134\n" in path.read_text(encoding="utf-8")
