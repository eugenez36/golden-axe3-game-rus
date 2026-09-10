<!-- Title = squash commit title. Imperative, ≤ 72 chars. -->

## What changed

<!-- One paragraph. Which addresses / tools / scripts. Link the issue: Closes #… -->

## Why

<!-- The problem or finding that motivated this. -->

## The four checks

- [ ] **Structural** — `romlib.py diff` shows only the expected bytes, checksum recomputed
- [ ] **Round-trip** — `text_tool.py verify` passes / re-pack → decode equals original
- [ ] **In-game** — headless run script: `scripts/…` · screenshot below
- [ ] **VRAM parity** — re-packing unchanged data gives byte-identical VRAM (graphics only; tick N/A otherwise)

## Proof

<!-- Paste the diff output and drop the screenshot(s) here. -->

## Housekeeping

- [ ] No `.bin` in the diff — the ROM stays out of git
- [ ] Journal updated (`docs/ru/journal.md`) if an address, table or dead end was found
- [ ] Labels set: `area: …` + `🛡️ needs verification` or `🕹️ verified in-game`
