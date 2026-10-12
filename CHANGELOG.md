# Changelog

All notable changes to the toolkit and to the image it builds. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow the roadmap in the README (`ga3 --version`, shown in the main menu as
`V x.y.z`). Every change to the ROM also changes the build hash recorded in
`roms.sha1`.

## [Unreleased]

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
- The main menu shows the toolkit version as `V x.y.z` (#5).
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

[Unreleased]: https://github.com/eugenez36/golden-axe3-game-rus/compare/aa2624b...HEAD
[0.3.6]: https://github.com/eugenez36/golden-axe3-game-rus/commit/1e4ccb1
[0.3.5]: https://github.com/eugenez36/golden-axe3-game-rus/commit/aa2624b
