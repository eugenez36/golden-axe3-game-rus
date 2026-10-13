"""ROM-gated tests: need baserom/ga3.bin. Skipped automatically when absent."""

import pytest

from ga3 import nemesis, text
from ga3 import pipeline as pl
from ga3.assets import Paths, handler_for
from ga3.rom import Rom, apply_ips

pytestmark = pytest.mark.rom


def test_header_fixes_are_noops(baserom):
    rom = Rom(bytes(baserom.data))  # the session fixture stays pristine
    rom.fix_rom_end()
    rom.fix_checksum()
    assert bytes(rom.data) == bytes(baserom.data)


def test_map_check_passes(project, baserom):
    assert pl.check_map(project, baserom) == []


def _generated_ranges(project) -> list[tuple[int, int]]:
    """Bytes the build generates rather than takes from assets: patch slots and their edits."""
    from ga3.assets.patch_asset import touched

    out = []
    for seg in project.map.by_type("patch"):
        out += [(seg.start, seg.end), *touched(seg)]
    return out


def test_extract_then_build_is_byte_identical(project, baserom, tmp_path):
    """Outside the generated patches, freshly extracted assets rebuild the base ROM exactly."""
    from ga3.assets.patch_asset import assembled, edits

    scratch = pl.Project(
        project.root, project.map, Paths(project.root, tmp_path / "assets", tmp_path / "build")
    )
    pl.extract_all(scratch, baserom, log=lambda *_: None)
    # a patch's own sources (strings, assembly) have no counterpart in the base ROM;
    # files extraction did produce (the font art) stay as extracted
    for seg in project.map.by_type("patch"):
        for src in handler_for(seg).sources(seg, project.paths):
            dst = scratch.paths.asset(str(src.relative_to(project.paths.assets)))
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
    built = pl.build(scratch, baserom, out=tmp_path / "out.bin", log=lambda *_: None)
    generated = _generated_ranges(project)
    assert generated, "rom_map.yml declares no patch; drop this masking"
    size = len(baserom.data)
    assert len(built.data) == project.map.image_size
    expansion = bytearray(built.data[size:])  # rom.build_size: FF outside the patch slots
    for start, end in generated:
        if start >= size:
            expansion[start - size : end - size] = b"\xff" * (end - start)
    assert expansion == b"\xff" * (project.map.image_size - size)
    masked = [bytearray(baserom.data), bytearray(built.data[:size])]
    for start, end in generated:
        for image in masked:
            image[start:end] = bytes(end - start)
    # the header checksum and ROM end follow the image; everything else must match
    for image in masked:
        image[0x18E:0x190] = b"\0\0"
        image[0x1A4:0x1A8] = b"\0\0\0\0"
    assert masked[0] == masked[1]
    for seg in project.map.by_type("patch"):
        if seg.get("patch_def") is not None:
            # the panel's tiles come from the font art, which here is the extracted one
            body, todo, _labels = assembled(seg, scratch.paths)
            assert bytes(built.data[seg.start : seg.start + len(body)]) == body
        else:
            todo = edits(seg)
        for e in todo:
            assert bytes(built.data[e.at : e.end]) == e.new


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
    # 202 before Latin V (0x40) and ё (0x3C) became text: binary data now reads as a few more runs
    assert count == 209


def test_pristine_free_font_slots(project, baserom):
    from ga3 import font

    seg = project.map.by_name("font")
    raw = nemesis.decompress(baserom.data, seg.start)
    # nine blank glyphs in the original translation ...
    # (0x20 is the space; 0x25 is the "solid block" whose pixels are all background
    #  because the menu swaps the background index -- both are in the table)
    blank = [0x20 + i for i in range(96) if font.is_blank(raw, i) and 0x20 + i not in (0x20, 0x25)]
    assert blank == [0x2A, 0x2B, 0x3C, 0x3E, 0x40, 0x4F, 0x51, 0x7B, 0x7F]
    # ... seven of which this project has since assigned (Ё Ъ ё, the parentheses, V and /)
    assert font.free_slots(raw) == [0x7B, 0x7F]


def test_loading_a_wrong_rom_is_refused(project, tmp_path):
    bad = tmp_path / "ga3.bin"
    bad.write_bytes(b"\0" * 0x100000)
    with pytest.raises(pl.PipelineError, match="sha1"):
        pl.load_baserom(project, bad)
    Rom.load(bad)  # plain loading is still allowed


def _message_lines(data: bytes, start: int, end: int) -> int:
    """FF-terminated lines of the dialogue message at ``start`` (header skipped), up to ``end``."""
    lines, pos = 0, start + 2
    while pos < end and data[pos] != 0x00:
        stop = data.index(0xFF, pos)
        if stop >= end:
            break
        lines += 1
        pos = stop + 1
    return lines


def test_every_dialogue_box_shows_all_its_lines(project, baserom, tmp_path):
    """Header byte 1 is the number of lines shown minus one; a smaller value cuts text off.

    Message 1 had 4 lines and a 3-line box, so «в округе.'» never appeared.
    """
    import struct

    built = pl.build(project, baserom, out=tmp_path / "out.bin", ips=False, log=lambda *_: None)
    data = bytes(built.data)
    seg = project.map.by_name("text_dialogue")
    table_at = seg.get("messages")
    starts = sorted(table_at + o for o in struct.unpack_from(">16H", data, table_at))
    bounds = dict(zip(starts, [*starts[1:], None], strict=True))
    wrong = []
    for start, nxt in bounds.items():
        shown = data[start + 1] + 1
        lines = _message_lines(data, start, nxt or seg.end)
        # the last message is followed by another text block, not by a message
        if (lines != shown) if nxt else (lines < shown):
            wrong.append(f"{start:06X}: {lines} lines, box shows {shown}")
    assert wrong == []
