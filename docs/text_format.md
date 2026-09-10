# Text format

*Russian original with the discovery story: `ru/journal.md`, «Как устроен текст».*

## Encoding

Text is stored as plain bytes, one per glyph, and the font is uploaded to VRAM
so that **tile index == text byte** (byte `0x20` is tile 0 of the font block).
The NEWGAME translators put Cyrillic onto the Latin positions:

```
ИГРОК  = 44 55 48 30 52    (the bytes read "DUH0R" in ASCII)
ВДВОЕМ = 42 4C 42 30 4E 4D
ОПЦИИ  = 30 47 57 44 44
```

The full table is `src/ga3/table.py`; `assets/text/encoding.tbl` is the same
table in Thingy format for WindHex, Atlas and similar tools. It was read off the
game, not guessed: capitals from the menu tilemap, lower case from the first
stage's dialogue tilemap (`docs/images/menu_main.png`, `dialogue.png`).

Pitfalls:

- Digits `0` and `3` are the same glyphs as «О» and «З»; the font has no
  separate digits. `encode()` maps both characters to the same byte.
- Some glyphs are duplicated («ж» is `0x26` and `0x3B`). Bytes that would not
  survive a round trip are exported as `{XX}` so the file stays exact.
- `0x71` is «й» (the «и» glyph plus a breve) and `0x50` is «ю»; at 8×8 they
  are easy to confuse, which produces «магическию» instead of «магический».
- `0x4F` Ъ, `0x51` Ё, `0x2A` `(` and `0x2B` `)` were drawn by this project.
  The original translation did not have them.

## Strings files (`assets/text/*.txt`)

One file per `text` segment of `rom_map.yml`:

| Segment | File | Contents |
|---|---|---|
| `text_menu` | `menu.txt` | menu and options labels |
| `text_stages` | `stages.txt` | stage name list |
| `text_ending` | `ending.txt` | ending screens |
| `text_dialogue` | `dialogue.txt` | NPC dialogue, credits |
| `text_misc` | `misc.txt` | assorted; several records are printable garbage |

Format:

```
# comment
HEXOFFSET:DECLENGTH | text
0179F3:24 | Наши воины (Гена и Женя)
```

Edit only the text right of `|`. Rules enforced by `ga3 build`:

1. every character must exist in the table (or be written as `{XX}`),
2. the encoded string may not be longer than `DECLENGTH`,
3. the record must lie inside its segment.

Shorter strings are padded with spaces (`0x20`). The records come from a scan
for runs of printable bytes, so a few capture neighbouring data bytes that
happen to be printable — edit the meaningful part only.

## Structure of the ending block

`0179F2–017AF3`, loaded by `move.l #$179F2` at `0179E4`. Each screen is:

```
<indent byte> <line 1> FE <indent byte> <line 2> FF
```

`FE` separates the two lines of a screen, `FF` ends the screen. (The journal
originally described these the other way round; the observed layout is above.)
Lines are packed tight: `0179F3` occupies exactly its 24 bytes and `FE`
follows immediately. A 15-space string at `017AE3` is the one place with room
for a translator's credit without moving anything.

## Growing text

Not possible in place. Free space is 914 bytes in three holes
(`0116B6`, `05AEAA`, `05B30A`) plus a probable 170-byte filler at `01B6D6`.
Relocating a string means finding and rewriting its pointer; no pointer table
has been mapped yet. `Rom.expand()` to 2 MiB exists for when that day comes.
