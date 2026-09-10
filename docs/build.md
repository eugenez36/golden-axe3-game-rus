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
(used once, to port the legacy IPS edits).

## Build

`ga3 build` copies the base ROM into memory and, in map order, asks every
handler to place its asset:

- **Passthrough** types (`code`, `data`, `unknown`, `free`) leave the base
  ROM's bytes alone — unless a local `.m68k`/`.raw` file exists, in which case
  it is copied in. That is how a hand-patched routine gets into the build.
- **Text** records are encoded with the table, checked for length and range,
  and space-padded. Growing a string is refused.
- **Nemesis** blocks are the identity-sensitive case. Our packer produces
  smaller output than SEGA's on 13 of 14 blocks, so recompressing an unchanged
  block would change the image. The handler therefore decodes the committed
  `.nem`, compares with the current tiles (`.4bpp` or the font art) and writes
  the `.nem` verbatim when they match. Only edited blocks are recompressed, and
  a block that no longer fits its slot fails the build with the overflow count.
- **Header** `auto` fields (checksum, ROM end) are computed last.

Then `build/ga3.bin` is written, an IPS patch against the base ROM is produced,
applied back as a self-check, and saved as `build/ga3.ips`.

## Verify

`ga3 verify` checks `baserom/ga3.bin` and `build/ga3.bin` against `roms.sha1`
and re-applies the IPS. `ga3 verify --update` records the current hashes; do
that in the same commit as any asset change. `make verify` also runs
`sha1sum -c roms.sha1` so the manifest works without Python.

## Derived-but-committed files

`ga3 assets refresh` regenerates `assets/text/encoding.tbl` (from
`ga3/table.py`), `assets/gfx/nemesis/font.nem` (from `font.txt`) and
`docs/rom_map.md`. CI runs it and fails if the result differs from what is
committed.

## Byte identity, in numbers

| Commit | `build/ga3.bin` |
|---|---|
| pristine assets | `e9538c05…` = the base ROM |
| translation edits ported | `d2329d84…`; differs from the base only at the checksum, `0179F3–017A0A`, `01D861–01DBA5`, `0EBBDC`, `0EBC29–0EBC2E` |

`ga3 map --check` confirms the map against the base ROM: Nemesis header fields,
exact block sizes, zero padding, free-space fill bytes, the reset vector and the
header checksum. `ga3 map` prints coverage; `unknown` is the metric to drive down.
