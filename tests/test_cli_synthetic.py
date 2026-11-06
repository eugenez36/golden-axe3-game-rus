"""``ga3`` subcommands driven through ``main()`` against the synthetic project."""

from __future__ import annotations

import pytest

from ga3 import pipeline as pl
from ga3.cli import main

from .conftest import Synth


def run(s: Synth, *argv: str) -> int:
    return main(["--root", str(s.root), *argv])


def test_extract_check_build_verify(synthetic_project, capsys):
    s = synthetic_project
    assert run(s, "extract") == 0
    assert run(s, "map", "--check") == 0
    assert run(s, "map", "--list") == 0
    assert "tiles4bpp" in capsys.readouterr().out
    assert run(s, "build") == 0
    assert s.project.build_rom.read_bytes() == s.image
    assert run(s, "verify", "--update") == 0
    assert run(s, "verify") == 0
    assert "OK" in capsys.readouterr().out
    assert run(s, "build", "-o", str(s.root / "build" / "alt.bin"), "--no-ips") == 0
    assert (s.root / "build" / "alt.bin").read_bytes() == s.image
    assert not (s.root / "build" / "alt.ips").exists()


def test_inspection_commands(synthetic_extracted, capsys):
    s = synthetic_extracted
    assert run(s, "info") == 0
    assert "SYNTHETIC TEST IMAGE" in capsys.readouterr().out
    assert run(s, "balance", "show") == 0
    out = capsys.readouterr().out
    assert "slot_3              75 (0x4B)" in out and "entry_1          48879 (0xBEEF)" in out
    assert run(s, "text", "verify") == 0
    assert "3 strings" in capsys.readouterr().out
    assert run(s, "font", "info") == 0
    assert "96 tiles, slot 840 bytes" in capsys.readouterr().out
    assert run(s, "nemesis", "size", "260") == 0
    assert "4 tiles" in capsys.readouterr().out
    assert run(s, "tiles", "ascii", "700", "4", "--cols", "4") == 0
    assert "|" in capsys.readouterr().out
    assert run(s, "map") == 0
    assert "unknown" in capsys.readouterr().out


def test_balance_set_hp_writes_the_table(synthetic_extracted, capsys):
    s = synthetic_extracted
    assert run(s, "balance", "set-hp", "40", "41", "42", "0x2B") == 0
    assert run(s, "build") == 0
    assert bytes(s.project.build_rom.read_bytes()[0x210:0x214]) == bytes([40, 41, 42, 43])
    assert run(s, "balance", "set-hp", "1", "2") == 1
    assert "expected 4 values" in capsys.readouterr().err


def test_balance_set_writes_a_table_field(synthetic_extracted, capsys):
    s = synthetic_extracted
    assert run(s, "balance", "set", "words.entry_1", "0x1FF") == 0
    assert "words.entry_1: 48879 -> 511" in capsys.readouterr().out
    assert run(s, "balance", "set", "hp_table.slot_0", "60") == 0
    assert "more than the HUD can draw" in capsys.readouterr().err
    assert run(s, "build") == 0
    built = s.project.build_rom.read_bytes()
    assert built[0x210] == 60 and built[0x216:0x218] == b"\x01\xff"
    assert run(s, "balance", "set", "words.nope", "1") == 1
    assert "no field 'nope'; known: entry_0, entry_1" in capsys.readouterr().err
    assert run(s, "balance", "set", "words.entry_0", "70000") == 1
    assert "outside 0..65535" in capsys.readouterr().err
    assert run(s, "balance", "set", "text_demo.x", "1") == 1
    assert "not a table" in capsys.readouterr().err


def test_patch_and_diff(synthetic_project, capsys):
    s = synthetic_project
    a = s.root / pl.BASEROM_REL
    b = s.root / "b.bin"
    img = bytearray(s.image)
    img[0x900] ^= 0xFF
    b.write_bytes(img)
    ips = s.root / "build" / "x.ips"
    assert run(s, "patch", "make", str(a), str(b), "-o", str(ips)) == 0
    out = s.root / "build" / "x.bin"
    assert run(s, "patch", "apply", str(a), str(ips), "-o", str(out)) == 0
    assert out.read_bytes() == bytes(img)
    assert run(s, "diff", str(a), str(b)) == 0
    assert "changes: 1" in capsys.readouterr().out


def test_assets_refresh_is_idempotent(synthetic_extracted, capsys):
    s = synthetic_extracted
    assert run(s, "assets", "refresh") == 0
    assert "refreshed" in capsys.readouterr().out
    assert (s.root / "docs" / "rom_map.md").exists()
    assert s.asset("text/encoding.tbl").exists()
    assert run(s, "assets") == 0
    assert "up to date" in capsys.readouterr().out


def test_missing_base_rom_is_a_clean_error(synthetic_project, capsys):
    s = synthetic_project
    (s.root / "baserom" / "ga3.bin").unlink()
    assert run(s, "build") == 1
    assert capsys.readouterr().err.startswith("error: base ROM not found")


@pytest.mark.parametrize("cmd", [["map", "--markdown"], ["--help"]])
def test_help_and_markdown_do_not_need_the_rom(synthetic_project, cmd, capsys):
    s = synthetic_project
    if cmd == ["--help"]:
        with pytest.raises(SystemExit) as exc:
            main(cmd)
        assert exc.value.code == 0
    else:
        assert run(s, *cmd) == 0
        assert "| Range |" in capsys.readouterr().out


# ---------------------------------------------------------------- regression tests


def _variant(s: Synth, name: str, off: int, value: int):
    img = bytearray(s.image)
    img[off] = value
    p = s.root / name
    p.write_bytes(img)
    return p


def test_info_honours_global_rom_and_positional_file(synthetic_project, capsys):
    s = synthetic_project
    alt = _variant(s, "alt.bin", 0x120, ord("X"))  # first letter of the domestic name
    assert run(s, "--rom", str(alt), "info") == 0
    assert "XYNTHETIC" in capsys.readouterr().out
    assert run(s, "info", str(alt)) == 0
    assert "XYNTHETIC" in capsys.readouterr().out
    assert run(s, "info") == 0
    assert "'SYNTHETIC" in capsys.readouterr().out


def test_build_from_an_explicit_rom_is_trusted_with_a_note(synthetic_extracted, capsys):
    s = synthetic_extracted
    free = s.seg("free_02CF").start  # never written by any handler
    alt = _variant(s, "alt.bin", free, 0x00)
    out = s.root / "build" / "alt_build.bin"
    assert run(s, "--rom", str(alt), "build", "-o", str(out)) == 0
    assert "note:" in capsys.readouterr().err
    assert out.read_bytes()[free] == 0x00
    assert run(s, "build", "--rom", str(alt), "-o", str(out)) == 0  # subcommand position too
    assert run(s, "--rom", str(alt), "map", "--check") == 1  # the free slot no longer holds 0xFF


def test_commands_outside_any_project(tmp_path, fixtures, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GA3_ROOT", raising=False)
    tiny = str(fixtures / "tiny.4bpp")
    assert main(["tiles", "ascii", "0", "4", "--file", tiny]) == 0
    assert main(["tiles", "ascii", "0", "4"]) == 1
    assert capsys.readouterr().err.startswith("error: no rom_map.yml found")
    assert main(["map"]) == 1
    assert "rom_map.yml not found" in capsys.readouterr().err
    assert main(["--root", str(tmp_path / "nowhere"), "map"]) == 1
    assert "rom_map.yml not found" in capsys.readouterr().err


def test_unknown_segment_name_is_a_clean_error(synthetic_extracted, capsys):
    s = synthetic_extracted
    import yaml

    doc = yaml.safe_load((s.root / pl.MAP_FILE).read_text(encoding="utf-8"))
    doc["segments"] = [seg for seg in doc["segments"] if seg["name"] != "hp_table"]
    (s.root / pl.MAP_FILE).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert run(s, "balance", "set-hp", "1", "2", "3", "4") == 1
    assert capsys.readouterr().err.startswith("error: no segment named 'hp_table'")


def test_build_errors_from_direct_handler_calls_are_clean(synthetic_extracted, capsys):
    s = synthetic_extracted
    s.asset("gfx/font/font.txt").unlink()
    assert run(s, "font", "info") == 1
    assert capsys.readouterr().err.startswith("error: font")


def test_ramsearch_errors_and_option_placement(tmp_path, capsys):
    from ga3.cli import build_parser

    assert main(["ramsearch", "corr", str(tmp_path / "none*.bin"), "1,2"]) == 1
    assert capsys.readouterr().err.startswith("error: no dumps match")
    args = build_parser().parse_args(
        ["ramsearch", "corr", "p", "1,2", "--limit", "5", "--min-distinct", "2"]
    )
    assert (args.limit, args.min_distinct) == (5, 2)
    args = build_parser().parse_args(["ramsearch", "value", "p", "7", "--limit", "3"])
    assert args.limit == 3


def test_map_check_assets_without_the_rom(synthetic_extracted, capsys):
    s = synthetic_extracted
    (s.root / pl.BASEROM_REL).unlink()
    assert run(s, "map", "--check-assets") == 0
    s.asset("gfx/tiles/art_01.png").unlink()
    assert run(s, "map", "--check-assets") == 1
    assert "missing assets/gfx/tiles/art_01.png" in capsys.readouterr().out


def test_malformed_map_is_a_clean_error(synthetic_project, capsys):
    s = synthetic_project
    (s.root / pl.MAP_FILE).write_text("rom: [unclosed\n", encoding="utf-8")
    assert run(s, "map") == 1
    assert "not valid YAML" in capsys.readouterr().err
