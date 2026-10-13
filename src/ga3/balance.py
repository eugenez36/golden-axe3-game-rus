"""Gameplay parameters edited by name rather than by byte.

Everything here was found experimentally: a watchpoint on the player's HP in
Work RAM, then the disassembler at the address that writes it::

    00E482  moveq   #$0, d0
    00E484  move.b  $144(a0), d0        ; max-HP level 0..3
    00E488  move.b  $e492(pc, d0.w), d0 ; pick from the HP table
    00E48C  move.b  d0, $142(a0)        ; store current HP
    00E490  rts
    00E492  33 3b 43 4b                 ; <- the table: 51, 59, 67, 75

The same array caps healing (code at 0x00E49C). The table itself lives in
``assets/data/hp_table.yml`` and is placed by the ``table`` handler; this
module only edits that file.

Work RAM addresses (68000 view), for emulator work only:
  FFC8E6  player 1 current HP (r = 1.0 correlation with the HUD bar length)
  FFC8E7  paired HP byte (updated by code at 0x010544)
Actor structure: +0x142 current HP, +0x144 max-HP level (0..3, raised by
items; every hero starts at 0, so the table is per level, not per hero --
see docs/heroes.md).

The HUD bar draws one pixel per HP and is about 54 px wide; the limit lives
in ``rom_map.yml`` as the segment's ``max_hud`` attribute.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def read_hp(path: Path) -> dict[str, int]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(doc.get("values") or {})


def write_hp(path: Path, values: dict[str, int]) -> None:
    text = path.read_text(encoding="utf-8")
    header = [ln for ln in text.splitlines() if ln.startswith("#")]
    doc = yaml.safe_load(text) or {}
    doc["values"] = dict(values)
    body = yaml.safe_dump(doc, sort_keys=False)
    path.write_text("\n".join(header) + ("\n" if header else "") + body, encoding="utf-8")


def validate_hp(values: list[int], max_hud: int | None = None) -> list[str]:
    """Range-check the values; return warnings for those the HUD cannot show in full."""
    warnings = []
    for i, v in enumerate(values):
        if not 1 <= v <= 0xFF:
            raise ValueError(f"HP {v} (slot {i}) is outside 1..255")
        if max_hud is not None and v > max_hud:
            warnings.append(
                f"slot {i}: HP {v} exceeds the HUD bar width ({max_hud}); the excess is invisible"
            )
    return warnings


def set_constant(rm, path: Path, name: str, value: int) -> tuple[int, list[str]]:
    """Write one gameplay constant (``constants:`` in rom_map.yml) to its asset file.

    Returns the previous value and warnings; raises ValueError for an unknown
    name or a value its format cannot hold.
    """
    from . import constants

    if name not in rm.constants:
        raise ValueError(f"no constant {name!r}; known: {', '.join(rm.constants)}")
    c = rm.constants[name]
    if not 0 <= value <= c.limit:
        raise ValueError(f"{name} {value} is outside 0..{c.limit} ({c.format})")
    warnings = []
    max_hud = c.get("max_hud")
    if max_hud is not None and value > max_hud:
        warnings.append(f"{name} {value} is more than the HUD can draw ({max_hud})")
    values = constants.read_values(path)
    old = values.get(name)
    values[name] = value
    constants.write_values(path, values, rm)
    return old, warnings
