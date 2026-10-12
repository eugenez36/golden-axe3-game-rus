# baserom/

Put your own dump of the game here as **`ga3.bin`**. Nothing in this directory
except this file is tracked by git, and the CI guard job fails on any ROM-sized
file with a SEGA header anywhere in the tree.

| Field | Expected value |
|---|---|
| File | `baserom/ga3.bin` |
| Game | Golden Axe III, Sega Mega Drive, Russian translation by NEWGAME (2003) |
| Serial | `GM 00004093-00` |
| Size | 1 048 576 bytes (1 MiB) |
| Header checksum | `9BB5` |
| SHA-1 | `e9538c0542b4a05050f5b68d279cddb06559ae20` |
| MD5 | `eae35fbc0f915048cead589db377407f` |

Check it with:

```bash
sha1sum -c --ignore-missing roms.sha1   # or compare with: ga3 info
```

`ga3 extract` and `ga3 build` refuse to run against an image whose SHA-1 does
not match `rom_map.yml`. To work with a different dump on purpose, pass
`--rom PATH` (the check is then skipped for both commands; a note is printed
when the SHA-1 differs).
