"""ROM-gated tests: need baserom/ga3.bin. Skipped automatically when absent."""

import pytest

from ga3 import nemesis, text
from ga3 import pipeline as pl
from ga3.assets import Paths
from ga3.rom import Rom, apply_ips

pytestmark = pytest.mark.rom


def test_header_fixes_are_noops(baserom):
    rom = Rom(bytes(baserom.data))  # the session fixture stays pristine
    rom.fix_rom_end()
    rom.fix_checksum()
    assert bytes(rom.data) == bytes(baserom.data)


def test_map_check_passes(project, baserom):
    assert pl.check_map(project, baserom) == []


def test_extract_then_build_is_byte_identical(project, baserom, tmp_path):
    scratch = pl.Project(
        project.root, project.map, Paths(project.root, tmp_path / "assets", tmp_path / "build")
    )
    pl.extract_all(scratch, baserom, log=lambda *_: None)
    built = pl.build(scratch, baserom, out=tmp_path / "out.bin", log=lambda *_: None)
    assert bytes(built.data) == bytes(baserom.data)
    ips = (tmp_path / "out.ips").read_bytes()
    assert ips == b"PATCHEOF"


def test_committed_assets_build_to_recorded_sha1(project, baserom, tmp_path):
    built = pl.build(project, baserom, out=tmp_path / "out.bin", ips=True, log=lambda *_: None)
    want = pl.read_sha_file(project.sha_file).get(pl.BUILD_ROM_REL)
    assert want, "roms.sha1 has no entry for the build; run `ga3 verify --update`"
    assert built.sha1() == want
    ips = (tmp_path / "out.ips").read_bytes()
    assert apply_ips(bytes(baserom.data), ips) == bytes(built.data)


def test_nemesis_parity_on_all_blocks(project, baserom):
    total_rom = total_ours = 0
    for seg in project.map.by_type("nemesis"):
        size = nemesis.block_size(baserom.data, seg.start)
        raw = nemesis.decompress(baserom.data, seg.start)
        assert len(raw) == seg.get("tiles") * 32
        assert size <= seg.size <= size + 2
        ours = nemesis.compress(raw, xor_mode=seg.get("xor"), slack=False)
        assert nemesis.decompress_blob(ours) == raw
        assert len(ours) <= size, f"{seg}: ours {len(ours)} > original {size}"
        total_rom += size
        total_ours += len(ours)
    assert total_rom == 14045
    assert total_ours < total_rom


def test_text_roundtrip_over_all_segments(project, baserom):
    count = 0
    for seg in project.map.by_type("text"):
        for off, ln, txt in text.find_strings(
            baserom.data, seg.start, seg.end, seg.get("min_len", 4)
        ):
            assert text.table.encode(txt) == bytes(baserom.data[off : off + ln])
            count += 1
    assert count == 202


def test_pristine_free_font_slots(project, baserom):
    from ga3 import font

    seg = project.map.by_name("font")
    raw = nemesis.decompress(baserom.data, seg.start)
    # nine blank glyphs in the original translation ...
    # (0x20 is the space; 0x25 is the "solid block" whose pixels are all background
    #  because the menu swaps the background index -- both are in the table)
    blank = [0x20 + i for i in range(96) if font.is_blank(raw, i) and 0x20 + i not in (0x20, 0x25)]
    assert blank == [0x2A, 0x2B, 0x3C, 0x3E, 0x40, 0x4F, 0x51, 0x7B, 0x7F]
    # ... four of which this project has since assigned (Ё Ъ and the parentheses)
    assert font.free_slots(raw) == [0x3C, 0x3E, 0x40, 0x7B, 0x7F]


def test_loading_a_wrong_rom_is_refused(project, tmp_path):
    bad = tmp_path / "ga3.bin"
    bad.write_bytes(b"\0" * 0x100000)
    with pytest.raises(pl.PipelineError, match="sha1"):
        pl.load_baserom(project, bad)
    Rom.load(bad)  # plain loading is still allowed
