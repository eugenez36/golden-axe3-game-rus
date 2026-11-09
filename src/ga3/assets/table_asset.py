"""Small numeric tables as YAML (e.g. the HP table at 0x00E492).

Map attributes: ``format`` (u8 | u16 | u32, big-endian), optional ``fields``
(names, one per entry), ``max_hud`` (warn when an *edited* value exceeds
what the HUD can draw; the base ROM's own values are not nagged about),
``range: [lo, hi]`` (refuse a value the game cannot use, e.g. a song ID that
is not in the music index) and ``hex: true`` (write the values as 0x..).
"""

from __future__ import annotations

import struct
from pathlib import Path

import yaml

from ..rom import Rom
from ..rom_map import Segment
from .base import BuildError, Handler, Paths, write_text

WIDTH = {"u8": 1, "u16": 2, "u32": 4}
FMT = {"u8": "B", "u16": "H", "u32": "I"}


def bounds(seg: Segment, width: int) -> tuple[int, int]:
    """The values a table entry may hold: the map's ``range`` or what the format fits."""
    lo, hi = seg.get("range") or (0, (1 << (8 * width)) - 1)
    return int(lo), int(hi)


def dump(fmt: str, values: dict[str, int], hex_values: bool = False) -> str:
    """The YAML body of a table asset; ``hex_values`` writes 0x.. (YAML reads it back as int)."""
    if not hex_values:
        return yaml.safe_dump({"format": fmt, "values": dict(values)}, sort_keys=False)
    digits = 2 * WIDTH[fmt]
    lines = [f"format: {fmt}", "values:"]
    lines += [f"  {k}: 0x{v:0{digits}X}" for k, v in values.items()]
    return "\n".join(lines) + "\n"


class TableHandler(Handler):
    committed = True

    def _layout(self, seg: Segment) -> tuple[str, int, list[str]]:
        fmt = seg.get("format", "u8")
        if fmt not in WIDTH:
            raise BuildError(f"{seg}: unknown table format {fmt!r}")
        width = WIDTH[fmt]
        if seg.size % width:
            raise BuildError(f"{seg}: size {seg.size} is not a multiple of {width}")
        count = seg.size // width
        fields = seg.get("fields") or [f"entry_{i}" for i in range(count)]
        if len(fields) != count:
            raise BuildError(f"{seg}: {len(fields)} field names for {count} entries")
        return fmt, width, list(fields)

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        fmt, _width, fields = self._layout(seg)
        values = struct.unpack(f">{len(fields)}{FMT[fmt]}", bytes(rom.data[seg.start : seg.end]))
        values = dict(zip(fields, values, strict=True))
        header = [
            f"# {seg.name}: {len(fields)} x {fmt}, ROM {seg.start:06X}-{seg.end:06X}",
        ]
        if seg.get("note"):
            header.append(f"# {seg.get('note')}")
        if seg.get("evidence"):
            header.append(f"# evidence: {seg.get('evidence')}")
        body = "\n".join(header) + "\n" + dump(fmt, values, bool(seg.get("hex")))
        return [write_text(paths.asset(seg.path), body)]

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        fmt, width, fields = self._layout(seg)
        path = paths.asset(seg.path)
        if not path.exists():
            raise BuildError(f"{seg}: missing table file {path}")
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if doc.get("format", fmt) != fmt:
            raise BuildError(f"{seg}: file format {doc.get('format')!r} != map format {fmt!r}")
        values = doc.get("values") or {}
        missing = [f for f in fields if f not in values]
        if missing:
            raise BuildError(f"{seg}: missing values for {missing}")
        lo, hi = bounds(seg, width)
        out = []
        for f in fields:
            v = values[f]
            if not isinstance(v, int) or not lo <= v <= hi:
                shown = f"0x{lo:X}..0x{hi:X}" if seg.get("range") else f"{lo}..{hi}"
                raise BuildError(f"{seg}: {f}={v!r} is not an integer in {shown}")
            out.append(v)
        blob = struct.pack(f">{len(out)}{FMT[fmt]}", *out)
        old = bytes(rom.data[seg.start : seg.end])
        self.place(rom, seg, blob, pad=None)
        if blob == old:
            return None
        note = "changed"
        max_hud = seg.get("max_hud")
        if max_hud is not None:
            before = struct.unpack(f">{len(out)}{FMT[fmt]}", old)
            over = [
                f"{f}={v}"
                for f, v, o in zip(fields, out, before, strict=True)
                if v != o and v > max_hud
            ]
            if over:
                note += f"; warning: {', '.join(over)} exceed what the HUD can draw ({max_hud})"
        return note
