"""Numbers inside the game's code, edited by name.

Some gameplay values are not in a table but are the operand of an instruction:
``move.b #2,$13c(a0)`` sets the spare lives. Cutting a one-byte segment out of
a code segment would split the instruction (and its listing), so these live
under the top-level ``constants:`` key of ``rom_map.yml`` instead: for each
constant, every instruction that carries it, with the bytes the base ROM holds
there and the offset of the operand inside them.

``extract`` writes the values to the asset file named by ``constants.path``;
``build`` checks each instruction against its base-ROM bytes (a map that
drifted from the code fails the build instead of corrupting it) and writes the
operand; ``check`` compares the map with the base ROM.
"""

from __future__ import annotations

import struct
from pathlib import Path

import yaml

from .assets.base import BuildError, Paths, write_bytes
from .rom import Rom
from .rom_map import Constant, RomMap, Site

PACK = {"u8": ">B", "u16": ">H"}


def _operand(data: bytes | bytearray, c: Constant, site: Site) -> int:
    """The constant as the image ``data`` holds it at ``site``."""
    at = site.at + site.offset
    return struct.unpack(PACK[c.format], bytes(data[at : at + c.width]))[0]


def _base_value(c: Constant, site: Site) -> int:
    """The constant in the base-ROM bytes the map gives for ``site``."""
    return struct.unpack(PACK[c.format], site.expect[site.offset : site.offset + c.width])[0]


def check(rom: Rom, rm: RomMap) -> list[str]:
    """Every site holds its instruction in the base ROM; all sites of a constant agree."""
    problems = []
    for c in rm.constants.values():
        for s in c.sites:
            found = bytes(rom.data[s.at : s.at + len(s.expect)])
            if found != s.expect:
                problems.append(
                    f"constants.{c.name}: 0x{s.at:06X} holds {found.hex(' ')}, "
                    f"expected {s.expect.hex(' ')}"
                )
        if len({_base_value(c, s) for s in c.sites}) > 1:
            problems.append(f"constants.{c.name}: its sites carry different values")
    return problems


def read_values(path: Path) -> dict[str, int]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(doc.get("values") or {})


def write_values(path: Path, values: dict[str, int], rm: RomMap) -> Path:
    lines = [
        "# Gameplay constants: numbers inside the game's code, edited by name.",
        "# Where each one sits is in rom_map.yml (constants:); `ga3 balance` edits this file.",
    ]
    for c in rm.constants.values():
        sites = ", ".join(f"{s.at:06X}" for s in c.sites)
        lines.append(f"# {c.name} ({c.format}, at {sites}): {c.get('note', '')}".rstrip(": "))
    body = yaml.safe_dump({"values": values}, sort_keys=False, allow_unicode=True)
    return write_bytes(path, ("\n".join(lines) + "\n" + body).encode("utf-8"))


def extract(rom: Rom, rm: RomMap, paths: Paths) -> list[Path]:
    if not rm.constants:
        return []
    values = {c.name: _operand(rom.data, c, c.sites[0]) for c in rm.constants.values()}
    return [write_values(paths.asset(rm.constants_path), values, rm)]


def sources(rm: RomMap, paths: Paths) -> list[Path]:
    return [paths.asset(rm.constants_path)] if rm.constants else []


def build(rom: Rom, rm: RomMap, paths: Paths) -> list[str]:
    """Write every constant into its instructions; one note per changed value."""
    if not rm.constants:
        return []
    path = paths.asset(rm.constants_path)
    if not path.exists():
        raise BuildError(f"constants: {path} is missing (run `ga3 extract --only constants`)")
    values = read_values(path)
    notes = []
    for c in rm.constants.values():
        if c.name not in values:
            raise BuildError(f"constants: {path.name} has no value for {c.name!r}")
        value = values[c.name]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= c.limit:
            raise BuildError(f"constants.{c.name}: {value!r} is outside 0..{c.limit} ({c.format})")
        for s in c.sites:
            found = bytes(rom.data[s.at : s.at + len(s.expect)])
            if found != s.expect:
                raise BuildError(
                    f"constants.{c.name}: 0x{s.at:06X} holds {found.hex(' ')}, "
                    f"expected {s.expect.hex(' ')}"
                )
            at = s.at + s.offset
            rom.data[at : at + c.width] = struct.pack(PACK[c.format], value)
        was = _base_value(c, c.sites[0])
        if value != was:
            note = f"constants.{c.name}: {was} -> {value}"
            max_hud = c.get("max_hud")
            if max_hud is not None and value > max_hud:
                note += f"; warning: above what the HUD can draw ({max_hud})"
            notes.append(note)
    return notes
