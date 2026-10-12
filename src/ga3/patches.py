"""Hand-assembled 68000 routines that the build adds to the image.

No assembler is involved: each routine is a short, fixed instruction sequence
whose encodings are spelled out next to the bytes. The routines know formats,
never addresses -- every address arrives from a ``patch`` segment in
``rom_map.yml`` (see ``ga3.assets.patch_asset``).
"""

from __future__ import annotations

import struct

from . import __version__, table


def jmp_abs(target: int) -> bytes:
    """``jmp target.l`` -- six bytes, the size of the instruction pair a hook replaces."""
    return struct.pack(">HI", 0x4EF9, target)


def vdp_write_vram(addr: int) -> int:
    """VDP control longword that starts a VRAM write at ``addr``.

    CD1-CD0 = 01 (VRAM write), A13-A0 in the high word, A15-A14 in the low
    word -- what the game's own helper at the menu code computes.
    """
    if not 0 <= addr < 0x10000 or addr & 1:
        raise ValueError(f"VRAM address 0x{addr:X} must be even and below 0x10000")
    return 0x40000000 | ((addr & 0x3FFF) << 16) | (addr >> 14)


def version_text(version: str = __version__) -> str:
    """What the main menu shows: ``V 0.3.6``."""
    return f"V {version}"


def menu_version(vram_end: int, attr: int, return_to: int, text: str) -> bytes:
    """Draw ``text`` right-aligned to ``vram_end`` on plane A, then resume the menu.

    Entered by ``jmp`` from the menu's last instruction pair, ``moveq #0,d1;
    bra.w return_to``, which it re-executes at the end. Like the menu's own
    item loop it expects ``a6`` = VDP control port and clobbers d0, d2, d7, a0.
    Each character is one tile word, ``attr + byte`` (tile index == text byte).
    The routine is position-independent.
    """
    glyphs = table.encode(text)
    if not 1 <= len(glyphs) <= 128:
        raise ValueError(f"menu version text must be 1..128 characters, got {len(glyphs)}")
    head = struct.pack(">HI", 0x2CBC, vdp_write_vram(vram_end - 2 * len(glyphs)))
    tail = b"".join(
        [
            struct.pack(">HH", 0x323C, attr),  # move.w #attr,d1
            struct.pack(">BB", 0x7E, len(glyphs) - 1),  # moveq #n-1,d7
            bytes.fromhex("3401"),  # loop: move.w d1,d2
            bytes.fromhex("D418"),  # add.b (a0)+,d2
            bytes.fromhex("3D42FFFC"),  # move.w d2,-4(a6)  (VDP data port)
            bytes.fromhex("51CFFFF6"),  # dbra d7,loop
            bytes.fromhex("7200"),  # moveq #0,d1  (the replaced instruction)
            jmp_abs(return_to),  # jmp return_to.l  (stands in for the replaced bra.w)
        ]
    )
    # lea text(pc),a0 follows `head`; its displacement counts from its extension word.
    lea = struct.pack(">Hh", 0x41FA, 2 + len(tail))
    return head + lea + tail + glyphs
