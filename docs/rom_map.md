# ROM map

Generated from `rom_map.yml` by `ga3 assets refresh`. Do not edit by hand.

Image: **Golden Axe 3 (RUS) — NEWGAME 2003**, 1048576 bytes, sha1 `e9538c0542b4a05050f5b68d279cddb06559ae20`,
header checksum `9BB5`, entry point `0FFA20`.

## Coverage

| Type | Bytes | Share |
|---|---|---|
| unknown | 533485 | 50.9% |
| tiles4bpp | 360448 | 34.4% |
| code | 111060 | 10.6% |
| pcm | 14880 | 1.4% |
| nemesis | 14050 | 1.3% |
| text | 13217 | 1.3% |
| free | 914 | 0.1% |
| header | 512 | 0.0% |
| data | 6 | 0.0% |
| table | 4 | 0.0% |

## Segments

| Range | Type | Segment | Asset | Notes |
|---|---|---|---|---|
| `000000–000100` | header | vectors | `header/vectors.yml` | mostly FFFFFFFF; code squeezed into unused vectors from 0x40 |
| `000100–000200` | header | header | `header/header.yml` |  |
| `000200–000284` | code | dispatcher | `code/dispatcher.m68k` | 33 long pointers, the main dispatcher |
| `000284–00E492` | code | code_boot | `code/code_boot.m68k` |  |
| `00E492–00E496` | table | hp_table | `data/hp_table.yml` | format u8; start and maximum HP of the four playable characters; slot->character order still to be proven; *evidence: watch FFC8E6 -> writer 00E48C; disasm 00E484 move.b $e492(pc,d0.w),d0* |
| `00E496–0116B6` | code | code_main_a | `code/code_main_a.m68k` | includes the healing cap at 00E49C and HP pair update at 010544 |
| `0116B6–011800` | free | free_0116B6 |  | filled with 0xFF; 330 bytes |
| `011800–013E76` | code | code_main_b | `code/code_main_b.m68k` | NemDec 0122FC, NemDecToRAM 01230E, code table builder 0123B2 |
| `013E76–014013` | nemesis | nem_013E76 | `gfx/nemesis/nem_013E76.nem` | 50 tiles |
| `014013–014E00` | code | code_main_c | `code/code_main_c.m68k` |  |
| `014E00–0151A0` | text | text_menu | `text/menu.txt` | menu and options strings embedded in menu data |
| `0151A0–016C00` | code | code_main_d | `code/code_main_d.m68k` |  |
| `016C00–016E00` | text | text_stages | `text/stages.txt` | stage name list |
| `016E00–0179F2` | code | code_main_e | `code/code_main_e.m68k` | 0179E4 move.l #$179F2 loads the ending text block |
| `0179F2–017AF3` | text | text_ending | `text/ending.txt` | ending screens: indent byte, text, FE between the two lines of a screen, FF ends a screen; 15-space slot at 017AE3; *evidence: disasm 0179E4; journal §Куда вписать титр переводчика* |
| `017AF3–01B780` | code | code_main_f | `code/code_main_f.m68k` | 01B6D6-01B780 is 170 bytes of FF, probably alignment padding (unverified free space) |
| `01B780–01BDA0` | nemesis | nem_01B780 | `gfx/nemesis/nem_01B780.nem` | 120 tiles, XOR |
| `01BDA0–01C48A` | nemesis | nem_01BDA0 | `gfx/nemesis/nem_01BDA0.nem` | 119 tiles, XOR |
| `01C48A–01CCCC` | nemesis | nem_01C48A | `gfx/nemesis/nem_01C48A.nem` | 120 tiles, XOR; 2 bytes of zero padding |
| `01CCCC–01D0D6` | nemesis | nem_01CCCC | `gfx/nemesis/nem_01CCCC.nem` | 81 tiles |
| `01D0D6–01D3A8` | nemesis | nem_01D0D6 | `gfx/nemesis/nem_01D0D6.nem` | 81 tiles; 1 byte of zero padding |
| `01D3A8–01D552` | nemesis | nem_01D3A8 | `gfx/nemesis/nem_01D3A8.nem` | 31 tiles, XOR; 1 byte of zero padding |
| `01D552–01D6D2` | nemesis | nem_01D552 | `gfx/nemesis/nem_01D552.nem` | 21 tiles, XOR |
| `01D6D2–01D85E` | nemesis | nem_01D6D2 | `gfx/nemesis/nem_01D6D2.nem` | 40 tiles, XOR |
| `01D85E–01DBA6` | nemesis | font | `gfx/font/font.txt` | 96 tiles; format font_art; 96 glyphs; text byte == tile index; slot is exactly 840 bytes; *evidence: vwatch AF00 B80 -> dma_src 01D85E; decoded block == VRAM dump, 3072/3072 bytes* |
| `01DBA6–01DBAC` | data | unk_font_tail | `code/unk_font_tail.m68k` | 6 bytes 44 18 FD 63 E8 00 between the font and the next block; not padding |
| `01DBAC–01DD16` | nemesis | nem_01DBAC | `gfx/nemesis/nem_01DBAC.nem` | 20 tiles; 1 byte of zero padding |
| `01DD16–01E26F` | nemesis | nem_01DD16 | `gfx/nemesis/nem_01DD16.nem` | 78 tiles, XOR |
| `01E26F–01E29A` | unknown | unk_01E26F |  |  |
| `01E29A–01E3DC` | nemesis | nem_01E29A | `gfx/nemesis/nem_01E29A.nem` | 18 tiles, XOR |
| `01E3DC–0295EE` | unknown | unk_01E3DC |  |  |
| `0295EE–029F08` | nemesis | nem_0295EE | `gfx/nemesis/nem_0295EE.nem` | 208 tiles |
| `029F08–05AEAA` | unknown | unk_029F08 |  |  |
| `05AEAA–05AFCE` | free | free_05AEAA |  | filled with 0x00; 292 bytes |
| `05AFCE–05B30A` | unknown | unk_05AFCE |  |  |
| `05B30A–05B42E` | free | free_05B30A |  | filled with 0x00; 292 bytes |
| `05B42E–080000` | unknown | unk_05B42E |  |  |
| `080000–0D8000` | tiles4bpp | art_main | `gfx/tiles` | 11520 uncompressed tiles in 23 sheets; palette unknown, rendered with a grey ramp |
| `0D8000–0E9B00` | unknown | unk_0D8000 |  |  |
| `0E9B00–0EC300` | text | text_dialogue | `text/dialogue.txt` | NPC dialogue, credits and ending text |
| `0EC300–0FB000` | unknown | unk_0EC300 |  |  |
| `0FB000–0FB500` | text | text_misc | `text/misc.txt` | misc strings; several records are printable garbage — edit with care |
| `0FB500–0FC000` | unknown | unk_0FB500 |  |  |
| `0FC000–0FFA20` | pcm | pcm | `sound/pcm/samples.pcm` | PCM sample data; sample table and rate unknown |
| `0FFA20–100000` | code | entry_stub | `code/entry_stub.m68k` | the translators' relocated entry point; *evidence: reset vector at 0x4 = 000FFA20* |

## Palettes (emulator CRAM captures, not build inputs)

- `title` — `palettes/title.pal` — emu/scenes/title.txt, title screen
- `title_menu` — `palettes/title_menu.pal` — emu/scenes/title.txt, menu after START
- `title_newgame` — `palettes/title_newgame.pal` — emu/scenes/title.txt, second menu state
- `stage1_intro` — `palettes/stage1_intro.pal` — emu/explore/enter.txt, e3 (attract walk)
- `stage1` — `palettes/stage1.pal` — emu/explore/enter.txt, e4
- `stage1_dialogue` — `palettes/stage1_dialogue.pal` — emu/scenes/dialogue.txt, first NPC dialogue
