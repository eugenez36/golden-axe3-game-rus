# Text format

*Russian original with the discovery story: `ru/journal.md`, «Как устроен текст».*

## Encoding

Text is stored as plain bytes, one per glyph, and the font is uploaded to VRAM
so that **tile index == text byte** (byte `0x20` is tile 0 of the font block).
The NEWGAME translators put Cyrillic onto the Latin positions:

```text
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
  separate glyphs for those two digits. `encode()` maps each digit and its
  letter to the same byte.
- Ж (`0x26`) and ж (`0x3B`) are distinct upper- and lower-case glyphs; no
  byte of the table shares its character with another. The reverse table keeps
  the first byte for a character, so if a glyph ever got a second byte,
  `decode_lossless()` would export the other one as `{XX}` and the file would
  still round-trip exactly. `{XX}` must be two hex digits.
- `0x29` is lower-case «ю» and `0x50` upper-case «Ю» (seen in-game: «МЕНЮ» on
  the options screen is `0x50`). Earlier versions of the table had the two labels
  swapped, so correct words read as «следуЮщий» in the text files.
  `test_letter_case_matches_glyph_height` now checks every letter's case
  against its drawing. `0x71` is «й» (the «и» glyph plus a breve).
- `0x4F` Ъ, `0x51` Ё, `0x3C` ё, `0x2A` `(`, `0x2B` `)` and `0x40` Latin `V`
  (for the version in the main menu) were drawn by this project. The original
  translation did not have them. Lower-case `v` encodes to the same byte as
  `V`. The text uses «ё» wherever it belongs (`docs/ru/proofreading.md`).
  Because `0x3C` and `0x40` are now printable, a few runs of binary data
  inside the text segments read as slightly longer "strings" on a fresh
  `ga3 extract`; the committed text files keep the old records, which are
  equally valid.
- Tables that mix control bytes and text, such as the options screen layout
  (`01512C`: column, row, text, `FF` per label), are kept as one record with
  the control bytes written as `{XX}`, so a label can grow at a neighbour's
  expense without moving anything else.

## Strings files (`assets/text/*.txt`)

One file per `text` segment of `rom_map.yml`, plus one per code segment that
carries strings (`strings:` in the map):

| Segment              | File              | Contents                                                 |
|----------------------|-------------------|----------------------------------------------------------|
| `text_menu`          | `menu.txt`        | title line, options screen layout                        |
| `menu_items` (patch) | `menu_items.txt`  | main-menu items, 4 × 8 characters                        |
| `code_main_b`        | `code_main_b.txt` | `1Р` `2Р` `КОМ`, `ПАУЗА`                                 |
| `code_main_d`        | `code_main_d.txt` | difficulty, button roles, `ИГРОК 2: СТАРТ`, score labels |
| `text_stages`        | `stages.txt`      | stage names, 12 × 20 characters, centred                 |
| `code_main_e`        | `code_main_e.txt` | `МАРШРУТ`, `ТЫ ПОГИБ`                                    |
| `text_ending`        | `ending.txt`      | ending screens                                           |
| `text_dialogue`      | `dialogue.txt`    | NPC dialogue, credits                                    |
| `text_misc`          | `misc.txt`        | assorted; several records are printable garbage          |

Format:

```text
# comment
HEXOFFSET:DECLENGTH | text
0179F3:24 | Наши воины (Гена и Женя)
```

Edit only the text right of `|`. Rules enforced by `ga3 build`:

1. every character must exist in the table (or be written as `{XX}`),
2. the encoded string may not be longer than `DECLENGTH`,
3. the record must lie inside its segment.

Shorter strings are padded with spaces (`0x20`). The records of a `text`
segment first came from a scan for runs of printable bytes, so many capture
data that happens to be printable. Real text is declared in the map:

- `prose: [[start, end], ...]` on a `text` segment lists where the game's text
  lives; records of real text were narrowed to the exact string (a record must
  never cover code bytes such as `4E 75`, `rts`, which decode as «Ег»).
- `strings: [[offset, length], ...]` with `strings_path` on a `code`/`data`
  segment declares strings embedded in code, each proven by the `lea` that
  loads it and the loop that draws it. The build writes exactly those spans and
  refuses records the map does not declare.

The English texts are SEGA's licence and region-lock messages in plain ASCII
(`0136BA`, `013DD0`). They are drawn with another font, are standard SEGA
wording and are not edited.

## Checking text

- `ga3 text verify` — every strings file against the table and its segment.
- `ga3 text lint` — mechanical checks of the prose only: a capital inside a
  word, «Э» (byte `0x22`) where a quotation mark was meant, double spaces, a
  space before punctuation, no space after it. Findings kept on purpose are
  listed per segment in `lint_allow: {0xOFFSET: [rule, ...]}`. Spelling and
  wording remain a human review.
- `ga3 text preview [--changed] [-o DIR]` — renders the prose with the current
  font art, one PNG per strings file, for text that is hard to reach in the
  emulator (the ending, duel results).
- `ga3 text export` re-extracts every strings file **from the ROM** and so
  discards the translation's edits; it is for a fresh start only.

## Structure of the ending block

`0179F2–017AF3`, loaded by `move.l #$179F2` at `0179E4`. Each screen is:

```text
<indent byte> <line 1> FE <indent byte> <line 2> FF
```

`FE` separates the two lines of a screen, `FF` ends the screen. (The journal
originally described these the other way round; the observed layout is above.)
Lines are packed tight: `0179F3` occupies exactly its 24 bytes and `FE`
follows immediately. The translator credit lives at `0179F3` (`ending.txt`); a
15-space string at `017AE3` is the other slot with room for a line without
moving anything.

## Growing text

Not possible in place. Of the 914 free bytes in three holes (`0116B6`,
`05AEAA`, `05B30A`) only 28 are left: the patches hold the rest (see
[patches.md](patches.md)). A probable 170-byte filler at `01B6D6` is not yet
verified.
Relocating a string means finding and rewriting its pointer; no pointer table
has been mapped yet. Room for relocated text exists: the build is expanded to
2 MiB (`rom.build_size`), `100000–1FFFFF` is free.
