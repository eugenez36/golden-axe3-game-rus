# Code patches

Three kinds of change go beyond text, font and tables. All of them are
`patch` segments in `rom_map.yml`: they own a slot carved out of verified free
space, and they change a few bytes of the game's code elsewhere, each checked
against what the base ROM holds there before anything is written.

| Patch          | What it does                                                                 | Kind                                                                          |
|----------------|------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| `menu_version` | `V X.YY.ZZZ` at the bottom right of the main menu                            | routine in `ga3.patches`                                                      |
| `menu_items`   | main-menu items 8 characters wide (`1 ИГРОК / 2 ИГРОКА / ДУЭЛЬ / ОПЦИИ`)     | routine in `ga3.patches`                                                      |
| `kill_counter` | enemies killed by each player, next to their HUD                             | assembled from `assets/patches/kill_counter.s`                                |
| `hero_panel`   | the hero stats panel on the character select                                 | assembled from `assets/patches/hero_panel.s`, data from `data/hero_panel.yml` |
| `difficulty`   | a third difficulty, «ЖЕСТЬ)»: the hard enemy set, every ordinary enemy twice | assembled from `assets/patches/difficulty.s`, names in `text/difficulty.txt`  |

After a build the pipeline checks that no later segment overwrote a patch's
slot or edits (a text record covering code did exactly that once).

## Assembled patches

A patch written in 68000 assembly lives in `assets/patches/NAME.s` and is
defined once under the top-level `patches:` key of `rom_map.yml`:

```yaml
patches:
  kill_counter:
    source: patches/kill_counter.s
    symbols: { HP: 0x142, P1: 0xC7A4, ... }          # every address the source uses
    hooks:                                           # per section: [address, base bytes, label]
      count: [[0x000E04, "93 28 01 42 6A 04", melee_a0], ...]
    glyphs: { section: tiles, art: gfx/font/font.txt, chars: "0123456789 ", ink: 0x06, bg: 0x0C }
segments:
  - { name: kill_counter_count, start: 0x011716, end: 0x011800, type: patch, fill: 0xFF,
      patch: kill_counter, section: count }
```

Each `section NAME` of the source is placed at the start of the segment with
that `section:`; a hook replaces the six bytes it names with `jmp label.l`.
`strings: { section, path, label }` puts the records of a strings file (the
usual `OFFSET:LENGTH | text`, offsets inside that section's slot, in order from
its start) at `label`, each padded with spaces to its length; `ga3 text
verify/lint/preview` check the file like any other.
The source holds no address of its own. `ga3.m68k` assembles it: a two-pass
assembler for the instructions and addressing modes these patches use, Motorola
syntax, local `.labels`, `dc.b`/`dc.w`/`even`/`section`. Every supported form
is checked by disassembling the output with Capstone (`tests/test_m68k.py`).

## Kill counter

**Counting.** Hit points are a byte at `+0x142` of each object (slots `0x160`
apart; player 1 at `FFC7A4`, player 2 at `FFC904`, enemies from `FFCA64`). Three
places take hit points away and now jump to the patch:

| Hook     | Victim                    | Attacker                                                 |
|----------|---------------------------|----------------------------------------------------------|
| `000E04` | `a0`                      | `a1` (hits)                                              |
| `000E74` | `a1`                      | `a0` (hits)                                              |
| `00F8BC` | `a0`                      | the caster in `$DC4E`: 0 player 1, 1 player 2 (magic)    |
| `00C7F8` | `a0` (object being freed) | the mark: counts an enemy that fell after a player's hit |

Each subtracts as before — and decides death as the game does: the game's
`bpl` clears HP when the result has bit 7 set; the patch uses `bhi` (HP was
above the damage, unsigned), which agrees for every HP the game allows
(0–`0x7F`) and every damage up to `0x80`. (An earlier `bgt` read an overflow,
HP 75 hit for 128, as a living hero with HP 203.) Each also marks the enemy
with the player who hit it (a
byte at `+0x15D` of the object, which the game itself never writes and clears
with the object). The kill goes to the marked player, up to 999, in their word
at `FFC3E0` (player 1) / `FFC3E2` (player 2):

- when the enemy's hit points run out (the three hooks above), or
- when the enemy's object is freed while it still has hit points: it fell off
  the stage after a player's hit (hook on the object clear routine `00C7F8`;
  seen on stage 5A, where an enemy knocked off a ledge is freed with HP left).

An enemy no player hit counts for nobody, also when it falls by itself. An
enemy that leaves the screen alive after a player's hit would count as well;
none was seen doing that on the 13 stages. The counters live in Work RAM the
game never writes after boot (watched over the stages); choosing a game mode in
the main menu (`014FF6`) clears them, so they carry over from stage to stage.

**Display.** Before the game waits for VBlank (`00F006`) the patch looks for
the third HUD block of each player present (tiles `33E` / `36A`, 4 x 3 cells)
among the first 8 sprites of the sprite list (`FFE5CA`, DMA'd to the SAT every
frame) and appends a 3 x 1 sprite just right of the magic boxes: three digits
for each player, right-aligned with blanks for missing leading digits
(`  7`, ` 42`, `999`). The list is
never walked: the game adds sprites in order (sprite n links to n+1) and keeps
their number in `FFEE70`, which its own end-of-list code (`000044`) uses too.
A duel has no enemies to count, so there the counters are not drawn at all:
the game mode (`FFF176`) is 2 for a duel against the computer and 3 once
player 2 joins it, against 0 and 1 for the one- and two-player games.
The three digit tiles per player (`6B8–6BA` for player 1, `6BB–6BD` for
player 2, at VRAM `D700`) are uploaded only when the number differs from the
one they hold (words `FFC3E4` / `FFC3E6`, set to `FFFF` whenever the HUD is
not shown, so they are uploaded again when it comes back). The digits are the
dialogue font's own glyphs, packed to 1 bit a pixel at build time, drawn in
palette 0's white on blue like a dialogue box. `D700-DFFF` (the unused window
table) is written by nobody once a stage has started on any of the 13 stages;
the title and menus use it, which is why the tiles are uploaded again whenever
the HUD reappears.

A counter is drawn only once its HUD's art is in VRAM: the patch reads back the
first word of each of the player's three HUD blocks (every block starts with a
non-zero border row). A spell clears the HUD tiles, and when it ends the game
puts the HUD sprites back 6-12 frames before it has reloaded their art, block
by block; a stage start loads the art late in the same way. Without the check
the digits showed alone next to an empty HUD for those frames.

**Checked.** `emu/scenes/kill_counter.txt` (hits), magic kills, a 2-player game
(each player's kills go to their counter), all 13 stages through the level
select (`A A A A START C C C C C C` on the character select), the reset, and
`ga3 lag` on `emu/scenes/stage1_fight.txt`: 233 of 3438 frames lost, the same
as without the patch. A busy 2-player fight on stage 6A, replayed from one
savestate with the same input, loses 64 frames in 1239 against 47 without it.
(The first version walked the whole list and redrew the digits every frame:
297 there, a visible slowdown.) After bot play on all 13 stages with two
players the digit tiles in VRAM match both counters, also for 7, 42, 100, 105
and 999 (`emu/scenes/kill_counter_999.txt`: one player from 998 stops at 999
after live kills; two players show 7 / 105 and 999 / 999). Three digits
(words, two divisions) did not change `ga3 lag`: still 233 of 3438 on
`stage1_fight`, 62 in 1239 on the 6A fight.
The HUD art check was verified on VRAM dumped every frame across a spell and a
stage start of a 2-player game: the digits never show without the HUD art.
In a duel against the computer and against player 2 both HUDs are drawn and
no counter is (`emu/scenes/duel_hud.txt`); switching the mode to a duel and
back in a running 1-player game hides the counter and brings it back with the
right digits, because hiding also clears the record of the digits shown.

## Hero stats panel (`hero_panel`)

On the character select the hero under each player's cursor gets a panel over
the title: name, magic, then health, hit / super, tempo and walking speed, each
with a bar (variant B of the mock-ups). One full-width panel (40 × 8 cells) in a
one-player game, a half panel (20 × 9) per player in a two-player game, none on
the duel select (`MODE` ≥ 2).

**Hook.** The select screen's cursor routine (`0161F0–0162A6`) runs once a frame
for each player's cursor block (`FFF300`, `FFF380`) and stores the cursor at
`016278`; the patch replaces that `move.w d0,$14(a0)` and the `mulu.w #6,d0`
after it, does both, and returns to `016280`.

**Drawing.** `src/ga3/hero_panel.py` renders every panel at build time from the
font art and `data/hero_panel.yml` into palette 0's colours (white 6 on blue 12,
the dialogue font's own; yellow 13 and black 9 for the bars), cuts it into
8 × 8 tiles (64, de-duplicated) and tilemaps per hero. The patch copies the tiles
to VRAM `3C40` (118 free tiles on this screen, never written from boot to the
end of the select) and writes the hero's tilemap into plane A (`C000`) over the
title. It draws only when the hero changed, the tiles are not in VRAM (the first
word of tile 0) or plane A no longer holds the panel's corner, so the panel
comes back when the game redraws the screen; interrupts are off while it talks
to the VDP. `SHOWN` (`FFC3E8`, one byte a player) is in the RAM range the game
never writes.

**Numbers.** From `docs/heroes.md`: `tests/test_hero_panel.py` checks hp, hit,
super and speed against the attack table, the walk table and the HP table of
the ROM; tempo (seconds between combo hits) is a measurement. Edit the names,
labels or values in `data/hero_panel.yml` and rebuild.

**Checked.** `emu/scenes/hero_select_stats.txt`: the four heroes alone, two
pairs with two players, the duel without a panel; the stage that follows starts
clean; `ga3 lag` on `stage1_fight` unchanged (233 of 3438).

## Difficulty «ЖЕСТЬ)» (`difficulty`)

OPTIONS → СЛОЖНОСТЬ has three values: ОБЫЧНО, ТРУДНО and **ЖЕСТЬ)**: the
enemies of ТРУДНО, and every ordinary enemy comes twice. The screen still holds
at most four enemies (four enemy slots, each with its own VRAM area), so the
fights get longer, not more crowded.

**What the game does.** The difficulty is the byte `$FFC726` (0 normal, 1 hard;
kept over a soft reset at `0002CC`). Its only reader in play is the spawn walker
(`00C1BE`): an entry of the stage's spawn data has a level (bits 31..30 of its
second long), and it is skipped when that level is above the difficulty (plus
one while both player objects exist, `$C408` = 3; 0 in the attract demo,
`$C718` bit 0). So ТРУДНО is ОБЫЧНО plus the level-1 entries, nothing else.

**Menu** (`0152E4`, reached by `bsr` with `d1` = −1, 0, +1): the value now wraps
over 0..2 both ways and its name, six characters, comes from
`text/difficulty.txt` (the old strings at `015318` are no longer read).

**Level** (`00C1BE`): the difficulty counts as at most 1, so ЖЕСТЬ) spawns
exactly the entries of ТРУДНО.

**Twice.** At ЖЕСТЬ) (not in the demo), once a plain entry of an ordinary type
(`10 12 14 16 18 1A 1C 2C 34 36 38`, handler `007954`) got an enemy slot
(`00C1FE`), the entry goes into a queue once more, with the X the game just
gave it as its absolute position, so the copy comes in where the original did
(a spot the stage's own data chose; the opposite edge put copies into walls).
Bosses (`32`, `2E`, `1E`), riders (commands 07/08) and command entries are
never doubled; an enemy a command handler spawned is copied as a plain enemy.
Every frame (`00BDBA`, the spawner's frame routine, not run while magic plays)
the oldest queued entry goes through the game's own spawn routine (`00C0FE`) as
soon as an enemy slot is free. The game drops an entry that finds no free slot
(`00C1F6`); at ЖЕСТЬ) an ordinary one is queued instead, with its copy, so the
copies never cost an original. A queued entry is not tested for its level again
(it passed when it came up; the two-player bonus may have changed since).
While entries wait, the wave is not cleared (`00C66E`) and the stage end does
not see an empty screen (`00C650`): the next wave and the scroll wait for them.
The routine that clears the game state at a stage start (`00E552`) empties the
queue.

The queue (16 entries of 8 bytes, a ring) lives at `FFBF00`: `FFBCC0–FFBFFF` is
written only by the RAM clear at power-on (watched over all 13 stages). Two
places that looked free were not: `FFC480–FFC5FF` is the Nemesis decoder's
table, rebuilt at every decompression, and `FFC600–FFC700` is the stack.

**Checked.** `emu/scenes/difficulty.txt`: the menu both ways and stage 1 with
four enemies on screen and copies waiting. With a bot (player kept alive) on
stage 1, every ordinary enemy came exactly twice (41 pairs, the boss once); on
the 13 stages through the level select, ЖЕСТЬ) finished every stage the same
bot finished on ТРУДНО, and the stages it did not finish stopped the same way
on ТРУДНО. The demo spawns the same enemies at the same frames as without the
patch. ОБЫЧНО and ТРУДНО spawn the same enemies as before. Lag on stage 1: 2.5 %
of frames lost on ЖЕСТЬ) against 1.0 % on ТРУДНО (more often four enemies at
once).
