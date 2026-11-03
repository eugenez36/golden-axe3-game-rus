"""The options items БАНКИ МАГИИ (starting magic potions) and 100 ВРАГОВ (patch options)."""

from __future__ import annotations

import pytest

from ga3 import table, text
from ga3.pipeline import open_project

from .conftest import ROOT

LABELS = ROOT / "assets" / "text" / "options.txt"
MENU = ROOT / "assets" / "text" / "menu.txt"


def _segs():
    proj = open_project(ROOT)
    segs = {s.get("section"): s for s in proj.map.by_type("patch") if s.get("patch") == "options"}
    return proj, segs


def _sym():
    return _segs()[1]["menu"].get("patch_def")["symbols"]


def test_labels_and_values_follow_each_other_from_the_slot_start():
    _proj, segs = _segs()
    rows = text.parse_strings_file(str(LABELS))
    sym = _sym()
    width, value = sym["LABEL_WIDTH"], sym["VALUE_WIDTH"]
    at = segs["labels"].start
    assert [(off, ln) for off, ln, _t in rows] == [
        (at, width),
        (at + width, width),
        (at + 2 * width, value),
        (at + 2 * width + value, value),
    ]
    assert [t for _o, _l, t in rows] == ["БАНКИ МАГИИ", "100 ВРАГОВ", "ВЫКЛ", "ВКЛ"]


def test_patch_assembles_label_and_hooks():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, _todo, labels = assembled(segs["labels"], proj.paths)
    assert body == b"".join(
        table.encode(t.ljust(n))
        for t, n in [("БАНКИ МАГИИ", 11), ("100 ВРАГОВ", 11), ("ВЫКЛ", 4), ("ВКЛ", 4)]
    )
    assert labels["LABELS"] == segs["labels"].start
    body, todo, labels = assembled(segs["menu"], proj.paths)
    assert 0 < len(body) <= segs["menu"].size
    edits = {e.at: e.new for e in todo}
    assert sorted(edits) == [0x00E476, 0x0150FE, 0x01525A, 0x0152C8, 0x0153D6, 0x015422, 0x01543C]
    assert edits[0x00E476] == b"\x4e\xf9" + labels["refill"].to_bytes(4, "big")  # jmp refill.l
    sym = _sym()
    assert edits[0x0153D6] == sym["MUS_CELL"].to_bytes(2, "big")  # move.w #$c830,d0 -> МУЗ. row 0F
    assert edits[0x015422] == sym["SND_CELL"].to_bytes(2, "big")  # move.w #$c9b0,d0 -> ЗВУК row 11


def _cell(row: int, col: int) -> int:
    return 0xC000 + row * 0x80 + col * 2


def test_items_below_buttons_are_two_rows_apart():
    sym = _sym()
    [layout] = [t for off, _ln, t in text.parse_strings_file(str(MENU)) if off == 0x01512C]
    assert "{08}{0F}МУЗ." in layout and "{08}{11}ЗВУК" in layout and "{08}{18}МЕНЮ" in layout
    assert sym["MUS_CELL"] == _cell(0x0F, 0x18)
    assert sym["SND_CELL"] == _cell(0x11, 0x18)
    assert (sym["POT_LABEL"], sym["POT_CELL"]) == (_cell(0x13, 8), _cell(0x13, 0x18))
    assert (sym["LIFE_LABEL"], sym["LIFE_CELL"]) == (_cell(0x15, 8), _cell(0x15, 0x18))
    assert (sym["ITEMS"], sym["POT_ITEM"], sym["LIFE_ITEM"], sym["MENU_ITEM"]) == (7, 4, 5, 6)
    src = (ROOT / "assets" / "patches" / "options.s").read_text(encoding="utf-8")
    assert ".rows:  dc.b    $08, $0B, $0F, $11, $13, $15, $18" in src


def test_default_is_the_potions_constant_and_the_hud_limit():
    proj, _segs_ = _segs()
    sym = _sym()
    potions = proj.map.constants["potions"]
    [site] = potions.sites
    assert sym["DEFAULT"] == site.at + site.offset  # the operand of the bypassed move
    assert sym["REFILL_BACK"] == site.at + len(site.expect)
    assert sym["POT_MAX"] == potions.get("max") == 6


def test_settings_live_in_the_byte_kept_over_a_soft_reset():
    sym = _sym()
    assert sym["POT"] == 0xC729  # 0002CC/0002E8 keep the long at $C726 (difficulty, buttons)
    assert sym["POT_MASK"] == (1 << sym["LIFE_BIT"]) - 1 >= sym["POT_MAX"]
    assert sym["LIFE_FLAG"] == 1 << sym["LIFE_BIT"]


def test_kill_counter_reads_the_same_bit():
    proj, _segs_ = _segs()
    [kc_seg] = [s for s in proj.map.by_type("patch") if s.get("patch") == "kill_counter"][:1]
    opt, kc = _sym(), kc_seg.get("patch_def")["symbols"]
    assert (kc["POT"], kc["LIFE_BIT"], kc["DEMO"]) == (opt["POT"], opt["LIFE_BIT"], opt["DEMO"])
    assert kc["LIVES_MAX"] == proj.map.constants["lives"].get("max_hud") == 9
    assert kc["LIFE_KILLS"] == 100


def test_text_commands_see_the_label():
    from ga3.cli import _text_units

    proj, _segs_ = _segs()
    units = {seg.name: path for seg, path, _s in _text_units(proj)}
    assert units["options_labels"] == LABELS
    assert "options_menu" not in units
