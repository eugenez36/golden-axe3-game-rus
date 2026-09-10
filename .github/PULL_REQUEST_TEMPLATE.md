<!-- Title = squash commit title. Imperative, ≤ 72 chars. -->

## What changed

<!-- One paragraph. Which addresses / tools / scripts. Link the issue: Closes #… -->

## Why

<!-- The problem or finding that motivated this. -->

## The four checks

- [ ] **Structural** — `ga3 diff baserom/ga3.bin build/ga3.bin` shows only the expected bytes; `ga3 verify --update` run
- [ ] **Round-trip** — `ga3 text verify` passes / `make assets` leaves no diff / `make test` green
- [ ] **In-game** — scene run with `ga3 emu emu/scenes/…` · screenshot below
- [ ] **VRAM parity** — re-packing unchanged data gives byte-identical VRAM (graphics only; tick N/A otherwise)

## Proof

<!-- Paste the diff output and drop the screenshot(s) here. -->

## Housekeeping

- [ ] No `.bin` in the diff — the ROM stays out of git; new offsets went into `rom_map.yml` with `evidence:`
- [ ] Journal updated (`docs/ru/journal.md`) if an address, table or dead end was found
- [ ] Labels set: `area: …` + `🛡️ needs verification` or `🕹️ verified in-game`
