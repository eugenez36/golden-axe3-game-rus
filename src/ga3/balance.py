"""Gameplay parameters edited by name rather than by byte.

Everything here was found experimentally: a watchpoint on the player's HP in
Work RAM, then the disassembler at the address that writes it::

    00E482  moveq   #$0, d0
    00E484  move.b  $144(a0), d0        ; character index
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
Actor structure: +0x142 current HP, +0x144 character index (0..3).
"""

from __future__ import annotations

from pathlib import Path

import yaml

RAM_HP_P1 = 0xFFC8E6
ACTOR_HP = 0x142
ACTOR_CHAR_INDEX = 0x144
HUD_MAX = 0x36  # the HUD bar draws one pixel per HP and is ~54 px wide


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


def validate_hp(values: list[int]) -> list[str]:
    warnings = []
    for i, v in enumerate(values):
        if not 1 <= v <= 0xFF:
            raise ValueError(f"HP {v} (slot {i}) is outside 1..255")
        if v > HUD_MAX:
            warnings.append(
                f"slot {i}: HP {v} exceeds the HUD bar width (~{HUD_MAX}); the excess is invisible"
            )
    return warnings
