# assets/gfx/nemesis

The 14 Nemesis-compressed tile blocks of the ROM, one `.nem` each, exactly as
long as the block in the image (0–2 bytes of zero word-alignment padding are
described in `rom_map.yml`, not stored here).

Editing workflow:

1. `ga3 extract --png` writes the decoded tiles next to each block as `.4bpp`
   (gitignored) and previews into `build/preview/`.
2. Edit the `.4bpp` (or render it to a PNG with `ga3 tiles render --file …`,
   edit, and import back with `ga3 tiles import --indexed`).
3. `ga3 build` recompresses only blocks whose tiles changed and refuses a block
   that no longer fits its slot. Unchanged blocks are written back byte for byte:
   our packer is smaller than SEGA's, so recompressing would break identity.

When a `.4bpp` exists it is the source of truth for that block's tiles and the
`.nem` is only reused if it still decodes to them; a stale `.4bpp` therefore
wins over an edited `.nem`. Delete it (or re-run `ga3 extract`) after editing a
`.nem` directly. The build log names the file each recompressed block came from.

Names are the ROM offset until a block's purpose is confirmed in-game; rename the
file and the `path:` in `rom_map.yml` together when you prove one (the load order
in `docs/evidence/logs/nemdec.log` is the starting point). The font is the
exception: `font.nem` is *derived* from `../font/font.txt` by `ga3 assets refresh`.
