"""The options item БАНКИ МАГИИ (patch options): starting magic potions."""

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


def test_label_is_one_record_from_the_slot_start():
    _proj, segs = _segs()
    rows = text.parse_strings_file(str(LABELS))
    width = _sym()["LABEL_WIDTH"]
    assert [(off, ln) for off, ln, _t in rows] == [(segs["labels"].start, width)]
    assert [t for _o, _l, t in rows] == ["БАНКИ МАГИИ"]


def test_patch_assembles_label_and_hooks():
    pytest.importorskip("capstone")
    from ga3.assets.patch_asset import assembled

    proj, segs = _segs()
    body, _todo, labels = assembled(segs["labels"], proj.paths)
    assert body == table.encode("БАНКИ МАГИИ")
    assert labels["LABELS"] == segs["labels"].start
    body, todo, labels = assembled(segs["menu"], proj.paths)
    assert 0 < len(body) <= segs["menu"].size
    hooks = {e.at: e.new for e in todo}
    assert sorted(hooks) == [0x00E476, 0x0150FE, 0x01525A, 0x0152C8, 0x01543C]
    assert hooks[0x00E476] == b"\x4e\xf9" + labels["refill"].to_bytes(4, "big")  # jmp refill.l


def test_menu_moves_three_rows_down_for_the_new_item():
    sym = _sym()
    [layout] = [t for off, _ln, t in text.parse_strings_file(str(MENU)) if off == 0x01512C]
    assert "{08}{19}МЕНЮ" in layout and "{08}{16}" not in layout
    assert sym["POT_LABEL"] == 0xC000 + 0x16 * 0x80 + 8 * 2  # МЕНЮ's old place
    assert sym["POT_CELL"] == 0xC000 + 0x16 * 0x80 + 0x18 * 2  # under the МУЗ./ЗВУК values
    assert (sym["ITEMS"], sym["POT_ITEM"], sym["MENU_ITEM"]) == (6, 4, 5)


def test_default_is_the_potions_constant_and_the_hud_limit():
    proj, _segs_ = _segs()
    sym = _sym()
    potions = proj.map.constants["potions"]
    [site] = potions.sites
    assert sym["DEFAULT"] == site.at + site.offset  # the operand of the bypassed move
    assert sym["REFILL_BACK"] == site.at + len(site.expect)
    assert sym["POT_MAX"] == potions.get("max") == 6


def test_setting_lives_in_the_byte_kept_over_a_soft_reset():
    sym = _sym()
    assert sym["POT"] == 0xC729  # 0002CC/0002E8 keep the long at $C726 (difficulty, buttons)


def test_text_commands_see_the_label():
    from ga3.cli import _text_units

    proj, _segs_ = _segs()
    units = {seg.name: path for seg, path, _s in _text_units(proj)}
    assert units["options_labels"] == LABELS
    assert "options_menu" not in units
