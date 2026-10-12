# Style and conventions

## One rule above all

**Every byte of the ROM is owned by exactly one segment in `rom_map.yml`, and
every offset lives there and nowhere else.** Code knows formats; the map knows
addresses. A pull request that hard-codes `0x01D85E` in Python will be sent back.

## What is committed

| Kind | Committed | Where |
|---|---|---|
| Human-editable representation of ROM data | yes | `assets/` (text, YAML, text art, indexed PNG, `.pal`, `.tbl`) |
| Compressed blocks that must round-trip byte-exactly | yes | `assets/gfx/nemesis/*.nem` |
| Small verbatim regions with no better form yet | yes | `assets/sound/pcm/*.pcm` |
| Verbatim copies of code and unidentified ranges | **no** | `assets/code/*.m68k`, `assets/raw/*.raw` (extracted for browsing, gitignored) |
| Generated listings and tables | yes, marked generated | `assets/code/asm/*.s`, `assets/text/encoding.tbl`, `docs/rom_map.md` |
| Anything derived from the build | **no** | `build/` |
| The ROM | **never** | `baserom/` (ignored), CI guard, pre-commit hook |

The repository plus a base ROM reproduces the image; the repository alone must
not. When a new asset type gets a human-editable form, its verbatim copy stops
being committed.

## File extensions

`.nem` Nemesis block · `.4bpp` raw tiles · `.pcm` samples · `.m68k` code bytes ·
`.raw` unidentified bytes · `.pal` palette text · `.tbl` Thingy table · `.s`
listing · `.inc` emulator script fragment. `.bin` is reserved for ROM images and
is ignored everywhere.

## Names

Semantic names once a purpose is proven (`font.nem`, `hp_table.yml`); the ROM
offset as the name until then (`nem_013E76.nem`, `unknown_01E3DC.raw`). Rename
the file and the `path:` in the map in the same commit.

## Evidence

An address enters `rom_map.yml` with an `evidence:` field naming how it was
proven: a watchpoint or breakpoint hit, a disassembly listing, a tilemap or VRAM
dump, or an in-game screenshot after a poke. Reasoning without a run is a
comment in the journal, not a map entry.

The per-type keys a segment may carry (`min_len`, `format`, `fields`,
`max_hud`, `tiles`, `xor`, `blob`, `first_byte`, `bg`, `ink`, `sheet_tiles`,
`cols`, `prefix`, `palette`, `fill`) are listed in the header of `rom_map.yml`
and explained in [docs/build.md](docs/build.md#rom_mapyml-keys).

## Code

- **Language**: English in code, comments, CLI help and commit messages.
  `docs/ru/journal.md` is the Russian engineering journal and stays Russian.
- **Python**: 3.12, `ruff` (config in `pyproject.toml`, line length 100),
  type hints on public functions, `from __future__ import annotations`.
  Percent formatting is allowed for hex offsets (`"%06X" % off`).
- **C**: C99, two-space indent, no new warnings under the flags in
  `emu/headless/Makefile`. The core is an untouched upstream except the
  `dma_hook` commit; frontend logic goes in `emu/headless/main.c`.
- **Tests**: ROM-free by default with synthetic fixtures in `tests/fixtures/`;
  anything that needs the image is marked `@pytest.mark.rom` and skips without it.
- **No in-place ROM writes**. Tools read `baserom/`, write `build/`.

## Emulator scenes

`emu/scenes/*.txt` are regression checks: deterministic, short, one purpose,
outputs under `build/shots/` and `build/dumps/` named after the scene. Shared
prefixes go in `_*.inc` files and are pulled in with `include`. Exploration
scripts that produced a finding go to `emu/explore/` and are documented in its
README; delete the ones that produce nothing.

## Commits and pull requests

- Imperative subject, 72 characters or fewer, English.
- One logical change per commit; asset edits and code changes in separate commits
  when possible, so `git log -- assets/` reads as the translation's history.
- Pull requests are squash-merged; the PR title becomes the commit subject.
- Any change to ROM contents passes the four checks in
  [CONTRIBUTING.md](CONTRIBUTING.md) and updates `roms.sha1`
  (`ga3 verify --update`) in the same commit.
