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
heard, from breakpoints on `00E4BA` (`SOUND` after it saves `a6`, `d0` = ID)
and `0F091C` (the driver picking a song) while a bot plays every stage
(level select by poke, player immortal, enemies at 1 HP; the recipe of
`emu/scenes/kill_counter.txt`). The last column is what `ga3 balance set`
edits.

| ID   | Where                                                      | Started by                                        | Edit                                                      |
|------|------------------------------------------------------------|---------------------------------------------------|-----------------------------------------------------------|
| `81` | after leaving the options screen (C on the last item)      | menu code in RAM, through `00EC4E`                | —                                                         |
| `82` | stage 7; duel arena 4                                      | `00E56C`                                          | `stage_music`                                             |
| `83` | hero select; also heard between fights of a duel           | menu code in RAM, through `00EC4E`                | —                                                         |
| `84` | a duel fight won: against the computer; a two-player fight | `00DBC4`; `00DC20`                                | `duel_won_song`                                           |
| `85` | stage 4A                                                   | `00E56C`                                          | `stage_music`                                             |
| `86` | stage 1; duel arena 1                                      | `00E56C`                                          | `stage_music`                                             |
| `87` | stage 6A                                                   | `00E56C`                                          | `stage_music`                                             |
| `88` | stage 3B; duel arena 2                                     | `00E56C`                                          | `stage_music`                                             |
| `89` | stage 4B                                                   | `00E56C`                                          | `stage_music`                                             |
| `8A` | stage 2B                                                   | `00E56C`                                          | `stage_music`                                             |
| `8B` | stage 2A                                                   | `00E56C`                                          | `stage_music`                                             |
| `8C` | stage 8                                                    | `00E56C`                                          | `stage_music`                                             |
| `8D` | the ending's text pages                                    | `00DFDE`                                          | `ending_song`                                             |
| `8E` | title and main menu (from frame 269 after power-on)        | menu code in RAM, through `00EC4E`                | —                                                         |
| `8F` | a stage cleared                                            | `00D9F8`                                          | `stage_clear_song`                                        |
| `90` | the screen before a stage («ЭТАП 2», score, the path)      | menu code in RAM, through `00EC4E`                | —                                                         |
| `91` | stage 3A                                                   | `00E56C`                                          | `stage_music`                                             |
| `92` | stage 5A; duel arena 3                                     | `00E56C`                                          | `stage_music`                                             |
| `93` | stage 5B                                                   | `00E56C`                                          | `stage_music`                                             |
| `94` | boss of stages 2B, 4B, 5A, 5B, 6B                          | a stage event                                     | `boss_song_2b` …                                          |
| `95` | stage 8: the final boss; the lightning; its second form    | a stage event; `00BA56`; `00E56C` (`$C778 = $12`) | `boss_song_8`, `lightning_song`, `stage_music.special_12` |
| `96` | stage 8: outside the castle with the freed prisoners       | `00DD56`                                          | `castle_song`                                             |
| `97` | stage 8: the first form falls; the castle falls            | `00B06A`; `00DF2C`                                | `boss_8_fall_song`, `castle_fall_song`                    |
| `99` | stage 6B                                                   | `00E56C`                                          | `stage_music`                                             |
| `9A` | game over; a duel against the computer lost                | `00D890`; `00DBCA`                                | `game_over_song`, `duel_lost_song`                        |
| `9B` | boss of stages 1, 2A, 3A, 3B, 4A, 6A                       | a stage event                                     | `boss_song_1` …                                           |

`stage_music.special_11` (`82`) is never heard: both scenes that set
`$C778 = $11` start their own song (`96`, `97`).

Proof: the bot runs (frames in the map's `evidence`), `emu/scenes/game_over.txt`
(`9A` at frame 6585), `emu/scenes/options_extra_life.txt` (`81`, frame 2801),
`emu/scenes/duel_two_players.txt` (`84` from `00DC20` at frame 4394; a
two-player duel is one fight, the title follows). The bosses of 3A, 4B, 5A and
5B were not reached by the bot: their entries are known from the event lists
alone (below). Stage 7 has no song event at all (its lists are `0EE7F0` and
`0EE7FA`); what its boss plays is not known yet. The title, the menus and the
screen before a stage run from code decompressed to RAM (`00EC3C`); it calls
`SOUND` through the vector `00EC4E` (`bra.w $e4b2`, a breakpoint on it fires
for `8E`, `83` and `90`), so those IDs are not in the ROM as plain bytes. That
`83` between duel fights comes the same way is not checked.

The options sound test (МУЗ.) plays `0154A4[n]`: `81–97`, `99–9B` (26
songs; `98`, the duplicate, is skipped).

Every `Edit` name is a constant with `range: [0x81, 0x9B]` in
`assets/data/gameplay.yml` (or the table `stage_music`, below):

```sh
ga3 balance set boss_song_1 0x8E   # the title's song for the boss of stage 1
make
```

Checked in the emulator: with `0x8E` the boss of stage 1 starts `0F5EFC`, the
title's song (`bp 0F091C`, frame 18230).

## A boss's song

The boss's song is not in the code: it is a stage event. A stage's events are
8-byte entries `[long, long]` in two lists, both indexed by `$C778` (a word
offset) and then by the section `$C77A` (a long pointer): objects at
`0EC866` (read by `00C15A`) and scripts at `0EC90A` (`00BDF2`). An object
list is entries up to `FFFF`; a script section is a word table of scripts, a
script is words (offsets of its waves, `FFFC`–`FFFF` end it), and a wave is a
word (delay, count) and `count` entries (`00C0A4`). The low six bits of the
second long are a command; `00C228` jumps through `00C244`, and command 3 is
`00C2F0: bra SOUND`: play the sound whose ID is the low byte of the first
long. So `[.. .. 00 9B][00 00 00 03]` starts song `9B` when the camera
reaches the entry. The stages' lists hold 16 such song entries, one or two a
stage (two when the stage's sections fork); `9B` and `94` are the two boss
songs, `95` the final boss's. Two more command-3 entries are not songs of a
stage: `0EEA12` in stage 5A plays sound `04`, an effect, and `0EE7FE` (`94`)
is the first entry of the castle scene's list (`$C778 = $11`), which the
stage 8 bot run passes without it being played. Stage 6A shares its lists
with the four duel arenas (`$C778 = $0C`–`$10`), so its boss entry is in
theirs too; no duel run has played it. `tests/test_sound_rom.py` walks the
lists as the game does and checks that every `boss_song_X` names exactly the
song entries of stage X.

## The end of stage 8

The order, with `$C766` (the game mode, `00D5CC` jumps through `00D5E0`):
the final boss (`95`, `boss_song_8`) → it falls, «Сны становятся явью!»
(`97`, `00B06A`) → mode `0F`, `10`: `$C778 = $11`, outside the castle with the
freed prisoners (`96`, `00DD56`) → mode `11`: lightning, the sky darkens
(`95`, `00BA56`) → mode `12`: `$C778 = $12`, the throne room and the second
form (`95`, `stage_music.special_12`) → modes `13`–`17`: the castle falls (`97`,
`00DF2C`) → mode `18`, once a page: the ending text (`8D`, `00DFDE`) → mode
`19`.

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
