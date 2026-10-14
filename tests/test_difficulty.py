"""The third difficulty «ЖЕСТЬ)» (patch difficulty) and strings carried by a patch."""

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
    assert [t for _o, _l, t in rows] == ["ОБЫЧНО", "ТРУДНО", "ЖЕСТЬ)"]


def test_patch_assembles_names_and_hooks():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, _todo, labels = assembled(segs["names"], proj.paths)
    assert body == b"".join(table.encode(t) for t in ("ОБЫЧНО", "ТРУДНО", "ЖЕСТЬ)"))
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


def test_place_section_assembles_without_hooks():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, todo, labels = assembled(segs["place"], proj.paths)
    assert 0 < len(body) <= segs["place"].size and todo == []
    _body, _todo, spawn = assembled(segs["spawn"], proj.paths)
    assert spawn["frame"] < segs["place"].start <= labels["pop"]  # frame reaches pop with jsr
    sym = segs["place"].get("patch_def")["symbols"]
    for name in ("GAP", "WAIT"):  # beside the queue, in RAM the game never writes
        assert 0xBCC0 <= sym[name] < sym["Q_DATA"]
        assert sym[name] not in (sym["Q_COUNT"], sym["Q_HEAD"], sym["COPYING"])
    end = sym["END_X"]

    def table(label):
        at, out = labels[label] - segs["place"].start, []
        while (v := int.from_bytes(body[at : at + 2], "big", signed=True)) != end:
            out.append(v)
            at += 2
        return out

    right, left = table("RIGHT_X"), table("LEFT_X")
    # every X is past the screen (0..0x140) or at most 8 pixels inside it
    assert all(x >= 0x138 for x in right) and all(x <= 8 for x in left)
    assert right[0] == 0x150 and left[0] == -0x10


@pytest.mark.rom
def test_copies_use_the_games_edges_and_collision_boxes(baserom):
    _proj, segs = _segs()
    sym = segs["place"].get("patch_def")["symbols"]
    rom = bytes(baserom.data)
    assert rom[0x00C11C:0x00C120].hex() == "06450150"  # placement 1: addi.w #$150,d5
    assert rom[0x00C12A:0x00C12E].hex() == "04450010"  # placement 2: subi.w #$10,d5
    lea = 0x002CAC
    assert rom[lea : lea + 2].hex() == "4bf9"
    assert int.from_bytes(rom[lea + 2 : lea + 6], "big") == sym["TERRAIN"]
    assert rom[lea + 6 : lea + 10].hex() == f"3c38{sym['STAGE']:04x}".lower()
    assert rom[0x002EEE:0x002EF2].hex() == f"3146{sym['FLOOR']:04x}"  # move.w d6,$74(a0)

    def word(a):
        return int.from_bytes(rom[a : a + 2], "big")

    def tops(stage, part, x, z):
        a = sym["TERRAIN"]
        a += word(a + 2 * stage)
        a += word(a + 2 * part)
        col = a + word(a + 2 * (x >> 6))
        found, at = [], col
        while True:
            off = word(at)
            at += 2
            box = [word(col + (off & 0x7FFF) + 2 * i) for i in range(7)]
            if abs(x - box[0]) < box[1] and abs(z - box[2]) < box[3] and box[6] == 0:
                found.append(box[4] + box[5])
            if off & 0x8000:
                return found

    # stage 1 (stage 3, part 0): the player stands at 937 on a box whose top is 936
    assert max(tops(3, 0, 0x365, 295)) == 936


@pytest.mark.rom
def test_terrain_column_tables_start_with_their_size(baserom):
    # floor bounds the column with the first offset: lists follow the table
    _proj, segs = _segs()
    terrain = segs["place"].get("patch_def")["symbols"]["TERRAIN"]
    rom = bytes(baserom.data)

    def s16(a):
        return int.from_bytes(rom[a : a + 2], "big", signed=True)

    met = "0/0 1/0 1/1 2/0 3/0 3/1 4/0 5/0 5/1 6/0 6/1 6/2 6/3 6/4 7/0 7/1 7/3 8/0 8/1 9/0 10/0"
    met += " 11/0 12/0 17/0 18/0"  # stage/part pairs the bot met
    seen = [tuple(map(int, pair.split("/"))) for pair in met.split()]
    for stage, part in seen:
        a = terrain + s16(terrain + 2 * stage)
        col = a + s16(a + 2 * part)
        size = s16(col)
        offs = [s16(col + i) for i in range(0, size, 2)]
        assert size > 0 and min(offs) == size and all(o % 2 == 0 for o in offs), (stage, part)
