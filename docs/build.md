# Build pipeline

```
baserom/ga3.bin ──ga3 extract──▶ assets/ ──ga3 build──▶ build/ga3.bin + build/ga3.ips
                                    ▲                          │
                              your edits                 ga3 verify ── roms.sha1
```

Everything is driven by `rom_map.yml`. Each segment names a type; the type
selects a handler in `src/ga3/assets/` that knows how to extract that byte range
into files and how to put the files back.

## Extract

`ga3 extract` (or `make extract`) reads the base ROM, checks its SHA-1 against
the map, and writes every segment:

| Type | Written | Committed |
|---|---|---|
| `header` | `assets/header/vectors.yml`, `header.yml` | yes |
| `text` | `assets/text/<segment>.txt`, one record per string | yes |
| `nemesis` | `<path>.nem` (exact block) + `<path>.4bpp` (decoded) | `.nem` only |
| `nemesis` + `format: font_art` | `gfx/font/font.txt` (art) + `gfx/nemesis/font.nem` | both |
| `table` | YAML with named values | yes |
| `tiles4bpp` | indexed PNG sheets, 512 tiles each | yes |
| `pcm`, `raw` | verbatim | yes |
| `code`, `data` | verbatim `.m68k` | no |
| gaps (`unknown`) | `assets/raw/unknown_XXXXXX.raw`, ≤ 64 KiB each | no |
| `free` | nothing (the map records the fill byte) | — |

`--only NAME…` restricts to named segments; `--png` also renders Nemesis
previews into `build/preview/`; `--rom PATH` extracts from another image
(used once, to port the legacy IPS edits). An explicit `--rom` is used as is,
with a note on stderr when its SHA-1 differs from the map's; only the default
`baserom/ga3.bin` is refused on a mismatch.

## Build

`ga3 build` copies the base ROM into memory and, in map order, asks every
handler to place its asset:

- **Passthrough** types (`code`, `data`, `unknown`, `free`) leave the base
  ROM's bytes alone — unless a local `.m68k`/`.raw` file exists, in which case
  it is copied in. That is how a hand-patched routine gets into the build.
- **Text** records are encoded with the table, checked for length and range,
  and space-padded. Growing a string is refused.
- **Nemesis** blocks are the identity-sensitive case. Our packer produces
  smaller output than SEGA's on all 14 blocks, so recompressing an unchanged
  block would change the image. The handler therefore decodes the committed
  `.nem`, compares with the current tiles (`.4bpp` or the font art) and writes
  the `.nem` verbatim when they match. Only edited blocks are recompressed, and
  a block that no longer fits its slot fails the build with the overflow count.
  The `.4bpp` next to a block, when present, is the source of truth for its
  tiles (the build note says which file it used); delete a stale one after
  editing the `.nem` directly.
- **Header** `auto` fields (checksum, ROM end) are computed last.

Then `build/ga3.bin` is written, an IPS patch against the base ROM is produced,
applied back as a self-check, and saved as `build/ga3.ips`.

## Verify

`ga3 verify` checks `baserom/ga3.bin` and `build/ga3.bin` against `roms.sha1`
and re-applies the IPS. `ga3 verify --update` records new or changed hashes,
but only when nothing else is wrong (a missing file or an IPS that does not
reproduce the build still fails); do that in the same commit as any asset
change. `make verify` also runs
`sha1sum -c roms.sha1` so the manifest works without Python.

## Derived-but-committed files

`ga3 assets refresh` regenerates `assets/text/encoding.tbl` (from
`src/ga3/table.py`), `assets/gfx/nemesis/font.nem` (from `font.txt`) and
`docs/rom_map.md`. CI runs it and fails if the result differs from what is
committed.

## Byte identity, in numbers

| Commit | `build/ga3.bin` |
|---|---|
| pristine assets | `e9538c05…` = the base ROM |
| translation edits ported | `d2329d84…`; differs from the base only at the checksum, `0179F3–017A0A`, `01D861–01DBA5`, `0EBBDC`, `0EBC29–0EBC2E` |

`ga3 map --check` confirms the map against the base ROM: Nemesis header fields,
exact block sizes, zero padding, free-space fill bytes, the reset vector, the
header serial and checksum, and that every committed asset file exists.
`ga3 map --check-assets` runs only that last part and needs no ROM (CI uses
it). `ga3 map` prints coverage; `unknown` is the metric to drive down.

## rom_map.yml keys

Every segment has `name`, `start`, `end` (or `size`), `type` and, for asset
types, `path` (relative to `assets/`). Optional keys by type:

| Type | Keys |
|---|---|
| any | `note` (free text), `evidence` (how the address was proven) |
| `text` | `min_len` — shortest run of printable bytes that counts as a string (default 4) |
| `table` | `format` (`u8`/`u16`/`u32`), `fields` (one name per entry), `max_hud` (warn when an edited value exceeds it) |
| `nemesis` | `tiles`, `xor` (both checked against the block header); with `format: font_art` also `blob` (the derived `.nem`), `first_byte`, `bg`, `ink` |
| `tiles4bpp` | `sheet_tiles` (tiles per PNG, default 512), `cols` (default 32), `prefix` (file stem), `palette` (`NAME[/INDEX]` from `assets/palettes/`, or `gray`) |
| `free` | `fill` — the byte the whole range must hold |

The `rom:` block records `title`, `serial`, `size`, `sha1`, `md5`,
`header_checksum` and `entry_point`; `size`, `sha1`, `serial`,
`header_checksum` and `entry_point` are enforced. `palettes:` lists the
emulator CRAM captures under `assets/palettes/` (not build inputs).

## Command reference

Global options come first: `--root PATH` (default: walk up from the working
directory to `rom_map.yml`, or `$GA3_ROOT`), `--rom PATH` (another image
instead of `baserom/ga3.bin`), `--version`. Hex offsets are written with or
without `0x`. Set `GA3_DEBUG=1` to see a traceback instead of `error: …`.

| Command | Does |
|---|---|
| `extract [--only SEG…] [--png] [--rom PATH]` | take the ROM apart into `assets/`; `--png` renders Nemesis previews |
| `build [-o FILE] [--no-ips] [--rom PATH]` | rebuild the image (and the IPS) from `assets/` |
| `verify [--update]` | hashes against `roms.sha1`, IPS against the build |
| `map [--check \| --check-assets \| --markdown \| --list]` | coverage, validation, the Markdown table |
| `assets [refresh]` | regenerate `encoding.tbl`, `font.nem`, `docs/rom_map.md` |
| `asm` | Capstone listings of every `code` segment (`[disasm]` extra) |
| `info [FILE]` | header, checksum and SHA-1 of an image |
| `diff A B [--limit N]` | byte differences between two images |
| `patch make ORIG PATCHED -o FILE` / `patch apply ORIG IPS -o FILE` | IPS in both directions |
| `tiles render OFF COUNT [-o PNG] [--palette REF] [--cols N] [--scale N] [--grid] [--file IMG]` | tiles as an RGB PNG |
| `tiles ascii OFF COUNT [--cols N] [--file IMG]` | tiles in the terminal |
| `tiles import PNG -o RAW [--indexed]` | PNG back to 4bpp bytes |
| `pals [--limit N]` | heuristic palette search (leads, not facts) |
| `nemesis unpack OFF [-o RAW] [--file IMG]` / `nemesis pack RAW -o NEM [--xor auto\|on\|off] [--no-slack]` / `nemesis size OFF [--file IMG]` | the codec by hand |
| `text export` / `text verify` | re-extract the strings files / check them against the table and the ROM |
| `font info` / `font export-art` / `font export-png [-o PNG] [--scale N]` | margin and free slots / re-extract the art / render the current art |
| `balance show` / `balance set-hp V V V V` | the HP table by name |
| `disasm ADDR [-n N] [--back N] [--file IMG]` | an m68000 listing window (`[disasm]` extra) |
| `ramsearch corr\|value\|decreasing …` | find variables in Work RAM dumps (see docs/emulator.md) |
| `emu SCRIPT [-- extra headless args]` | run a scene against `build/ga3.bin` |

`--file IMG` on the inspection commands reads any file (a `.4bpp`, a dump)
without a project; `--palette REF` is `NAME[/INDEX]` from `assets/palettes/`
or a hex ROM offset (a `.pal` file wins over a look-alike such as `cafe`).
