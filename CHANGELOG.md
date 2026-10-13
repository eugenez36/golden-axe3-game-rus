# Changelog

All notable changes to the toolkit and to the image it builds. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions are
`X.YY.ZZZ`, zero-padded everywhere (`0.37.400`, `0.38.001`): in `ga3 --version`,
in the main menu (`V X.YY.ZZZ`) and in the tags (`vX.YY.ZZZ`); releases before
0.37.400 kept their old numbers. Every change to the ROM also changes the build
hash recorded in `roms.sha1`.

## [Unreleased]

### Added

- **Gameplay constants:** numbers inside the code (instruction operands) are
  mapped under `constants:` in `rom_map.yml` with their instructions' base-ROM
  bytes and edited by name in `assets/data/gameplay.yml`. The first two:
  **spare lives** (2; at the start and after a continue) and **credits**
  (continues, 4). `ga3 balance set lives 5`, `ga3 balance show`; the table is
  in `docs/rom_map.md`.
- **Hero stats on the character select:** the hero under each player's cursor
  shows name, magic, health, hit / super, tempo and walking speed, each with a
  bar, over the title (full width alone, a half panel each with two players,
  none on the duel select). Numbers checked against the ROM's tables; data in
  `assets/data/hero_panel.yml`, patch `hero_panel`.
- **Difficulty «ЖЕСТЬ)»:** a third value of OPTIONS → СЛОЖНОСТЬ. The enemies
  of ТРУДНО, and every ordinary enemy comes twice (never a boss): the copy
  enters where the original did as soon as one of the four enemy slots is
  free, and the next wave waits for it. Names in `text/difficulty.txt`, patch
  `difficulty`. An assembled patch can carry a strings file (`strings:`).
- **OPTIONS → БАНКИ МАГИИ:** the magic potions a player gets when they have
  none (start, death, continue), 0–6, kept over a soft reset like the
  difficulty. МЕНЮ moves three rows down. The constant `potions` is now the
  item's default, and the default is 0 (the base game gives 1; the attract
  demo still does). Label in `text/options.txt`, patch `options`.
- **Gameplay constant `potions`:** the magic potions a player gets when they
  have none — at the start, after a death and after a continue; since БАНКИ
  МАГИИ, the item's default (0; the base game gives 1). `ga3 balance set
  potions 6`; capped at 6, what the HUD can draw. Constants take a
  hard `max` in `rom_map.yml`, refused by `balance set` and by the build;
  `balance show` prints it.
- **Docs: `docs/heroes.md`**, every parameter of the four heroes: attacks,
  speeds, magic, health, potions, lives.
- **Font: `/`** in the blank slot `3E`, for hit / super on the character
  select («6/18»). The font block is 837 of its 840 bytes; `7B` and `7F` stay
  free.
- **The build is 2 MiB:** `rom.build_size` in `rom_map.yml` expands the image
  (the base dump stays 1 MiB and is still checked against its SHA-1);
  `100000–1FFFFF` is free space for new code and data (the patches since start
  at `100000`; `102400–1FFFFF` is still free). The IPS writer emits
  RLE records, so the expansion adds about 140 bytes to the patch.

### Fixed

- Kill counter: a hit of 128 damage (a power of `0xFF` plus the carried
  half) left the victim alive with HP 203 instead of knocking it out as the
  original game does; the hooks now decide death with `bhi`, which matches
  the game's `bpl` for every allowed HP. Stock moves never reach that damage.

## [0.37.400] — 2026-10-12

The proofread text, the kill counter (to 999) and the bug hunt, with the
toolkit and documentation work behind them. First release numbered
`X.YY.ZZZ`; the main menu shows `V 0.37.400`.

### Added

- **Kill counter** next to each player's HUD (#11, #17): enemies killed by
  that player, up to 999 (three digits for each player); the kill goes to the
  player who hit the enemy last, falls off the stage included. Reset when a
  game mode is chosen, not shown in a duel. Written in 68000 assembly
  (`assets/patches/kill_counter.s`).
- **`ga3.m68k`**, a two-pass 68000 assembler for patch sources; every
  supported instruction form is checked by disassembling it with Capstone
  (#11).
- Assembled multi-slot patches in `rom_map.yml` (`patches:`), hooks checked
  against the base ROM's bytes, and a post-build check that no later segment
  overwrote a patch (#11).
- **`ga3 lag SCENE`** counts frames lost to slowdown; the headless emulator
  gained `--overclock PCT` (#10). Player settings for Genesis Plus GX in the
  README.
- `make regress` runs the scenes in parallel, one per CPU (#9).
- Scenes `game_over.txt` (map screen with score and rank), `duel_hud.txt` and
  `kill_counter_999.txt` (#16, #17).
- `align-md-tables` pre-commit hook: Markdown tables stay aligned (#14).
- Docs: `docs/patches.md`, `docs/ru/proofreading.md`, a bug-hunt entry in the
  journal.

### Changed

- **Game text proofread** (#6): spelling and punctuation fixes, the lower-case
  «ё», main-menu items widened to 8 characters («2 ИГРОКА»), options labels
  «МУЗ.» / «ЗВУК». Details in `docs/ru/proofreading.md`.
- The main menu shows the toolkit version (#5), now as `V X.YY.ZZZ`.
- Versions are `X.YY.ZZZ`, zero-padded; a test keeps `ga3.__version__`,
  `pyproject.toml` and the menu line in that form.
- `docs/rom_map.md` escapes Markdown in notes and evidence (#12).
- Documentation reviewed against the code: stale facts, wording and
  formatting fixed (#12, #13).

### Fixed

- Map screen: the grade (AAA … F) was labelled «ЭТАП» (stage); now «РАНГ»
  (#16).
- Character table: the glyphs `0x29` / `0x50` had their cases swapped (#6).
- Kill counter, before release: digits showed before the HUD art reloaded
  after a spell; walking the whole sprite list every frame slowed busy
  two-player fights down (#11).

## [0.3.6] — 2026-10-12

### Fixed

- Audit of the toolkit (#4): synthetic test project, `_open_image`,
  `ga3 map --check-assets`, ruff pinned in both places.

## [0.3.5] — 2026-09-10

### Added

- The `ga3` package: `rom_map.yml` → `assets/` → `build/` pipeline with
  byte-identical rebuilds, `roms.sha1` and an IPS patch.
- Assets extracted from the base ROM; the 2003 translation's edits ported
  onto them.
- Headless Genesis Plus GX (submodule with a `dma_hook`), scripted scenes,
  screenshots, dumps, watchpoints.
- CI, pre-commit hooks, bilingual README, contribution and style guides.

[Unreleased]: https://github.com/eugenez36/golden-axe3-game-rus/compare/v0.37.400...HEAD
[0.37.400]: https://github.com/eugenez36/golden-axe3-game-rus/compare/1e4ccb1...v0.37.400
[0.3.6]: https://github.com/eugenez36/golden-axe3-game-rus/commit/1e4ccb1
[0.3.5]: https://github.com/eugenez36/golden-axe3-game-rus/commit/aa2624b
