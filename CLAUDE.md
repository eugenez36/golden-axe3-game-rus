**Allowed (read-only):**
- `git status`, `git diff`, `git log`, `git branch -v`, `git show`

**Rules:**
- User decides when and what to commit
- Never add "Generated with Claude Code" or "Co-Authored-By: Claude" to commits

**Project workflow:**
- Every change on a fresh branch from `main`: `quest/…` for features, `glitch/…` for fixes and docs
- Pipeline: `rom_map.yml` → `assets/` → `build/`; offsets live only in `rom_map.yml`, new addresses come with `evidence`
- A change to the ROM updates `roms.sha1` (`ga3 verify --update`) and the last row of the hash table in `docs/build.md`
- Before a push: `make verify && make test && pre-commit run --all-files` (CI runs the same hooks; `make lint` alone misses whitespace and tables)
- New code goes in `assets/patches/*.s`, hooked only over base-ROM bytes the map names; check it in the emulator (`emu/scenes/`)
- Documents stay current with the map (`tests/test_docs.py`); `docs/ru/journal.md` records how things were found and is never rewritten, only annotated
- Version `X.YY.ZZZ`, zero-padded; only the owner bumps it, and then only ZZZ unless told otherwise; no milestones on work in progress
