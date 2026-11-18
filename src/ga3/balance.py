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


def read_table(path: Path) -> dict[str, int]:
    """The ``values`` of a table asset (``assets/data/*.yml`` of a ``table`` segment)."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(doc.get("values") or {})


def write_table(
    path: Path, values: dict[str, int], fmt: str = "u8", hex_values: bool = False
) -> None:
    """Write new ``values`` into a table asset in the map's ``fmt``, keeping its header comments."""
    from .assets.table_asset import dump

    text = path.read_text(encoding="utf-8")
    header = [ln for ln in text.splitlines() if ln.startswith("#")]
    body = dump(fmt, values, hex_values)
    path.write_text("\n".join(header) + ("\n" if header else "") + body, encoding="utf-8")


read_hp = read_table
write_hp = write_table


def set_table_field(seg, path: Path, field: str, value: int) -> tuple[int, list[str]]:
    """Write one field of a ``table`` segment's asset; the previous value and warnings.

    Raises ValueError for an unknown field or a value the format cannot hold.
    """
    from .assets.base import BuildError
    from .assets.table_asset import TableHandler, check

    try:
        fmt, width, fields = TableHandler()._layout(seg)  # the fields, named or entry_N
    except BuildError as exc:
        raise ValueError(str(exc)) from None
    if field not in fields:
        raise ValueError(f"{seg.name} has no field {field!r}; known: {', '.join(fields)}")
    problem = check(seg, width, field, value)
    if problem:
        raise ValueError(f"{seg.name}.{problem}")
    warnings = []
    max_hud = seg.get("max_hud")
    if max_hud is not None and value > max_hud:
        warnings.append(f"{seg.name}.{field} {value} is more than the HUD can draw ({max_hud})")
    values = read_table(path)
    old = values.get(field)
    values[field] = value
    write_table(path, values, fmt, bool(seg.get("hex")))
    return old, warnings


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
    why = constants.problem(c, value)
    if why:
        raise ValueError(f"{name} {why}")
    warnings = []
    max_hud = c.get("max_hud")
    if max_hud is not None and value > max_hud:
        warnings.append(f"{name} {value} is more than the HUD can draw ({max_hud})")
    values = constants.read_values(path)
    old = values.get(name)
    values[name] = value
    constants.write_values(path, values, rm)
    return old, warnings
