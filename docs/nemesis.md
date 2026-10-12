# Nemesis compression

*Russian original with the derivation: `ru/journal.md`, «Как устроена графика».*

Nemesis is SEGA's in-house tile compressor. This game's decoder sits at
`0122FC` (`NemDec`, into the VDP port) and `01230E` (`NemDecToRAM`);
`src/ga3/nemesis.py` was written from that disassembly and verified against a
VRAM dump: the decoded font matches all 3072 bytes the game uploads.

## Format

```text
word    header: bit 15 = XOR mode, bits 0..14 = tile count
...     code table, terminated by FF
...     bit stream, MSB first
```

The code table lists, per pixel value (descriptor `>= 80`, low nibble = pixel),
pairs of (info byte, code byte); info = run length − 1 in bits 4..6 and code
length in bits 0..3. The stream is a Huffman code over (pixel, run) symbols.
A six-ones prefix (`peek(8) >= FC`) means "7 literal bits follow" (3 bits of
run, 4 bits of pixel), so the code space is 252 of 256 entries. In XOR mode each
output row is the accumulator XORed with the previous row.

## The 14 blocks in this ROM

| Segment      | Tiles | XOR | Exact size | Pad | Ours      |
|--------------|-------|-----|------------|-----|-----------|
| `nem_013E76` | 50    | no  | 413        | —   | 375       |
| `nem_01B780` | 120   | yes | 1568       | 0   | 1563      |
| `nem_01BDA0` | 119   | yes | 1770       | 0   | 1759      |
| `nem_01C48A` | 120   | yes | 2112       | 2   | 2085      |
| `nem_01CCCC` | 81    | no  | 1034       | 0   | 1023      |
| `nem_01D0D6` | 81    | no  | 721        | 1   | 715       |
| `nem_01D3A8` | 31    | yes | 425        | 1   | 412       |
| `nem_01D552` | 21    | yes | 384        | 0   | 370       |
| `nem_01D6D2` | 40    | yes | 396        | 0   | 393       |
| `font`       | 96    | no  | 840        | —   | 808       |
| `nem_01DBAC` | 20    | no  | 361        | 1   | 353       |
| `nem_01DD16` | 78    | yes | 1369       | —   | 1342      |
| `nem_01E29A` | 18    | yes | 322        | —   | 318       |
| `nem_0295EE` | 208   | no  | 2330       | —   | 2264      |
| **total**    |       |     | **14045**  |     | **13780** |

"Exact size" is what `ga3 nemesis size` reports: the bytes the decoder actually
consumes. (The earlier reader-position estimate was one byte short on 12
blocks; the journal has since been recalculated with `ga3 nemesis size`.) "Pad" is the base ROM's zero
word-alignment after the block; the map's `end` includes it. The twelve blocks
from `01B780` lie nearly back to back: the six bytes after the font
(`44 18 FD 63 E8 00`) are data, not padding, and 43 unidentified bytes sit
between `nem_01DD16` and `nem_01E29A`.

## Why the encoder matches SEGA's

The first version lost by about 400 bytes. Three changes closed the gap:

1. **Rare symbols are cheaper inline.** A table entry costs 2 bytes plus
   `f × len` stream bits; inline costs 13 bits per occurrence and no table
   space. Keep a symbol in the table only if `f × (13 − len) ≥ 16`; below that
   it goes inline. On XOR blocks SEGA's packer keeps 56 table symbols where the
   naive approach kept a hundred — nearly 100 bytes.
2. **Package-merge for code lengths.** Plain Huffman produces codes longer than
   8 bits, which the format cannot store; package-merge solves the depth-limited
   problem exactly.
3. **The four reserved entries** (`FC..FF`) are modelled as four zero-weight
   phantom symbols inside package-merge instead of lengthening codes afterwards.
   That alone saved 88 bytes.

The cut of long runs (12 identical pixels as 8+4 or 6+6) is refined by dynamic
programming once the symbol prices are known, and each strategy runs twice.
`compress()` always verifies itself by decoding. Optimality is not proven; on
every block of this ROM the result is smaller than the original.

## Consequence for the build

Because our output is smaller, recompressing an unchanged block would change the
image. `ga3 build` therefore writes the committed `.nem` verbatim while its
decoded tiles are unchanged and recompresses only edited blocks
(`src/ga3/assets/nemesis_asset.py`). `compress(slack=False)` drops the two
spare bytes the writer normally appends for the reader's 16-bit look-ahead;
inside a ROM the next block provides them.
