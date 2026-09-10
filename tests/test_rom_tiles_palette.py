import os
import random
import struct

import pytest

from ga3 import palette, tiles
from ga3.rom import Rom, apply_ips, diff, make_ips


def _image(size=0x400, seed=1):
    rnd = random.Random(seed)
    data = bytearray(rnd.getrandbits(8) for _ in range(size))
    data[0x100:0x110] = b"SEGA MEGA DRIVE "
    return data


def test_checksum_and_header_fixes():
    rom = Rom(_image(0x401))  # odd length exercises the zero-padded tail
    rom.fix_checksum()
    assert rom.checksum_ok()
    assert rom.fix_rom_end() == 0x400
    assert rom.rom_bounds()[1] == 0x400
    body = bytes(rom.data[0x200:]) + b"\x00"
    assert rom.compute_checksum() == sum(struct.unpack(f">{len(body) // 2}H", body)) & 0xFFFF


def test_save_requires_path_and_fixes_header(tmp_path):
    rom = Rom(_image())
    out = tmp_path / "x.bin"
    rom.save(out)
    back = Rom.load(out)
    assert back.checksum_ok()
    assert back.sha1() == rom.sha1()


def test_expand():
    rom = Rom(_image())
    rom.expand(0x800, fill=0xEE)
    assert len(rom.data) == 0x800 and rom.data[-1] == 0xEE
    with pytest.raises(ValueError):
        rom.expand(0x10)


def test_diff_merges_close_edits():
    a = bytes(_image())
    b = bytearray(a)
    b[10] ^= 1
    b[15] ^= 1  # within max_gap=8 -> one span
    b[100] ^= 1
    ch = diff(a, bytes(b))
    assert [(o, len(n)) for o, _, n in ch] == [(10, 6), (100, 1)]


def test_ips_roundtrip_including_large_run_and_eof_collision():
    a = bytes(_image(0x460000, seed=2))
    b = bytearray(a)
    b[0x454F46] ^= 0xFF  # offset that spells "EOF"
    for i in range(0x20000):  # > 0xFFFF contiguous bytes
        b[0x1000 + i] ^= 0x5A
    b[-1] ^= 1
    patch = make_ips(a, bytes(b))
    assert patch.startswith(b"PATCH") and patch.endswith(b"EOF")
    assert apply_ips(a, patch) == bytes(b)


def test_ips_apply_rle_and_truncate():
    a = b"\x00" * 16
    ips = (
        b"PATCH" + b"\x00\x00\x04" + b"\x00\x00" + b"\x00\x03" + b"\xaa" + b"EOF" + b"\x00\x00\x08"
    )
    out = apply_ips(a, ips)
    assert out == b"\x00" * 4 + b"\xaa" * 3 + b"\x00"


def test_tile_codec_identity():
    rnd = random.Random(3)
    for _ in range(50):
        t = bytes(rnd.getrandbits(8) for _ in range(32))
        assert tiles.tile_encode(tiles.tile_decode(t)) == t


def test_indexed_png_roundtrip(tmp_path):
    pytest.importorskip("PIL")
    rnd = random.Random(4)
    raw = bytes(rnd.getrandbits(8) for _ in range(32 * 40))
    img = tiles.render_indexed(raw, 0, 40, cols=16)
    p = tmp_path / "t.png"
    img.save(p)
    assert tiles.import_indexed(str(p), count=40) == raw
    # an RGB file must be rejected: it lost the indices
    img.convert("RGB").save(tmp_path / "rgb.png")
    with pytest.raises(ValueError):
        tiles.import_indexed(str(tmp_path / "rgb.png"))


def test_rgb_png_roundtrip_with_gray16(tmp_path):
    pytest.importorskip("PIL")
    rnd = random.Random(5)
    raw = bytes(rnd.getrandbits(8) for _ in range(32 * 8))
    p = tmp_path / "g.png"
    tiles.dump_tiles(raw, 0, 8, str(p), cols=8, scale=1)
    assert tiles.import_tiles(str(p)) == raw


def test_palette_words():
    for i, lvl in enumerate(palette.VDP_LEVELS):
        w = (i << 9) | (i << 5) | (i << 1)
        assert palette.word_to_rgb(w) == (lvl, lvl, lvl)
        assert palette.rgb_to_word((lvl, lvl, lvl)) == w
    assert palette.looks_like_palette(b"\x0e\xee" * 16, 0)
    assert not palette.looks_like_palette(b"\x0f\xff" * 16, 0)


def test_pal_file_roundtrip():
    words = b"".join(struct.pack(">H", (i << 9) | (i << 1)) for i in range(8)) * 8
    txt = palette.format_pal(words, ["test"])
    pals = palette.parse_pal(txt)
    assert len(pals) == 4 and pals[0][3] == palette.word_to_rgb((3 << 9) | (3 << 1))


def test_gpgx_cram_unpack():
    # packed BBBGGGRRR = 0b111_000_111 (0x1C7) -> ----BBB-GGG-RRR- = 0x0E0E (LE in the dump)
    dump = struct.pack("<H", 0x1C7)
    assert palette.gpgx_cram_to_words(dump) == b"\x0e\x0e"


def test_gray16_has_16_entries():
    assert len(tiles.GRAY16) == 16 and os.environ is not None
