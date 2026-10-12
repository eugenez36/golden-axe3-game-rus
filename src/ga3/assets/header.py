"""Vector table (0x000-0x0FF) and cartridge header (0x100-0x1FF) as YAML.

Vectors are 64 big-endian longs. Header text fields are stored as quoted
strings of their exact width when they are pure printable ASCII, otherwise
as hex. ``checksum: auto`` and ``rom_end: auto`` let the pipeline compute the
values after every other segment is in place.
"""

from __future__ import annotations

import struct
from pathlib import Path

import yaml

from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths, write_text

VECTOR_NAMES = {
    0: "reset_sp",
    1: "reset_pc",
    2: "bus_error",
    3: "address_error",
    4: "illegal_instruction",
    5: "zero_divide",
    6: "chk_instruction",
    7: "trapv_instruction",
    8: "privilege_violation",
    9: "trace",
    10: "line_1010_emulator",
    11: "line_1111_emulator",
    24: "spurious_interrupt",
    25: "level_1_interrupt",
    26: "level_2_interrupt_ext",
    27: "level_3_interrupt",
    28: "level_4_interrupt_hblank",
    29: "level_5_interrupt",
    30: "level_6_interrupt_vblank",
    31: "level_7_interrupt",
}
for _t in range(16):
    VECTOR_NAMES[32 + _t] = f"trap_{_t}"

# (key, offset, size, kind)   kind: text | u32 | checksum
HEADER_FIELDS = [
    ("console", 0x100, 16, "text"),
    ("copyright", 0x110, 16, "text"),
    ("domestic_name", 0x120, 48, "text"),
    ("overseas_name", 0x150, 48, "text"),
    ("serial", 0x180, 14, "text"),
    ("checksum", 0x18E, 2, "checksum"),
    ("io_support", 0x190, 16, "text"),
    ("rom_start", 0x1A0, 4, "u32"),
    ("rom_end", 0x1A4, 4, "u32"),
    ("ram_start", 0x1A8, 4, "u32"),
    ("ram_end", 0x1AC, 4, "u32"),
    ("sram_info", 0x1B0, 12, "text"),
    ("modem_info", 0x1BC, 12, "text"),
    ("notes", 0x1C8, 40, "text"),
    ("region", 0x1F0, 16, "text"),
]


class _Hex(int):
    pass


def _hex_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:int", f"0x{int(data):08X}")


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(_Hex, _hex_representer)


def _is_text(b: bytes) -> bool:
    return all(0x20 <= c <= 0x7E for c in b)


class HeaderHandler(Handler):
    committed = True

    def _kind(self, seg: Segment) -> str:
        if seg.start == 0x000 and seg.end == 0x100:
            return "vectors"
        if seg.start == 0x100 and seg.end == 0x200:
            return "header"
        raise BuildError(f"{seg}: header handler expects 000000-000100 or 000100-000200")

    # -- vectors -----------------------------------------------------------

    def _extract_vectors(self, rom: Rom) -> str:
        longs = struct.unpack(">64I", bytes(rom.data[0:0x100]))
        doc = {}
        for i, v in enumerate(longs):
            doc[VECTOR_NAMES.get(i, f"vector_{i:02d}")] = _Hex(v)
        head = (
            "# 68000 vector table, 64 longs. Values are exact ROM contents.\n"
            "# Most entries are 0xFFFFFFFF; the translators moved reset_pc to 0x0FFA20\n"
            "# and squeezed code into unused vectors from 0x40 on, so treat every\n"
            "# value as data, not as an address you may change freely.\n"
        )
        return head + yaml.dump(doc, Dumper=_Dumper, sort_keys=False)

    def _build_vectors(self, rom: Rom, path: Path) -> None:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        values = []
        for i in range(64):
            key = VECTOR_NAMES.get(i, f"vector_{i:02d}")
            if key not in doc:
                raise BuildError(f"vectors: missing {key}")
            v = doc[key]
            if not isinstance(v, int) or not 0 <= v <= 0xFFFFFFFF:
                raise BuildError(f"vectors: {key}={v!r} is not a 32-bit integer")
            values.append(v)
        rom.data[0:0x100] = struct.pack(">64I", *values)

    # -- header ------------------------------------------------------------

    def _extract_header(self, rom: Rom) -> str:
        doc: dict = {}
        for key, off, size, kind in HEADER_FIELDS:
            raw = bytes(rom.data[off : off + size])
            if kind == "checksum":
                doc[key] = "auto"
            elif kind == "u32":
                doc[key] = "auto" if key == "rom_end" else _Hex(struct.unpack(">I", raw)[0])
            elif _is_text(raw):
                doc[key] = raw.decode("ascii")
            else:
                doc[key] = {"hex": raw.hex()}
        head = (
            "# Cartridge header, 0x100-0x1FF. Text fields keep their exact width and\n"
            "# trailing spaces. 'auto' fields (checksum, rom_end) are recomputed by\n"
            "# `ga3 build` after every segment is in place.\n"
        )
        return head + yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=200)

    def _build_header(self, rom: Rom, path: Path) -> None:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, off, size, kind in HEADER_FIELDS:
            if key not in doc:
                raise BuildError(f"header: missing field {key}")
            v = doc[key]
            if kind == "checksum":
                if v != "auto":
                    rom.set_u16(off, int(v))
                continue
            if kind == "u32":
                if v == "auto":
                    continue  # fixed by the pipeline after all segments are placed
                rom.set_u32(off, int(v))
                continue
            if isinstance(v, dict) and "hex" in v:
                raw = bytes.fromhex(v["hex"])
            elif isinstance(v, str):
                raw = v.encode("ascii")
            else:
                raise BuildError(f"header: {key} must be a string or {{hex: ...}}")
            if len(raw) != size:
                raise BuildError(f"header: {key} must be exactly {size} bytes, got {len(raw)}")
            rom.data[off : off + size] = raw

    # -- Handler interface -------------------------------------------------

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        kind = self._kind(seg)
        body = self._extract_vectors(rom) if kind == "vectors" else self._extract_header(rom)
        return [write_text(paths.asset(seg.path), body)]

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        kind = self._kind(seg)
        path = paths.asset(seg.path)
        if not path.exists():
            raise BuildError(f"{seg}: missing {path}")
        if kind == "vectors":
            self._build_vectors(rom, path)
        else:
            self._build_header(rom, path)
        return None
