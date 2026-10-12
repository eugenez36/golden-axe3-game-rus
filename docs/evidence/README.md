# docs/evidence — how the addresses were proven

Small artefacts from the reverse-engineering runs, kept so that every entry in
`rom_map.yml` can be traced to something a second person can re-run. Nothing
here is needed to build; the scripts that produced these live in `emu/explore/`.

| File | Produced by | Shows |
|---|---|---|
| `logs/dma_sources.txt` | `emu/explore/dmalog.txt` (distilled from a 500 KB log) | every DMA transfer in the first minute: CRAM is filled only from Work RAM; 13 distinct ROM→VRAM sources outside the tile-art region and the Nemesis blocks (`00084A`, `01E84A`, `04ADBE`, then a cluster at `04ADDE`–`04B8FE`) |
| `logs/nemdec.log` | `emu/explore/nemdec.txt` | breakpoint register dumps at `NemDec`/`NemDecToRAM`: a0 holds the source of each Nemesis block |
| `logs/hpwrite.log` | `emu/explore/hpwatch.txt` | who writes `FFC8E6` (player 1 HP): `00EA20` almost every frame during play, `00E48C` once at start — the routine that reads the HP table — plus the boot-time RAM clear at `0002DA` and a handful of one-off writers (`00E532`, `00E55A`, `010362`, `010544`, `0FFA7C`) |
| `logs/fontram.log` | `emu/explore/fontsrc.txt` | the font passing through Work RAM at `FFE84A` before its DMA |
| `logs/text_regions.json` | an early Python survey | `[start, end)` byte ranges that decode as text; the seed of the five `text_*` segments |
| `ips/letters.ips`, `ips/credits.ips` | the pre-pipeline demo builds | the translation edits before they became asset diffs (see commit "Port the translation edits") |

Screenshots that document specific claims are in `docs/images/`:

| Image | Claim |
|---|---|
| `menu_main.png` | the menu reads «1 ИГРОК» from tiles `44 55 48 30 52`: the character table is what the game uses |
| `title_newgame.png` | second menu state with the NEWGAME logo (Latin `W N G` kept in the font) |
| `dialogue.png` | the dialogue frame whose tilemap confirmed the lower-case mapping |
| `font_grid.png` | the decoded font block with indices; matches the VRAM dump on all 3072 bytes |
| `newletters.png` | Ё drawn into slot 0x51, seen in-game |
| `parens.png` | the parentheses (0x2A / 0x2B) in-game |
| `hud.png` | the HUD health bar; one pixel per HP, ~54 px wide, which is why HP above 0x36 is invisible |
