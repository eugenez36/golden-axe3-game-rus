"""Gameplay constants: instruction operands edited by name (``constants:`` in rom_map.yml)."""

from __future__ import annotations

import hashlib
import re

import pytest
import yaml

from ga3 import balance, rom_map
from ga3 import pipeline as pl
from ga3.cli import main
from ga3.rom import Rom

from .conftest import Synth

# The synthetic "boot" code at 0x200 holds 00 01 02 ... 0F; the fixture makes
# 0x20B a 05 so that two "instructions" carry the same constant.
SITES = [[0x204, "04 05 06", 1], [0x20A, "0A 05", 1]]


def _with_constants(s: Synth, values: dict) -> Synth:
    doc = yaml.safe_load((s.root / pl.MAP_FILE).read_text(encoding="utf-8"))
    doc["constants"] = {"path": "data/gameplay.yml", "values": values}
    (s.root / pl.MAP_FILE).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    s.project = pl.open_project(s.root)
    return s


@pytest.fixture
def synth_constants(synthetic_project) -> Synth:
    s = synthetic_project
    img = bytearray(s.image)
    img[0x20B] = 0x05
    rom = Rom(img)
    rom.fix_checksum()
    s.image = bytes(rom.data)
    (s.root / pl.BASEROM_REL).write_bytes(s.image)
    doc = yaml.safe_load((s.root / pl.MAP_FILE).read_text(encoding="utf-8"))
    doc["rom"]["sha1"] = hashlib.sha1(s.image).hexdigest()
    doc["rom"]["header_checksum"] = rom.stored_checksum()
    (s.root / pl.MAP_FILE).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    v = {"format": "u8", "sites": SITES, "max_hud": 9, "note": "demo", "evidence": "synthetic"}
    return _with_constants(s, {"lives": v})


def _parse(values: dict) -> rom_map.RomMap:
    doc = {"rom": {"size": 0x100}, "segments": [], "constants": {"path": "x.yml", "values": values}}
    return rom_map.parse(doc)


def test_parse_reads_sites_and_rejects_bad_definitions():
    site = [0x10, "11 FC 00 04 C7 7C", 2]
    rm = _parse({"n": {"format": "u16", "sites": [site], "evidence": "e"}})
    c = rm.constants["n"]
    assert (c.format, c.width, c.sites[0].at, c.sites[0].offset) == ("u16", 2, 0x10, 2)
    assert c.sites[0].expect == bytes.fromhex("11FC0004C77C")
    bad = [
        ({"sites": [[0x10, "00", 0]]}, "evidence is required"),
        ({"format": "u32", "sites": [[0x10, "00", 0]], "evidence": "e"}, "format must be"),
        ({"sites": [[0x10, "zz", 0]], "evidence": "e"}, "not hex bytes"),
        ({"format": "u16", "sites": [[0x10, "00 01", 1]], "evidence": "e"}, "runs past"),
        ({"sites": [[0xFF, "00 01", 0]], "evidence": "e"}, "past rom.size"),
        ({"sites": [], "evidence": "e"}, "sites:"),
        ({"sites": [site], "max": 256, "evidence": "e"}, "max must be within"),
        ({"sites": [site], "max": "6", "evidence": "e"}, "max must be an integer"),
    ]
    for d, msg in bad:
        with pytest.raises(rom_map.RomMapError, match=msg):
            _parse({"n": d})


def test_extract_check_and_identity_build(synth_constants):
    s = synth_constants
    pl.extract_all(s.project, s.rom, log=lambda *_: None)
    gp = s.root / "assets" / "data" / "gameplay.yml"
    assert yaml.safe_load(gp.read_text(encoding="utf-8"))["values"] == {"lives": 5}
    assert "demo" in gp.read_text(encoding="utf-8")  # the note is in the header
    assert pl.check_map(s.project, s.rom) == []
    out = pl.build(s.project, s.rom, log=lambda *_: None)
    assert bytes(out.data) == s.image


def test_build_writes_every_site_and_nothing_else(synth_constants):
    s = synth_constants
    pl.extract_all(s.project, s.rom, log=lambda *_: None)
    gp = s.root / "assets" / "data" / "gameplay.yml"
    old, warnings = balance.set_constant(s.project.map, gp, "lives", 12)
    assert old == 5 and warnings and "HUD" in warnings[0]
    notes = []
    out = bytes(pl.build(s.project, s.rom, log=notes.append).data)
    assert out[0x205] == 12 and out[0x20B] == 12
    changed = {i for i in range(len(out)) if out[i] != s.image[i]}
    assert changed - {0x18E, 0x18F} == {0x205, 0x20B}  # plus the header checksum
    assert any("lives: 5 -> 12" in n and "HUD" in n for n in notes)


def test_drifted_map_and_bad_values_fail_cleanly(synth_constants):
    s = synth_constants
    pl.extract_all(s.project, s.rom, log=lambda *_: None)
    gp = s.root / "assets" / "data" / "gameplay.yml"
    gp.write_text("values:\n  lives: 256\n", encoding="utf-8")
    with pytest.raises(pl.PipelineError, match=r"outside 0\.\.255 \(u8\)"):
        pl.build(s.project, s.rom, log=lambda *_: None)
    gp.write_text("values: {}\n", encoding="utf-8")
    with pytest.raises(pl.PipelineError, match="no value for 'lives'"):
        pl.build(s.project, s.rom, log=lambda *_: None)
    v = {"format": "u8", "sites": [[0x204, "04 99 06", 1]], "evidence": "synthetic"}
    _with_constants(s, {"lives": v})
    gp.write_text("values:\n  lives: 5\n", encoding="utf-8")
    assert any("0x000204 holds 04 05 06" in p for p in pl.check_map(s.project, s.rom))
    with pytest.raises(pl.PipelineError, match="expected 04 99 06"):
        pl.build(s.project, s.rom, log=lambda *_: None)


def test_max_is_a_hard_limit(synth_constants):
    """``max`` refuses a value the game cannot handle; ``max_hud`` only warns."""
    s = synth_constants
    v = {"format": "u8", "sites": SITES, "max": 6, "evidence": "synthetic"}
    _with_constants(s, {"lives": v})
    assert s.project.map.constants["lives"].limit == 6
    pl.extract_all(s.project, s.rom, log=lambda *_: None)
    gp = s.root / "assets" / "data" / "gameplay.yml"
    assert balance.set_constant(s.project.map, gp, "lives", 6) == (5, [])
    with pytest.raises(ValueError, match=r"outside 0\.\.6"):
        balance.set_constant(s.project.map, gp, "lives", 7)
    gp.write_text("values:\n  lives: 7\n", encoding="utf-8")  # edited by hand
    with pytest.raises(pl.PipelineError, match=r"outside 0\.\.6"):
        pl.build(s.project, s.rom, log=lambda *_: None)


def test_quick_site_edits_the_count_of_a_subq(synth_constants):
    """``[address, bytes, offset, quick]``: the 3-bit count of addq / subq (8 is stored as 0)."""
    s = synth_constants
    img = bytearray(s.image)
    img[0x20C:0x210] = bytes.fromhex("5B29013E")  # subq.b #5,$13e(a1)
    rom = Rom(img)
    rom.fix_checksum()
    s.image = bytes(rom.data)
    (s.root / pl.BASEROM_REL).write_bytes(s.image)
    doc = yaml.safe_load((s.root / pl.MAP_FILE).read_text(encoding="utf-8"))
    doc["rom"]["sha1"] = hashlib.sha1(s.image).hexdigest()
    doc["rom"]["header_checksum"] = rom.stored_checksum()
    (s.root / pl.MAP_FILE).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    sites = [[0x204, "04 05 06", 1], [0x20C, "5B 29 01 3E", 0, "quick"]]
    v = {"format": "u8", "sites": sites, "max": 8, "evidence": "synthetic"}
    _with_constants(s, {"lives": v})
    assert s.project.map.constants["lives"].sites[1].quick
    pl.extract_all(s.project, s.rom, log=lambda *_: None)
    gp = s.root / "assets" / "data" / "gameplay.yml"
    assert yaml.safe_load(gp.read_text(encoding="utf-8"))["values"] == {"lives": 5}
    assert pl.check_map(s.project, s.rom) == []
    for value, word in ((3, "5729"), (8, "5129"), (1, "5329")):
        balance.set_constant(s.project.map, gp, "lives", value)
        out = bytes(pl.build(s.project, s.rom, log=lambda *_: None).data)
        assert out[0x205] == value and out[0x20C:0x20E].hex() == word, value
    gp.write_text("values:\n  lives: 0\n", encoding="utf-8")
    with pytest.raises(pl.PipelineError, match=r"holds 1\.\.8"):
        pl.build(s.project, s.rom, log=lambda *_: None)
    for d, msg in (
        ({"sites": [[0x20C, "5B 29", 0, "quick"]], "max": 9, "evidence": "e"}, "max at most 8"),
        ({"format": "u16", "sites": [[0x20C, "5B 29", 0, "quick"]], "evidence": "e"}, "format u8"),
        ({"sites": [[0x20C, "5B", 0, "quick"]], "evidence": "e"}, "runs past"),
        ({"sites": [[0x20C, "5B 29", 0, "fast"]], "evidence": "e"}, "quick"),
    ):
        with pytest.raises(rom_map.RomMapError, match=msg):
            _parse({"n": d})


def test_missing_asset_is_reported(synth_constants):
    s = synth_constants
    assert any("constants: missing" in p for p in pl.check_assets(s.project))


def test_balance_cli_shows_and_sets(synth_constants, capsys):
    s = synth_constants
    root = ["--root", str(s.root)]
    assert main([*root, "extract"]) == 0
    assert main([*root, "balance", "set", "lives", "3"]) == 0
    assert main([*root, "balance", "show"]) == 0
    assert re.search(r"lives\s+3 \(u8 at 000204, 00020A\)", capsys.readouterr().out)
    assert main([*root, "balance", "set", "nope", "1"]) == 1
    assert main([*root, "balance", "set", "lives", "300"]) == 1


def test_rom_map_doc_lists_the_constants(synth_constants):
    table = rom_map.constants_table(synth_constants.project.map)
    assert "| lives | u8 | `000204`, `00020A` | demo; *evidence: synthetic* |" in table
