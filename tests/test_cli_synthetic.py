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
    assert "slot_3      75" in capsys.readouterr().out
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
