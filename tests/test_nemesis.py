import pytest

from ga3 import nemesis
from ga3.tiles import tile_encode


def test_fixture_roundtrip(fixtures):
    raw = (fixtures / "tiny.4bpp").read_bytes()
    nem = (fixtures / "tiny.nem").read_bytes()
    assert nemesis.decompress_blob(nem) == raw
    assert nemesis.info(nem, 0)["tiles"] == 4


def test_block_size_is_exact(fixtures):
    nem = (fixtures / "tiny.nem").read_bytes()
    # surround with junk: the size must not depend on what follows the block
    data = b"\xaa" * 7 + nem + b"\x55" * 9
    assert nemesis.block_size(data, 7) == len(nem)


@pytest.mark.parametrize("xor", [False, True, None])
def test_compress_roundtrip_modes(fixtures, xor):
    raw = (fixtures / "tiny.4bpp").read_bytes()
    blob = nemesis.compress(raw, xor_mode=xor)
    assert nemesis.decompress(blob, 0) == raw
    assert blob.endswith(b"\0\0")
    assert nemesis.strip_slack(blob) == blob[:-2]


def test_compress_without_slack_decodes_when_followed_by_data(fixtures):
    raw = (fixtures / "tiny.4bpp").read_bytes()
    blob = nemesis.compress(raw, slack=False)
    assert nemesis.decompress(blob + b"\xff\xff\xff", 0) == raw
    assert nemesis.block_size(blob + b"\xff\xff\xff", 0) == len(blob)


def test_inline_symbols_are_used_for_noise():
    # 16 distinct nibbles per row => 64 rare symbols; the packer must go inline
    rows = [[(x * 7 + y * 3) % 16 for x in range(8)] for y in range(8)]
    raw = tile_encode(rows) * 3
    blob = nemesis.compress(raw, xor_mode=False, slack=False)
    assert nemesis.decompress_blob(blob) == raw


def test_solid_tile_is_tiny():
    raw = tile_encode([[0xC] * 8 for _ in range(8)]) * 8
    blob = nemesis.compress(raw, slack=False)
    assert len(blob) < 16


def test_rejects_bad_sizes():
    with pytest.raises(ValueError):
        nemesis.compress(b"\0" * 31)
    with pytest.raises(ValueError):
        nemesis.compress(b"")


def test_decompress_blob_matches_fixture(fixtures):
    raw = (fixtures / "tiny.4bpp").read_bytes()
    nem = (fixtures / "tiny.nem").read_bytes()
    assert nemesis.decompress_blob(nem) == raw
    assert nemesis.decompress_blob(bytearray(nem)) == raw


@pytest.mark.parametrize("blob", [b"", b"\x00", b"\x00\x04", b"\x00\x04\x80\x01"])
def test_truncated_block_raises_valueerror(blob):
    with pytest.raises(ValueError):
        nemesis.decompress(blob, 0)
    with pytest.raises(ValueError):
        nemesis.block_size(blob, 0)
    if len(blob) < 2:
        with pytest.raises(ValueError, match="no Nemesis header"):
            nemesis.info(blob, 0)
