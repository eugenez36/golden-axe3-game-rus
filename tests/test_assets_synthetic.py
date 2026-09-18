"""Every asset handler and the pipeline, exercised on the synthetic image (no ROM needed)."""

from __future__ import annotations

import struct

import pytest

from ga3 import nemesis, palette, table
from ga3 import pipeline as pl
from ga3.assets import Paths, handler_for

from .conftest import Synth

EXPECTED_FILES = {
    "header/vectors.yml",
    "header/header.yml",
    "code/boot.m68k",
    "data/hp_table.yml",
    "data/words.yml",
    "raw/unknown_000218.raw",
    "text/demo.txt",
    "gfx/nemesis/tiny.nem",
    "gfx/nemesis/tiny.4bpp",
    "gfx/font/font.txt",
    "gfx/nemesis/font.nem",
    "raw/unknown_000648.raw",
    "gfx/tiles/art_00.png",
    "gfx/tiles/art_01.png",
    "sound/pcm/samples.pcm",
    "raw/blob.raw",
    "code/tail.m68k",
}


def _build(s: Synth, **kw):
    return pl.build(s.project, s.rom, log=lambda *_: None, **kw)


def _notes(s: Synth) -> dict[str, str]:
    notes: dict[str, str] = {}

    def log(line: str) -> None:
        parts = line.split(None, 2)
        if len(parts) == 3 and "-" in parts[0]:
            notes[parts[1]] = parts[2]

    pl.build(s.project, s.rom, out=s.root / "build" / "noted.bin", log=log)
    return notes


def test_extract_writes_every_expected_file(synthetic_project):
    s = synthetic_project
    files = pl.extract_all(s.project, s.rom, log=lambda *_: None)
    rel = {str(p.relative_to(s.project.paths.assets)) for p in files}
    assert rel == EXPECTED_FILES
    assert all(p.exists() for p in files)


def test_extract_then_build_is_byte_identical_without_rom(synthetic_extracted):
    s = synthetic_extracted
    out = s.root / "build" / "out.bin"
    built = _build(s, out=out)
    assert bytes(built.data) == s.image
    assert out.read_bytes() == s.image
    assert (s.root / "build" / "out.ips").read_bytes() == b"PATCHEOF"


def test_check_map_is_clean_on_synthetic_image(synthetic_extracted):
    s = synthetic_extracted
    assert pl.check_map(s.project, s.rom) == []


def test_check_map_reports_free_fill_and_header_mismatch(synthetic_extracted):
    s = synthetic_extracted
    bad = bytearray(s.image)
    free = s.seg("free_02CF")
    bad[free.start] = 0x00
    struct.pack_into(">I", bad, 4, 0x300)  # reset vector no longer the entry point
    problems = pl.check_map(s.project, type(s.rom)(bytes(bad)))
    assert any("expected fill 0xFF" in p for p in problems)
    assert any("reset vector" in p for p in problems)


# ---------------------------------------------------------------- header


def test_header_field_width_is_enforced(synthetic_extracted):
    s = synthetic_extracted
    p = s.asset("header/header.yml")
    p.write_text(p.read_text(encoding="utf-8").replace("'SEGA MEGA DRIVE '", "SEGA"), "utf-8")
    with pytest.raises(pl.PipelineError, match="exactly 16 bytes"):
        _build(s)


def test_missing_vector_is_refused(synthetic_extracted):
    s = synthetic_extracted
    p = s.asset("header/vectors.yml")
    lines = p.read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in lines if not ln.startswith("trap_3:")]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(pl.PipelineError, match="missing trap_3"):
        _build(s)


def test_non_ascii_header_field_roundtrips_as_hex(synthetic_project, tmp_path):
    s = synthetic_project
    img = bytearray(s.image)
    img[0x1C8] = 0x01  # first byte of `notes` is no longer printable
    rom = type(s.rom)(bytes(img))
    scratch = pl.Project(s.root, s.project.map, Paths(s.root, tmp_path / "a", tmp_path / "b"))
    pl.extract_all(scratch, rom, log=lambda *_: None)
    assert "hex:" in (tmp_path / "a" / "header" / "header.yml").read_text(encoding="utf-8")
    built = pl.build(scratch, rom, out=tmp_path / "out.bin", ips=False, log=lambda *_: None)
    assert bytes(built.data) == bytes(img)


# ---------------------------------------------------------------- table


def test_table_edit_and_range(synthetic_extracted):
    s = synthetic_extracted
    p = s.asset("data/hp_table.yml")
    p.write_text(p.read_text(encoding="utf-8").replace("slot_0: 51", "slot_0: 40"), "utf-8")
    notes = _notes(s)
    assert notes["hp_table"].startswith("changed")
    built = _build(s, ips=False)
    assert built.data[s.seg("hp_table").start] == 40

    p.write_text(p.read_text(encoding="utf-8").replace("slot_0: 40", "slot_0: 256"), "utf-8")
    with pytest.raises(pl.PipelineError, match="0..255"):
        _build(s)


def test_table_u16_roundtrip_and_format_mismatch(synthetic_extracted):
    s = synthetic_extracted
    p = s.asset("data/words.yml")
    txt = p.read_text(encoding="utf-8")
    assert "entry_0: 4660" in txt and "entry_1: 48879" in txt  # 0x1234, 0xBEEF
    p.write_text(txt.replace("format: u16", "format: u8"), "utf-8")
    with pytest.raises(pl.PipelineError, match="format 'u8' != map format 'u16'"):
        _build(s)


# ---------------------------------------------------------------- text


def test_text_shorten_pads_grow_and_unknown_refused(synthetic_extracted):
    s = synthetic_extracted
    p = s.asset("text/demo.txt")
    txt = p.read_text(encoding="utf-8")
    assert "000220:5 | ИГРОК" in txt
    p.write_text(txt.replace("| ИГРОК", "| ИГР"), "utf-8")
    built = _build(s, ips=False)
    assert bytes(built.data[0x220:0x225]) == table.encode("ИГР") + b"\x20\x20"

    p.write_text(txt.replace("| ИГРОК", "| ИГРОКИ"), "utf-8")
    with pytest.raises(pl.PipelineError, match="longer than the original"):
        _build(s)
    p.write_text(txt.replace("| ИГРОК", "| ИГРОß"), "utf-8")
    with pytest.raises(pl.PipelineError, match="not in the game font"):
        _build(s)


# ---------------------------------------------------------------- nemesis


def test_nemesis_verbatim_then_recompressed_after_edit(synthetic_extracted):
    s = synthetic_extracted
    seg = s.seg("nem_tiny")
    assert "nem_tiny" not in _notes(s)  # untouched block: written back verbatim
    raw_path = s.asset("gfx/nemesis/tiny.4bpp")
    raw = bytearray(raw_path.read_bytes())
    raw[0] ^= 0x0F
    raw_path.write_bytes(raw)
    notes = _notes(s)
    assert notes["nem_tiny"].startswith("recompressed")
    built = _build(s, ips=False)
    assert nemesis.decompress(built.data, seg.start) == bytes(raw)
    size = nemesis.block_size(built.data, seg.start)
    assert not any(built.data[seg.start + size : seg.end])  # zero padded to the slot


def test_nemesis_tile_count_is_enforced(synthetic_extracted):
    s = synthetic_extracted
    raw_path = s.asset("gfx/nemesis/tiny.4bpp")
    raw_path.write_bytes(raw_path.read_bytes() + b"\x00" * 32)
    with pytest.raises(pl.PipelineError, match="expected 4 tiles, got 5"):
        _build(s)


def test_font_art_edit_recompresses_and_refresh_blob_rewrites_nem(synthetic_extracted):
    s = synthetic_extracted
    seg = s.seg("font")
    art = s.asset("gfx/font/font.txt")
    blob = s.asset("gfx/nemesis/font.nem")
    before = blob.read_bytes()
    txt = art.read_text(encoding="utf-8")
    assert "@ 3C  FREE" in txt
    txt = txt.replace("@ 3C  FREE\n" + "........\n" * 8, "@ 3C  FREE\n" + "#......#\n" * 8)
    art.write_text(txt, encoding="utf-8")
    assert _notes(s)["font"].startswith("recompressed")
    h = handler_for(seg)
    path, did = h.refresh_blob(seg, s.project.paths)
    assert did and path == blob and blob.read_bytes() != before
    assert "font" not in _notes(s)  # the refreshed .nem is now used verbatim
    built = _build(s, ips=False)
    raw = nemesis.decompress(built.data, seg.start)
    assert raw[(0x3C - 0x20) * 32 : (0x3C - 0x20) * 32 + 4] == b"\x6c\xcc\xcc\xc6"


# ---------------------------------------------------------------- tiles4bpp


def test_tiles_sheets_use_pal_palette_and_roundtrip_edits(synthetic_extracted):
    Image = pytest.importorskip("PIL.Image")
    s = synthetic_extracted
    seg = s.seg("art")
    demo = palette.load_pal(str(s.asset("palettes/demo.pal")))[0]
    img = Image.open(s.asset("gfx/tiles/art_00.png"))
    assert img.mode == "P" and tuple(img.getpalette()[:3]) == demo[0]

    sheet = s.asset("gfx/tiles/art_01.png")
    img = Image.open(sheet)
    px = img.load()
    px[0, 0] = (px[0, 0] + 1) % 16
    img.save(sheet)
    assert _notes(s)["art"] == "changed"
    built = _build(s, ips=False)
    first = seg.start + 4 * 32  # tile 4 = first tile of sheet 1
    assert (built.data[first] >> 4) == px[0, 0]


def test_tiles_rgb_sheet_is_rejected(synthetic_extracted):
    Image = pytest.importorskip("PIL.Image")
    s = synthetic_extracted
    sheet = s.asset("gfx/tiles/art_00.png")
    Image.open(sheet).convert("RGB").save(sheet)
    with pytest.raises(pl.PipelineError, match="mode P"):
        _build(s)


# ---------------------------------------------------------------- raw / passthrough


def test_passthrough_override_size_check_and_missing_pcm(synthetic_extracted):
    s = synthetic_extracted
    boot = s.asset("code/boot.m68k")
    boot.write_bytes(bytes(reversed(range(16))))
    assert _notes(s)["boot"] == "1 file(s)"
    built = _build(s, ips=False)
    assert bytes(built.data[0x200:0x210]) == bytes(reversed(range(16)))

    boot.write_bytes(b"\x00" * 15)
    with pytest.raises(pl.PipelineError, match="15 bytes, slot is 16"):
        _build(s)
    boot.unlink()  # passthrough again
    assert "boot" not in _notes(s)

    s.asset("sound/pcm/samples.pcm").unlink()
    with pytest.raises(pl.PipelineError, match="missing asset file"):
        _build(s)


def test_unknown_gap_files_are_optional(synthetic_extracted):
    s = synthetic_extracted
    s.asset("raw/unknown_000218.raw").unlink()
    assert bytes(_build(s, ips=False).data) == s.image


# ---------------------------------------------------------------- verify


def test_verify_records_and_checks_hashes(synthetic_extracted):
    s = synthetic_extracted
    log: list[str] = []
    assert pl.verify(s.project, log=log.append) is False  # no build yet
    assert any("MISSING" in ln for ln in log)
    _build(s)
    assert pl.verify(s.project, update=True, log=lambda *_: None) is True
    sha = pl.read_sha_file(s.project.sha_file)
    assert set(sha) == {pl.BASEROM_REL, pl.BUILD_ROM_REL}
    assert pl.verify(s.project, log=lambda *_: None) is True

    s.project.build_ips.write_bytes(b"PATCH\x00\x02\x00\x00\x01\xffEOF")
    log.clear()
    assert pl.verify(s.project, log=log.append) is False
    assert any("does not reproduce" in ln for ln in log)
