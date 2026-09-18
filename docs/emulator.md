# The headless emulator

*Russian original: `ru/journal.md`, «Эмулятор как измерительный прибор».*

No emulator could be installed on the machine this project started on, so
`emu/headless/` is a frontend for **Genesis Plus GX** that needs only libc and
zlib: no window, no SDL, no libretro. It runs a ROM under a script, presses
buttons, saves PNG screenshots (own encoder), dumps VDP and CPU memory, and
reports which code writes where. Every address in `rom_map.yml` was found with it.

```bash
make emu                                   # -> build/emu/headless_gpgx
ga3 emu emu/scenes/menu_verify.txt         # runs against build/ga3.bin
build/emu/headless_gpgx --rom build/ga3.bin --script emu/scenes/title.txt
make regress                               # every scene in emu/scenes/
```

Command line: `--rom FILE` (required), `--script FILE` (`-` reads stdin),
`--frames N` (run this many frames when there is no script), `--png FILE`
(screenshot at the end), `--scale N`, `--quiet`. `ga3 emu SCRIPT` supplies
`--rom build/ga3.bin` and passes anything after the script through.

## The core

`emu/gpgx` is a git submodule on the `ga3/dma-hook` branch of
[eugenez36/Genesis-Plus-GX](https://github.com/eugenez36/Genesis-Plus-GX):
upstream `27426f0` plus one commit adding a `dma_hook` function pointer under
`#ifdef HOOK_CPU` (`emu/patches/0001-dma-hook.patch`, 14 lines). Nothing else in
the core is modified; `make -C emu/headless check-core` verifies the hook is
present. Objects go to `build/emu/obj/`, the core tree stays clean.

## Script commands

Scripts are line oriented, `#` starts a comment, arguments cannot contain
spaces, at most three are read.

| Command | Meaning |
|---|---|
| `include PATH` | run another script here; relative to the including file, nesting ≤ 8 |
| `wait N` | advance N frames (60 per second) |
| `press BTNS [N]` | press for N frames, release for N (default 6) |
| `hold BTNS N` | hold for N frames |
| `pad2 BTNS [N]` | the same on the second pad |
| `screenshot PATH [S]` | PNG, integer scale S; directories are created |
| `dump WHAT PATH` | `vram cram vsram wram zram sat satvram regs` |
| `watchlog PATH` | file for watchpoint / breakpoint / DMA lines |
| `watch ADDR LEN [NAME]` | 68000 write watchpoint (hex address **and** length) |
| `vwatch ADDR LEN [NAME]` | VRAM write watchpoint, including DMA (logs `dma_src`) |
| `bp ADDR` | dump A0–A6 / D0–D3 whenever ADDR executes |
| `dmalog on\|off` | log every DMA transfer with its source |
| `clearwatch` | remove RAM and VRAM watchpoints (breakpoints stay) |
| `poke8 / poke16 ADDR VAL` | patch Work RAM (hex, 68000 address; the byte swap is handled) |
| `state save\|load PATH` | savestate |
| `reset`, `status`, `echo`, `quiet` | |

Buttons: `up down left right a b c x y z start mode`, joined with `+`.

## Scenes and exploration

`emu/scenes/` holds regression scenes (deterministic, named outputs under
`build/shots/` and `build/dumps/`); shared prefixes are `_*.inc` files pulled in
with `include`. `emu/explore/` keeps the one-off runs that produced the
findings, documented in its README.

## Three Genesis Plus GX pitfalls

They cost half of the debugging time, so they are written down:

1. **VRAM and the sprite table are stored byte-swapped** on little-endian hosts
   (`*(uint16*)&vram[i] = data`). The dumper writes honest big-endian.
2. **Work RAM is byte-swapped too** (`READ_BYTE` is `BASE[ADDR ^ 1]`): dump
   offset `O` is 68000 address `FF0000 | (O ^ 1)`. `ga3 ramsearch` compensates.
3. **DMA copies do not call `cpu_hook`.** Hence the `dma_hook` commit — without
   it the source of graphics uploads cannot be found.

Also: the game addresses RAM as `FFFFxxxx` while the bus carries 24 bits, so
watchpoints mask addresses with `FFFFFF` and account for access width.
CRAM is stored in GPGX's packed 9-bit little-endian form;
`ga3.palette.gpgx_cram_to_words()` turns a dump into standard CRAM words.

## Finding a variable: the HP example

1. `emu/explore/hp.txt` walks right for 26 steps saving a Work RAM dump and a
   screenshot each time.
2. Measure the health bar length on the screenshots.
3. `ga3 ramsearch corr 'build/dumps/explore/hp/w*.bin' 51,51,50,…` — `FFC8E6`
   correlates at r = 1.0 (`--limit`, `--min-distinct` and `--threshold` go
   after the mode; `value` and `decreasing` are the other modes).
4. `emu/explore/hpwatch.txt` (`watch FFC8E6 2`) lists the writers: `00EA20`
   during play, and `00E48C` once at start — the one that reads the table.
5. `ga3 disasm E482 -n 12` shows `move.b $e492(pc,d0.w),d0` — the table.

Lives, magic and timers have not been found yet; the method is the same.
