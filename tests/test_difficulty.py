"""The third difficulty «ЖЕСТЬ» (patch difficulty) and strings carried by a patch."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ga3 import table, text
from ga3.assets.base import BuildError
from ga3.pipeline import open_project

from .conftest import ROOT

NAMES = ROOT / "assets" / "text" / "difficulty.txt"


def _segs():
    proj = open_project(ROOT)
    segs = {
        s.get("section"): s for s in proj.map.by_type("patch") if s.get("patch") == "difficulty"
    }
    return proj, segs


def test_names_are_three_records_of_six_from_the_slot_start():
    _proj, segs = _segs()
    rows = text.parse_strings_file(str(NAMES))
    start = segs["names"].start
    assert [(off, ln) for off, ln, _t in rows] == [(start + 6 * i, 6) for i in range(3)]
    assert [t for _o, _l, t in rows] == ["ОБЫЧНО", "ТРУДНО", "ЖЕСТЬ"]


def test_patch_assembles_names_and_hooks():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, _todo, labels = assembled(segs["names"], proj.paths)
    assert body == b"".join(table.encode(t.ljust(6)) for t in ("ОБЫЧНО", "ТРУДНО", "ЖЕСТЬ"))
    assert labels["NAMES"] == segs["names"].start
    _body, todo, _labels = assembled(segs["menu"], proj.paths)
    assert [(e.at, e.expect.hex()) for e in todo] == [(0x0152E4, "d338c7260238")]
    body, todo, labels = assembled(segs["spawn"], proj.paths)
    assert 0 < len(body) <= segs["spawn"].size
    hooks = {e.at: e.new for e in todo}
    assert sorted(hooks) == [0x00BDBA, 0x00C1BE, 0x00C1F6, 0x00C1FE, 0x00C650, 0x00C66E, 0x00E552]
    assert hooks[0x00C1FE] == b"\x4e\xf9" + labels["spawned"].to_bytes(4, "big")  # jmp spawned.l


def test_queue_lives_in_ram_the_game_never_writes():
    _proj, segs = _segs()
    sym = segs["spawn"].get("patch_def")["symbols"]
    end = sym["Q_DATA"] + 8 * sym["Q_LEN"]
    assert 0xBCC0 <= sym["Q_COUNT"] < sym["Q_DATA"] and end <= 0xC000  # FFBCC0-FFBFFF
    assert sym["Q_LEN"] & (sym["Q_LEN"] - 1) == 0  # a ring indexed with Q_LEN-1


def test_patch_strings_are_checked(tmp_path):
    from ga3.assets.patch_asset import _string_tables

    proj, segs = _segs()
    paths = replace(proj.paths, assets=tmp_path)
    (tmp_path / "text").mkdir()
    bad = tmp_path / "text" / "difficulty.txt"
    seg = segs["names"]
    bad.write_text(f"{seg.start:06X}:6 | СЛИШКОМ ДЛИННО\n", encoding="utf-8")
    with pytest.raises(BuildError, match="longer than 6"):
        _string_tables(seg, paths)
    bad.write_text(f"{seg.start + 6:06X}:6 | ОБЫЧНО\n", encoding="utf-8")
    with pytest.raises(BuildError, match="should start at"):
        _string_tables(seg, paths)
    bad.write_text(f"{seg.start:06X}:6 | ЛЁД\n", encoding="utf-8")
    src = _string_tables(seg, paths)  # shorter: padded with spaces
    space = table.encode(" ")[0]
    assert src.splitlines()[-1].endswith(", ".join([f"${space:02X}"] * 3))


def test_text_commands_see_the_names():
    from ga3.cli import _text_units

    proj, _segs_ = _segs()
    units = {seg.name: path for seg, path, _s in _text_units(proj)}
    assert units["difficulty_names"] == NAMES
    assert "difficulty_menu" not in units and "difficulty_spawn" not in units
