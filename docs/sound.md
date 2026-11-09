# Sound

All of the game's sound is one bank, `0F0000–0FFA10`, laid out as SEGA's
SMPS 68k (the driver of Sonic 1): the 68000 plays music and SFX itself
(driver RAM `FFC000`, update `0F0202` once a frame), the Z80 only plays DAC
samples (`z80_driver`, 406 bytes, copied to the Z80 at boot). Segment by
segment: [rom_map.md](rom_map.md) (`snd_*`, `z80_driver`, `dac_table`,
`pcm`); samples: [assets/sound/pcm/README.md](../assets/sound/pcm/README.md).

## Songs

A sound is queued by `SOUND` (`00E4B2`, `d0.b` = ID); IDs `81–9B` are songs
(`snd_music_index`, 27 pointers; `97` and `98` are one song). Where each is
heard, from breakpoints on `0F091C` (the driver picking a song) and on the
`SOUND` calls with a constant ID:

| ID   | Where                                                 | Proof                                           |
|------|-------------------------------------------------------|-------------------------------------------------|
| `81` | after leaving the options screen (C on the last item) | `emu/scenes/options_extra_life.txt`, frame 2801 |
| `82` | stage 7; duel arena 4                                 | `stage_music`                                   |
| `83` | hero select                                           | every scene through the menu                    |
| `84` | called at `00DBC4`, `00DC20`                          | disassembly only                                |
| `85` | stage 4A                                              | `stage_music`                                   |
| `86` | stage 1; duel arena 1                                 | `stage_music`, `emu/scenes/duel_hud.txt`        |
| `87` | stage 6A                                              | `stage_music`                                   |
| `88` | stage 3B; duel arena 2                                | `stage_music`                                   |
| `89` | stage 4B                                              | `stage_music`                                   |
| `8A` | stage 2B                                              | `stage_music`                                   |
| `8B` | stage 2A                                              | `stage_music`                                   |
| `8C` | stage 8                                               | `stage_music`                                   |
| `8D` | called at `00DFDE`                                    | disassembly only                                |
| `8E` | title and main menu (from frame 293 after power-on)   | every scene                                     |
| `8F` | called at `00D9F8`                                    | disassembly only                                |
| `90` | after the game over                                   | `emu/scenes/game_over.txt`, frame 6974          |
| `91` | stage 3A                                              | `stage_music`                                   |
| `92` | stage 5A; duel arena 3                                | `stage_music`                                   |
| `93` | stage 5B                                              | `stage_music`                                   |
| `94` | —                                                     | not heard yet                                   |
| `95` | `special_12` in `stage_music`; called at `00BA56`     | disassembly only                                |
| `96` | called at `00DD56` (after `$C778 = $11`)              | disassembly only                                |
| `97` | called at `00B06A`, `00DF2C` (after `$C778 = $11`)    | disassembly only                                |
| `99` | stage 6B                                              | `stage_music`                                   |
| `9A` | game over (`00D892`); also called at `00DBCA`         | `emu/scenes/game_over.txt`, frame 6585          |
| `9B` | —                                                     | not heard yet                                   |

The options sound test (МУЗ.) plays `0154A4[n]`: `81–97`, `99–9B` (26
songs; `98`, the duplicate, is skipped).

## A stage's song

`00E56C` plays `stage_music[$C778]` when a stage starts (also after a
continue). `$C778` is not the stage's order: the level select's cursor goes
through `00EE72` to `$C776`, and `00D686` turns that into `$C778`; a duel sets
it from `00054A` (arenas 1–4). The table `stage_music` (`00E578`, 19 bytes,
`assets/data/stage_music.yml`) is named by what the level select shows, so

```sh
ga3 balance set stage_music.stage_1 0x8E   # the title's song on stage 1
make
```

The map gives the table `range: [0x81, 0x9B]`: anything else is refused by
`ga3 balance set` and by the build, because the driver would read a song
pointer from outside its index. Checked in the emulator: with `0x8E` stage 1
starts with the title's song (`bp 0F091C`, `a4 = 0F5EFC`).
