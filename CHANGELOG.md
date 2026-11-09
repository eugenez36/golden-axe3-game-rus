# Changelog

All notable changes to the toolkit and to the image it builds. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions are
`X.YY.ZZZ`, zero-padded everywhere (`0.37.400`, `0.38.001`): in `ga3 --version`,
in the main menu (`V X.YY.ZZZ`) and in the tags (`vX.YY.ZZZ`); releases before
0.37.400 kept their old numbers. Every change to the ROM also changes the build
hash recorded in `roms.sha1`.

## [Unreleased]

### Added

- **The sound bank, mapped** (issue #53). `0F0000–0FFA10` is SEGA's SMPS 68k
  driver: pointer table `0F0000`, music index `0F0116` (27 songs, IDs
  `81–9B`), driver code `0F01FA` (listing `snd_driver.s`), songs `0F186C`,
  SFX `0F93E4`, the Z80 DAC driver `0FACC8` (406 bytes, copied to the Z80 at
  boot) and its sample table `0FAE5E`. Proof: `emu/scenes/sound_bank.txt`,
  `tests/test_sound_rom.py`. The build is unchanged.

### Fixed

- **`text_misc` was sample data.** `0FB000–0FB500` holds bytes of the first
  DAC sample, not strings: `assets/text/misc.txt` is gone (210 strings in
  eleven files), and `samples.pcm` now starts where the samples do, `0FAEB8`
  (it began mid-sample at `0FC000`).

## [0.37.800] — 2026-11-06

Gameplay by name: the heroes' speeds and powers, the spells' damage, the
continue countdown and the prisoners a life costs join the HP table, lives,
credits and potions under `ga3 balance`; the hero panel reads the same files.
The toolkit builds twice as fast and the emulator has the RESET button; the
main menu shows `V 0.37.800`.

### Added

- **Releases carry the game.** Every GitHub release has the built image
  `ga3-X.YY.ZZZ.bin` (download, open in a Mega Drive emulator, play) and the
  patch `ga3-X.YY.ZZZ.ips` as files, with a `.sha256` to check them;
  `make dist` writes them to `build/dist/`, and the README opens with where
  to get them.
- **Prisoners per life by name.** Constant `prisoners` (`0103F2` … `010410`:
  the freed prisoners that earn a life, 5; the icons shown and the blinks
  follow it; up to 8, the HUD draws 5 icons); `ga3 balance set prisoners 3`.
  A constant's site may now be an `addq` / `subq` (`[address, bytes, offset,
  quick]`: the 3-bit count in the opcode). Patch `kill_counter` reads the
  game's operand for the icons of its life every 100 kills (`ICONS_SRC`), so
  the two signals agree; its `bonus` section grows by 4 bytes and the build
  hash changes.

- **Continue countdown by name.** Constants `countdown` (`00E650`: the seconds
  «ИГРАЕМ? 9» counts from after the last death, one digit) and
  `countdown_frames` (`00E65C`, `00E71A`: frames a count lasts, 60) in
  `data/gameplay.yml`; `ga3 balance set countdown 5`. Checked in the emulator:
  the count at `FFC783` steps every `countdown_frames` frames and the game over
  starts at zero. The image is unchanged.

- **Hero parameters by name.** Two new table segments, `walk_speed`
  (`0x337E6`, `data/walk_speed.yml`: X and depth walking speed of every
  class) and `move_speed` (`0x337FA`, `data/move_speed.yml`: dash, jump,
  dash-jump and air speed of 15 classes), and new constants in
  `data/gameplay.yml`: `KEY_hit` / `KEY_super` (the power of each hero's first
  combo hit and launch), `magic_l0` … `magic_team` and `enemy_magic` (the
  spells' damage). `ga3 balance show` lists every table and constant;
  `ga3 balance set TABLE.FIELD VALUE` edits a table field
  (`walk_speed.kain_x 0x200`). The hero panel of the character select derives
  hp, hit, super and speed from these files (`hero_panel.yml` keeps the names
  and the measured tempo), so a change shows on the select screen and in play:
  checked in the emulator (Kain at `0x300` walks exactly 3 px a frame, the panel
  shows 180). The image is unchanged.

- **Emulator:** `softreset`, the console's RESET button (`gen_reset(0)`, as
  the libretro frontend; Work RAM and the I/O registers kept). `reset` stays
  the power-on reset, which clears RAM. Scenes `options_reset.txt` (100 ВРАГОВ
  kept over `softreset`, cleared by `reset`) and
  `options_extra_life_2p_blink.txt` (player 2's prisoner icons blink five
  times for the life at 100 kills, a Work RAM dump every 8 frames).

## [0.37.700] — 2026-11-06

The menus in the style of the README banner, and the banner itself replaced
by the new title and menu, captured in the emulator. A new options item: a
life for every hundred kills. The toolkit builds twice as fast; the main menu
shows `V 0.37.700`.

### Added

- **OPTIONS → 100 ВРАГОВ** (patches `options` and `kill_counter`), ВЫКЛ by
  default: with ВКЛ, every 100th kill of a player (100, 200, … up to the
  counter's 999) gives that player a life, signalled the way the game signals
  a life for five prisoners: the five prisoner icons blink with the extra-life
  sound. No life above 9 (the HUD's one digit), none in the demo. Kept over a
  soft reset with the other options (bit 7 of `$C729`).

- **Menus in the banner's style** (patch `menus`, `assets/patches/menus.s`):
  the title, the main menu, the options and the character select get the
  banner's navy sky with drifting cloud strips, its blocky gold logo with a
  black outline (also in the intro's scroller and the falling letters), a gold
  cursor and a black bottom bar under a gold line — СЕГА, НАЖМИ СТАРТ blinking
  on the title, the version in the menu, 2О26 NЕWGАМЕ. The duel's ВЫБОР ГЕРОЯ
  and ВЫБОР ЭТАПА turn gold, the ending's THE END is in the new letters. Slots at
  `102760–10491F`; most of the patch points the game's own loaders at new
  data.
- **`ga3 banner-art`** draws the menus' art (`assets/gfx/screens/*.png`) from
  `docs/branding/banner.svg`; **`make banner`** captures the title and the menu
  (`emu/scenes/banner.txt`) and **`ga3 banner-anim`** turns the shots into the
  README banner, `docs/branding/banner.png` (an animated PNG).
- **Enigma codec** (`ga3.enigma`): the game's tilemap compression, decoder and
  encoder; **`ga3.screen`**: indexed PNG → tiles, maps, sprite tiles, palettes.
- **Patches:** `pointers:` (point the game's code at new data without a hook)
  and `art:` (tiles, maps and palettes from PNGs) in a patch definition.

### Changed

- **Main menu:** the version line moves to the middle of the bottom bar
  (`menu_version` ends at column 24).
- **Options screen:** seven items; below КНОПКИ every item is two rows from
  the next (МУЗ., ЗВУК, БАНКИ МАГИИ, 100 ВРАГОВ, МЕНЮ). The options patch's
  slots move to `104920` (labels) and `104A00` (code); the kill counter's
  `kill` moves to `104940`.
- **Toolkit, faster build:** a patch with several sections is assembled once
  per build instead of once per section (its `art:` PNGs were Nemesis-packed
  again for every section); the run cutting of the Nemesis packer, the import
  of indexed PNG sheets, the IPS run-length search and the header checksum
  do less work. `ga3 build` takes about half the time; the image is the same.
- **Toolkit:** `rom_map.yml` refuses a `patches:` entry no segment uses;
  `ga3` no longer turns a `KeyError`/`IndexError` of its own into a one-word
  `error:` line (a bug keeps its traceback); Pillow 11.3 or newer is required
  (the toolkit already used its API).

### Fixed

- **Assembler:** a branch or `d16(pc)` operand farther than 32 KiB used to be
  assembled silently with the wrong sign (a jump 0x9000 bytes ahead became a
  jump 0x7000 bytes back); it is now an error naming the line.
- **Toolkit:** the patch handler forgets the previous build before the next
  one (it kept what every segment wrote, for the overwrite check, across
  builds in one process).

## [0.37.600] — 2026-10-16

Fixes to «ЖЕСТЬ» and the kill counter: copies come in past a screen edge, on
the ground; a gnome drops two potions; the counter's digits no longer turn into
pieces of sprites; the main menu shows `V 0.37.600`.

### Added

- **ЖЕСТЬ, twice the potions:** a gnome hit by a player drops two potions
  instead of one (meat stays single), so the potions keep up with the doubled
  enemies. New patch section `drop` at `102700`, hook at `0098B8`.
- **Docs tests:** `tests/test_docs.py` checks that the documents keep up with
  `rom_map.yml`.

### Changed

- **Difficulty «ЖЕСТЬ»:** the third value of OPTIONS → СЛОЖНОСТЬ lost its
  smiley (was «ЖЕСТЬ)»).

### Fixed

- **ЖЕСТЬ, where the copies come in:** a copy of an enemy now comes in one at
  a time, just past an edge of the screen, on ground at the player's level
  found in the stage's collision boxes. It used to come in where its original
  had, often long after: behind the camera, where it could not reach the
  player on uneven ground, or inside the floor, where it fell through it; on
  stage 8 such copies stopped the wave. New patch section `place` at `102400`.
- **Kill counter artifacts:** the digit tiles moved from VRAM `D700` to `DF00`
  and are uploaded again every 256 frames. The game keeps objects' animation
  frames at `D700–DEFF` (stage 2, 3A …), which replaced the digits by pieces of
  a sprite, read as a wrong number, until the count changed.

## [0.37.500] — 2026-10-13

The 2 MiB build, hero stats on the character select, the third difficulty
«ЖЕСТЬ)» and the options item БАНКИ МАГИИ; the main menu shows `V 0.37.500`.

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

[Unreleased]: https://github.com/eugenez36/golden-axe3-game-rus/compare/v0.37.800...HEAD
[0.37.800]: https://github.com/eugenez36/golden-axe3-game-rus/compare/v0.37.700...v0.37.800
[0.37.700]: https://github.com/eugenez36/golden-axe3-game-rus/compare/v0.37.600...v0.37.700
[0.37.600]: https://github.com/eugenez36/golden-axe3-game-rus/compare/v0.37.500...v0.37.600
[0.37.500]: https://github.com/eugenez36/golden-axe3-game-rus/compare/v0.37.400...v0.37.500
[0.37.400]: https://github.com/eugenez36/golden-axe3-game-rus/compare/1e4ccb1...v0.37.400
[0.3.6]: https://github.com/eugenez36/golden-axe3-game-rus/commit/1e4ccb1
[0.3.5]: https://github.com/eugenez36/golden-axe3-game-rus/commit/aa2624b
