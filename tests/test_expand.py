"""rom.build_size: a build larger than the base ROM, and RLE records in the IPS."""

from __future__ import annotations

import pytest
import yaml

from ga3 import pipeline as pl
from ga3 import rom_map
from ga3.rom import apply_ips, make_ips

from .conftest import SYNTH_SIZE

GROWN = 0x20000  # 128 KiB: the smallest build_size the map accepts


def _parse(rom: dict, segments=()) -> rom_map.RomMap:
    return rom_map.parse({"rom": rom, "segments": list(segments)})


def test_build_size_is_checked():
    rm = _parse({"size": 0x100000, "build_size": 0x200000})
    assert (rm.size, rm.image_size) == (0x100000, 0x200000)
    assert rm.segments[-1].end == 0x200000  # the gap up to the new end is covered
    assert _parse({"size": 0x100000}).image_size == 0x100000
    for bad in (0x80000, 0x210000, 0x800000):
        with pytest.raises(rom_map.RomMapError, match="build_size"):
            _parse({"size": 0x100000, "build_size": bad})
    with pytest.raises(rom_map.RomMapError, match="extends past the image"):
        _parse({"size": 0x100}, [{"name": "x", "start": 0, "end": 0x200, "type": "free",
                                  "fill": 0}])  # fmt: skip


def test_synthetic_build_expands_and_the_ips_stays_small(synthetic_project):
    s = synthetic_project
    doc = yaml.safe_load((s.root / pl.MAP_FILE).read_text(encoding="utf-8"))
    doc["rom"]["build_size"] = GROWN
    doc["segments"].append(
        {"name": "free_new", "start": SYNTH_SIZE, "end": GROWN, "type": "free", "fill": 0xFF}
    )
    (s.root / pl.MAP_FILE).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    s.project = pl.open_project(s.root)
    pl.extract_all(s.project, s.rom, log=lambda *_: None)
    assert pl.check_map(s.project, s.rom) == []  # the base dump keeps its size and sha1

    built = pl.build(s.project, s.rom, log=lambda *_: None)
    data = bytes(built.data)
    assert len(data) == GROWN
    assert data[SYNTH_SIZE:] == b"\xff" * (GROWN - SYNTH_SIZE)
    assert built.rom_bounds() == (0, GROWN - 1)  # the header's ROM end follows
    assert built.stored_checksum() == built.compute_checksum()

    ips = s.project.build_ips.read_bytes()
    assert apply_ips(s.image, ips) == data
    assert len(ips) < 200  # the FF expansion went into RLE records, not into the patch


def test_ips_rle_records_round_trip():
    base = bytes(range(256)) * 64
    new = bytearray(base)
    new[100:400] = b"\x00" * 300  # a long run -> RLE
    new[1000:1010] = b"\x11" * 10  # a short run -> plain record
    new += b"\xff" * 70000  # an expansion longer than one record can hold
    ips = make_ips(base, bytes(new))
    assert apply_ips(base, ips) == bytes(new)
    assert len(ips) < 100
    assert b"\x00\x00\xff\xff\xff" in ips  # an RLE record of the maximum run, 0xFF
