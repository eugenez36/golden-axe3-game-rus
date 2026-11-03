"""Enigma -- SEGA's tilemap compression scheme. Decoder and encoder.

The decoder mirrors the game's own routine:
  0x01252C  EniDec         -- d0 = base attribute, a0 = source, a1 = destination
  0x012482  inline value   -- flag bits, then the tile index
It shares the bit reader with Nemesis (0x012434 / 0x01243E / 0x012452).

Format
------
  byte    packet length: bits in an inline tile index
  byte    flag mask: bit 0 = each inline value carries a V-flip bit (0x1000),
          bit 1 = it carries an H-flip bit (0x0800). Golden Axe III's decoder
          ignores the other bits; priority and palette come from the base.
  word    incrementing value (base is added at start)
  word    common value (base is added at start)
  ...     bit stream, read MSB first, until the end code

Every packet is a mode and a 4-bit count; the mode repeats count+1 times:
  00   the incrementing value, which then grows by one each word
  01   the common value
  100  one inline value, repeated
  101  one inline value, growing by one each word
  110  one inline value, shrinking by one each word
  111  count+1 inline values; count 15 ends the stream

The decoder leaves a0 on the next even address after the stream.
The output has no shape: the caller copies a width x height rectangle.
"""

from __future__ import annotations

import struct
from collections import Counter

from .nemesis import BitWriter

FLAG_V = 0x1000
FLAG_H = 0x0800
TILE_MASK = 0x07FF
MAX_RUN = 16
END_COUNT = 0xF


class _Bits:
    def __init__(self, data: bytes, pos: int):
        self.data = data
        self.bit = pos * 8

    def read(self, n: int) -> int:
        value = 0
        for _ in range(n):
            byte = self.data[self.bit >> 3] if (self.bit >> 3) < len(self.data) else 0
            value = (value << 1) | ((byte >> (7 - (self.bit & 7))) & 1)
            self.bit += 1
        return value

    def end(self) -> int:
        """The address the game leaves in a0: past the last byte touched, made even."""
        end = (self.bit + 7) >> 3
        return end + (end & 1)


def decompress(data: bytes, offset: int, base: int = 0) -> tuple[list[int], int]:
    """Decode one map. Returns (words, size in bytes including the even pad)."""
    packet_len = data[offset]
    mask = data[offset + 1]
    inc, common = struct.unpack_from(">HH", data, offset + 2)
    inc = (inc + base) & 0xFFFF
    common = (common + base) & 0xFFFF
    bits = _Bits(data, offset + 6)
    out: list[int] = []

    def inline() -> int:
        value = base
        if mask & 1 and bits.read(1):
            value |= FLAG_V
        if mask & 2 and bits.read(1):
            value |= FLAG_H
        return (value + bits.read(packet_len)) & 0xFFFF

    while True:
        if bits.read(1) == 0:
            mode = bits.read(1)
            count = bits.read(4)
            for _ in range(count + 1):
                if mode == 0:
                    out.append(inc)
                    inc = (inc + 1) & 0xFFFF
                else:
                    out.append(common)
            continue
        mode = bits.read(2)
        count = bits.read(4)
        if mode == 3:
            if count == END_COUNT:
                return out, bits.end() - offset
            out.extend(inline() for _ in range(count + 1))
            continue
        value = inline()
        step = (0, 1, -1)[mode]
        for _ in range(count + 1):
            out.append(value)
            value = (value + step) & 0xFFFF


# ---------------------------------------------------------------- encoding


def _run(words: list[int], i: int, start: int, step: int) -> int:
    n = 0
    while i + n < len(words) and n < MAX_RUN and words[i + n] == (start + step * n) & 0xFFFF:
        n += 1
    return n


def _stream(words: list[int], packet_len: int, mask: int, inc: int, common: int) -> bytes:
    w = BitWriter()

    def inline(value: int) -> None:
        if mask & 1:
            w.write(1 if value & FLAG_V else 0, 1)
        if mask & 2:
            w.write(1 if value & FLAG_H else 0, 1)
        w.write(value & TILE_MASK, packet_len)

    def starts_run(j: int) -> bool:
        return any(_run(words, j, words[j], step) > 1 for step in (0, 1, -1))

    i = 0
    while i < len(words):
        n = _run(words, i, inc, 1)
        if n:
            w.write(0b00, 2)
            w.write(n - 1, 4)
            inc = (inc + n) & 0xFFFF
            i += n
            continue
        n = _run(words, i, common, 0)
        if n:
            w.write(0b01, 2)
            w.write(n - 1, 4)
            i += n
            continue
        best_mode, best_n = 0b100, 1
        for mode, step in ((0b100, 0), (0b101, 1), (0b110, -1)):
            n = _run(words, i, words[i], step)
            if n > best_n:
                best_mode, best_n = mode, n
        if best_n > 1:
            w.write(best_mode, 3)
            w.write(best_n - 1, 4)
            inline(words[i])
            i += best_n
            continue
        # Literals until something cheaper starts; at most 15 (count 15 ends).
        j = i + 1
        while (
            j < len(words)
            and j - i < END_COUNT
            and words[j] not in (inc, common)
            and not starts_run(j)
        ):
            j += 1
        w.write(0b100 if j - i == 1 else 0b111, 3)
        w.write(j - i - 1, 4)
        for value in words[i:j]:
            inline(value)
        i = j
    w.write(0b111, 3)
    w.write(END_COUNT, 4)
    return w.finish(slack=False)


def compress(words: list[int], base: int = 0) -> bytes:
    """Encode a map whose words are `base` plus tile index and V/H bits.

    Tries the likeliest incrementing start values and keeps the shortest
    result, padded to an even length as the game expects.
    """
    rel = [(word - base) & 0xFFFF for word in words]
    for word in rel:
        if word & ~(FLAG_V | FLAG_H | TILE_MASK):
            word = (word + base) & 0xFFFF
            raise ValueError(f"map word {word:04X}: priority/palette differ from base {base:04X}")
    mask = (1 if any(word & FLAG_V for word in rel) else 0) | (
        2 if any(word & FLAG_H for word in rel) else 0
    )
    packet_len = max(1, max((word & TILE_MASK for word in rel), default=0).bit_length())
    common = Counter(rel).most_common(1)[0][0] if rel else 0
    pairs = Counter(rel[k] for k in range(len(rel) - 1) if rel[k + 1] == (rel[k] + 1) & 0xFFFF)
    starts = [start for start, _ in pairs.most_common(8)] or [0]
    best = b""
    for start in starts:
        blob = struct.pack(">BBHH", packet_len, mask, start, common) + _stream(
            rel, packet_len, mask, start, common
        )
        if not best or len(blob) < len(best):
            best = blob
    return best + b"\x00" * (len(best) & 1)
