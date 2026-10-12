# Code patches

Three kinds of change go beyond text, font and tables. All of them are
`patch` segments in `rom_map.yml`: they own a slot carved out of verified free
space, and they change a few bytes of the game's code elsewhere, each checked
against what the base ROM holds there before anything is written.

| Patch          | What it does                                                             | Kind                                           |
|----------------|--------------------------------------------------------------------------|------------------------------------------------|
| `menu_version` | `V x.y.z` at the bottom right of the main menu                           | routine in `ga3.patches`                       |
| `menu_items`   | main-menu items 8 characters wide (`1 ИГРОК / 2 ИГРОКА / ДУЭЛЬ / ОПЦИИ`) | routine in `ga3.patches`                       |
| `kill_counter` | enemies killed by each player, next to their HUD                         | assembled from `assets/patches/kill_counter.s` |

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

Each subtracts as before and marks the enemy with the player who hit it (a
byte at `+0x15D` of the object, which the game itself never writes and clears
with the object). The kill goes to the marked player, to 99, in their byte at
`FFC3E0`/`FFC3E1`:

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
frame) and appends a 2 x 1 sprite just right of the magic boxes. The list is
never walked: the game adds sprites in order (sprite n links to n+1) and keeps
their number in `FFEE70`, which its own end-of-list code (`000044`) uses too.
A duel has no enemies to count, so there the counters are not drawn at all:
the game mode (`FFF176`) is 2 for a duel against the computer and 3 once
player 2 joins it, against 0 and 1 for the one- and two-player games.
The two digit tiles per player go to VRAM `D700` only when the number differs
from the one they hold (`FFC3E2` / `FFC3E3`, set to `FF` whenever the HUD is
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
players the digit tiles in VRAM match both counters, also for 10 and 99.
The HUD art check was verified on VRAM dumped every frame across a spell and a
stage start of a 2-player game: the digits never show without the HUD art.
In a duel against the computer and against player 2 both HUDs are drawn and
no counter is (`emu/scenes/duel_hud.txt`); switching the mode to a duel and
back in a running 1-player game hides the counter and brings it back with the
right digits, because hiding also clears the record of the digits shown.
