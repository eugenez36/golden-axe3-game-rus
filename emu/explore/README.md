# emu/explore — one-off exploration scripts

These are the runs that found the addresses recorded in `rom_map.yml`. They are
kept for provenance, not as regression checks (`emu/scenes/` is for that), and
they write under `build/shots/explore/` and `build/dumps/explore/`.

| Script | What it found |
|---|---|
| `dmalog.txt` | every DMA transfer with its source: CRAM always comes from Work RAM; three uncompressed ROM→VRAM uploads (`00084A`, `01E84A`, `04ADBE`) |
| `nemdec.txt` | breakpoints on `NemDec` (0122FC) / `NemDecToRAM` (01230E): register dumps give the source offsets of all 14 Nemesis blocks |
| `fontvram.txt` | `vwatch AF00 B80`: the font's DMA source is `01D85E` |
| `fontsrc.txt` | `watch FFE84A 200`: how the font is staged in Work RAM |
| `hpwatch.txt` | `watch FFC8E6 2`: the writer of player 1's HP is `00E48C` |
| `hp.txt` | 26 Work RAM dumps + screenshots for `ga3 ramsearch corr` (HP bar correlation r = 1.0) |
| `enter.txt` | attract-mode walk into stage 1 with VRAM/CRAM snapshots (`stage1*.pal`) |
| `survey.txt`, `survey2.txt` | blind screenshot sweeps of the first minute |

Removed on purpose: `fontdma.txt` (identical to `fontvram.txt`), `hptest.txt`
(produced no output), `menu_test.txt` and `letters.txt` (folded into
`emu/scenes/menu_verify.txt` and `emu/scenes/dialogue_pages.txt`).
