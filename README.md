<div align="center">

<img src="docs/branding/banner.svg" alt="Golden Axe III — ROM hacking toolkit" width="100%">

**English** · [Русский](README.ru.md)

![Platform](https://img.shields.io/badge/platform-Sega_Mega_Drive-1F3A5F?style=for-the-badge&logo=sega&logoColor=white)
![CPU](https://img.shields.io/badge/cpu-Motorola_68000-2F5D8A?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C99](https://img.shields.io/badge/c-99-A8B9CC?style=for-the-badge&logo=c&logoColor=black)
[![License](https://img.shields.io/badge/license-MIT-F5B301?style=for-the-badge)](LICENSE)
[![ROM](https://img.shields.io/badge/ROM-not_included-D7263D?style=for-the-badge)](#legal)
[![CI](https://github.com/eugenez36/golden-axe3-game-rus/actions/workflows/ci.yml/badge.svg)](https://github.com/eugenez36/golden-axe3-game-rus/actions/workflows/ci.yml)

</div>

---

A ROM-hacking toolkit for **Golden Axe III** (Sega Mega Drive, 1993) built around
the **NEWGAME 2003 Russian translation**. The cartridge image is taken apart into
an editable tree of assets — text, font, Nemesis graphics, tile sheets, palettes,
samples, data tables, code listings — and rebuilt **byte for byte** from it.
Every change is proved inside the real game with a **headless Genesis Plus GX**:
no window, just scripts, screenshots and memory dumps.

Nothing here is guessed. Every offset lives in one file, `rom_map.yml`, with the
evidence that put it there.

```text
baserom/ga3.bin ──ga3 extract──▶ assets/ ──ga3 build──▶ build/ga3.bin + build/ga3.ips
   (yours, never                 (committed,              (verified against
    committed)                    the ROM taken apart)     roms.sha1)
```

## Highlights

- **Reproducible build.** `make` rebuilds the image from `assets/`; `make verify`
  checks it against `roms.sha1`. Freshly extracted assets give back the base
  ROM to the byte; the committed ones give the build recorded in `roms.sha1`.
- **The ROM, taken apart.** Header and vectors as YAML, 224 strings in eleven text
  files, the font as text art, 14 Nemesis blocks, 22 indexed-PNG sheets of tile
  art, the PCM region, the HP table and gameplay constants, the hero panel's
  data, six captured palettes and Capstone listings
  of every code segment. What is still unidentified is measured, not hidden:
  `ga3 map` prints the coverage.
- **Nemesis codec, both ways.** Decoder lifted from the game's disassembly and
  verified against a VRAM dump (3072/3072 bytes). The encoder beats SEGA's on
  all 14 blocks (13 780 vs 14 045 bytes); its output differs from SEGA's, so for
  byte identity the build reuses the original blocks verbatim until you edit
  them.
- **Font editing in plain text.** Glyphs as `#`/`.` art. **Ё**, **ё**, **Ъ**,
  Latin **V**, the parentheses and **/** were added to a translation that never
  had them; the build refuses a font that would not fit its 840-byte slot (837
  used).
- **Gameplay by name.** `ga3 balance set-hp 60 60 60 60` edits the HP table;
  `ga3 balance set lives 5` / `set credits 9` / `set potions 3` the spare
  lives, the continues and the default of OPTIONS → БАНКИ МАГИИ (starting magic
  potions, 0–6). These are numbers inside the code, each instruction checked
  against the base ROM; the addresses are the map's business.
- **New code in 68000 assembly.** Patches live in `assets/patches/*.s`, are
  assembled by the built-in `ga3.m68k` (every instruction form checked with
  Capstone) and hook the game only where the base ROM holds the expected
  bytes. They show each player's kills next to their HUD, the hero stats on
  the character select, a third difficulty «ЖЕСТЬ» and OPTIONS → БАНКИ МАГИИ
  ([docs/patches.md](docs/patches.md)).
- **Emulator as a measuring instrument.** Scripted input, screenshots, VDP and
  RAM dumps, watchpoints, breakpoints and a `dma_hook` added to the core so DMA
  sources can be traced. A cheat-engine-style RAM correlator finds values from
  screenshots (player HP: r = 1.0000).

## Quick start

> The ROM is not part of this repository. Put your own dump at `baserom/ga3.bin`
> (1 MiB, SHA-1 `e9538c05…`, see [baserom/README.md](baserom/README.md)).
> Full setup: [INSTALL.md](INSTALL.md).

```bash
git clone --recurse-submodules https://github.com/eugenez36/golden-axe3-game-rus.git
cd golden-axe3-game-rus
make venv && source .venv/bin/activate

make            # build/ga3.bin + build/ga3.ips from assets/
make verify     # sha1sum -c roms.sha1
make test       # pytest (ROM-gated tests skip without the ROM)

# edit something
$EDITOR assets/text/dialogue.txt          # a string; may not grow
$EDITOR assets/gfx/font/font.txt          # a glyph
ga3 balance set-hp 60 60 60 60            # the HP table
make && ga3 verify --update               # rebuild, record the new hash

# see it in the actual game
make emu && make regress                  # screenshots land in build/shots/
ga3 emu emu/scenes/dialogue_pages.txt

# look around
ga3 map                                   # coverage: what is still unknown
ga3 map --check                           # the map against the base ROM
ga3 extract --only nem_013E76 --png      # Nemesis previews in build/preview/ (a bare extract overwrites your edits)
ga3 disasm E482 -n 12                     # the HP table's reader
```

## How it fits together

```mermaid
flowchart LR
    ROM[("baserom/ga3.bin<br/>read-only, not committed")] --> X[ga3 extract]
    MAP[["rom_map.yml<br/>every offset, with evidence"]] --> X
    MAP --> B
    X --> A["assets/<br/>text · gfx · palettes · sound · data · header · code/asm"]
    A --> B[ga3 build]
    ROM --> B
    B --> OUT[("build/ga3.bin<br/>build/ga3.ips")]
    OUT --> V{{"ga3 verify<br/>roms.sha1 · IPS self-check"}}
    OUT --> E["headless Genesis Plus GX<br/>emu/scenes · screenshots · dumps · watchpoints"]
    E -. new addresses .-> MAP
```

## Repository layout

```text
rom_map.yml       the single home of every ROM offset (splat-style segments)
roms.sha1         sha1 of the base ROM and of the build; `make verify`
Makefile          venv · build · extract · verify · test · lint · assets · asm · emu · regress · clean · distclean · help
pyproject.toml    the ga3 package and its `ga3` command
baserom/          put your ROM here (ignored)
assets/           the ROM taken apart — see STYLE.md for what is committed
  header/         vectors.yml, header.yml
  text/           menu · stages · ending · dialogue · misc · menu_items · difficulty · options · code_main_{b,d,e} .txt, encoding.tbl
  gfx/            font/font.txt, nemesis/*.nem, tiles/art_*.png (indexed)
  palettes/       *.pal captured from the emulator (no ROM source known yet)
  sound/pcm/      samples.pcm
  data/           hp_table.yml, gameplay.yml (lives, credits, potions), hero_panel.yml
  patches/        *.s: 68000 sources of the assembled patches (kill_counter, hero_panel, difficulty, options)
  code/asm/       Capstone listings (generated)
build/            everything derived (ignored): ROM, IPS, emulator, shots, dumps, previews
src/ga3/          the toolkit: rom · nemesis · table · text · font · tiles · palette · rom_map · assets/ · pipeline · patches · m68k · constants · hero_panel · balance · disasm · ramsearch · lag · cli
tests/            pytest; ROM-free fixtures plus ROM-gated tests
emu/              gpgx (submodule) · patches/ · headless/ · scenes/ · explore/
docs/             README (index) · build · text_format · nemesis · font · emulator · patches · heroes · rom_map (generated) · evidence/ · images/ · branding/ · ru/journal.md · ru/proofreading.md
```

## ROM map

Generated from `rom_map.yml`: [docs/rom_map.md](docs/rom_map.md). The short version:

| Range                            | Contents                                                                                                                                                                                      |
|----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `000000–000200`                  | vectors and header (entry point moved by the translators to `0FFA20`)                                                                                                                         |
| `000200–01B780`                  | 68000 code, with the HP table at `00E492`, a Nemesis block at `013E76`, the menu / stage / ending text, the menu-version routine, the main-menu items and the kill counter at `0116B6–011800` |
| `01B780–01E3DC`                  | 12 Nemesis blocks nearly back to back (a 6-byte data stub after the font, 43 unknown bytes at `01E26F`), the font at `01D85E` (840 B)                                                         |
| `0295EE–029F08`                  | one more Nemesis block (208 tiles)                                                                                                                                                            |
| `05AEAA–05AFCE`, `05B30A–05B42A` | the kill counter's display code and digit glyphs, in two former holes                                                                                                                         |
| `080000–0D8000`                  | 11 264 uncompressed 4bpp tiles                                                                                                                                                                |
| `0E9B00–0EC300`                  | dialogue, credits, ending text                                                                                                                                                                |
| `0FC000–0FFA20`                  | PCM samples                                                                                                                                                                                   |
| `0FFA20–100000`                  | the relocated entry stub                                                                                                                                                                      |
| `100000–102700`                  | the hero stats panel, the «ЖЕСТЬ» difficulty and the БАНКИ МАГИИ option (patches `hero_panel`, `difficulty`, `options`)                                                                       |
| `102700–102760`                  | «ЖЕСТЬ»: the second potion from a gnome's hit (patch `difficulty`)                                                                                                                            |
| `102760–200000`                  | free: the build is expanded to 2 MiB (`rom.build_size`)                                                                                                                                       |

Free space: **about 1 MiB** (1 038 496 bytes) at `102760–1FFFFF` — the build is expanded to 2 MiB
(`rom.build_size` in `rom_map.yml`; the base dump stays 1 MiB) — plus 28 bytes
left of the 914 in the original image's three verified holes, which the patches
(menu version, menu items, kill counter) fill. About half of the base image is
still `unknown`; `ga3 map` prints the exact figure and the ranges.

## Roadmap

- [x] **v0.10 — Text & Font** · byte-exact round-trip, glyph editor, Ё / Ъ / ( ), translator credit
- [x] **v0.20 — Nemesis packer parity** · smaller than the original on all 14 blocks, self-verifying
- [x] **v0.30 — Headless emulator** · scenes, screenshots, dumps, watchpoints, `dma_hook`
- [x] **v0.35 — Reproducible build** · `rom_map.yml`, `assets/`, `build/`, `roms.sha1`, tests, CI
- [x] **v0.37.400 — Text and kill counter** · proofread text, kill counter up to 999, bug hunt ([CHANGELOG](CHANGELOG.md))
- [ ] **v0.40 — Gameplay tables** · lives, credits and starting magic potions done (`ga3 balance`), hero stats on the select screen, difficulty «ЖЕСТЬ»; timers next (method ready in `ga3 ramsearch`)
- [ ] **v0.50 — Palettes and tilemaps in ROM** · turn the grey tile sheets into real colours
- [ ] **v1.00 — Release IPS** · verified patch with RU + EN docs

Progress is tracked in [milestones](https://github.com/eugenez36/golden-axe3-game-rus/milestones).

## Playing

Apply `build/ga3.ips` to your own dump, or run `build/ga3.bin`, in any Mega
Drive emulator. In Genesis Plus GX (RetroArch), *System Overclock* 150–200%
shortens the pauses while magic loads and *Remove Per-Line Sprite Limit*
removes flicker; numbers in [docs/emulator.md](docs/emulator.md#lag-and-overclock).
The small blue box right of each HUD counts the enemies that player has killed
(up to 999); it starts from zero when a game mode is chosen in the main menu
and is not shown in a duel. On the character select a panel shows the stats
of the hero under each cursor. OPTIONS adds a third difficulty, «ЖЕСТЬ» (every
ordinary enemy comes twice), and БАНКИ МАГИИ: the magic potions a player gets
when they have none, 0–6 (default 0).

## Documents

[INSTALL.md](INSTALL.md) · [CHANGELOG.md](CHANGELOG.md) · [STYLE.md](STYLE.md) ·
[CONTRIBUTING.md](CONTRIBUTING.md) ·
[docs/build.md](docs/build.md) · [docs/text_format.md](docs/text_format.md) ·
[docs/nemesis.md](docs/nemesis.md) · [docs/font.md](docs/font.md) ·
[docs/emulator.md](docs/emulator.md) · [docs/patches.md](docs/patches.md) ·
[docs/heroes.md](docs/heroes.md) ·
[docs/evidence](docs/evidence/README.md) ·
**[engineering journal (Russian)](docs/ru/journal.md)** — how each address was found, dead ends included.

## Legal

- **No ROM is distributed here**, and none ever will be. Golden Axe III is © SEGA.
  "SEGA", "Mega Drive", "Genesis" and "Golden Axe" are trademarks of SEGA Corporation.
- `assets/` contains data extracted from the game in editable form so that
  changes can be reviewed as diffs. Together with a base ROM it reproduces the
  image; the repository alone does not — code and unidentified regions are
  deliberately not committed (see [STYLE.md](STYLE.md)).
- The Russian translation this toolkit targets is the work of **NEWGAME (2003)**.
- The toolkit is [MIT](LICENSE). Genesis Plus GX is by Charles MacDonald and
  Eke-Eke under its own **non-commercial** license; see
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<div align="center">
<sub>Built with a hex editor, a disassembler, and far too many screenshots of an orc.</sub>
</div>
