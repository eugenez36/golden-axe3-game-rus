# The four heroes: every parameter, where it lives, what it allows

Everything here was traced in the code and confirmed in the headless emulator;
values that are not proven are marked so. Addresses are ROM offsets of the
base image unless they start with `FF` (Work RAM, 68000 view). Speeds are
signed 8.8 fixed-point words: pixels per frame × 256 (`0x0190` = 1.5625).

## Who is who

| Select cursor (`FFF315`) | Hero                                                                                                                                                 | Class id (object `+0x131`) |
|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------|
| 0                        | Chronos Lait (panther-man)                                                                                                                           | 3                          |
| 1                        | Kain Grinder (barbarian, the default)                                                                                                                | 2                          |
| 2                        | Sarah Barn (amazon)                                                                                                                                  | 4                          |
| 3                        | Proud Cragger (giant)                                                                                                                                | 0                          |
| 4 (duel only)            | the winged, eagle-headed beast-man: the fifth fighter of the duel select; the 1-player select cannot reach it (the old man in its middle is scenery) | 1                          |

The ROM holds no hero names; the full names are those of the original
game's manual. The select screen turns the cursor into the class with the
byte table at `0x160FA` (`04 03 05 01 02` = class + 1). Every per-hero table
below is indexed by the class id; classes 5–14 are enemies and share the same
tables.

## At a glance

What differs between the heroes, and what does not:

|                                                   | Proud       | Kain        | Chronos    | Sarah       |
|---------------------------------------------------|-------------|-------------|------------|-------------|
| Magic                                             | earth       | water       | storm      | fire        |
| Combo hit / finisher / launch (power; damage = ½) | 8 / 16 / 24 | 6 / 12 / 18 | 4 / 8 / 12 | 5 / 10 / 15 |
| First hit lands (frames after the press)          | 9           | 7           | 9          | 11          |
| Whole 3-hit combo (frames)                        | 79          | 77          | 57         | 47          |
| Walk / dash speed (px per frame)                  | 1.375 / 3   | 1.5625 / 4  | 2.0 / 5    | 1.75 / 4    |
| Jump height (standing / dash)                     | 64 / 88 px  | 68 / 93 px  | 69 / 95 px | 69 / 95 px  |
| Jab reach                                         | 64 px       | 76 px       | 70 px      | 68 px       |

The same for all four: HP 51 at the start (75 at the top level), magic
damage 6 / 16 / 32 (56 for the team spell), potions 0…6 at the start (OPTIONS → БАНКИ МАГИИ, default 0; base game 1), up to 6 by pick-ups, defence, recovery,
2 spare lives.

The player objects are `FFC7A4` (player 1) and `FFC904` (player 2), `0x160`
bytes each.

Editable by name (`ga3 balance show`): the walking speeds are the table
`walk_speed` (`data/walk_speed.yml`), the dash, jump and air speeds
`move_speed` (`data/move_speed.yml`), the first combo hit and the launch of
each hero the constants `KEY_hit` / `KEY_super` and the spells' damage
`magic_l0` … `magic_team`, `enemy_magic` (`data/gameplay.yml`); `ga3 balance
set walk_speed.kain_x 0x200`, `ga3 balance set kain_super 20`. The hero panel
of the character select reads the same files.

## Movement

The physics step `002C14–002CA0` runs every frame for three axes (height,
depth, X) of velocity / acceleration / limit / position / fraction; the
fixed-point add at `002E70` keeps the whole-pixel part as a signed byte.
X position is object `+0x2E` (word, pixels), its fraction `+0x32`.

| Parameter                     | Where                                                                            | Proud          | Kain            | Chronos      | Sarah         | Class 1      |
|-------------------------------|----------------------------------------------------------------------------------|----------------|-----------------|--------------|---------------|--------------|
| Walk speed X                  | `0x337E6 + class×4`, high word (read at `0070B6–0070E0`): `walk_speed.KEY_x`     | `0x0160` 1.375 | `0x0190` 1.5625 | `0x0200` 2.0 | `0x01C0` 1.75 | `0x0180` 1.5 |
| Walk speed in depth (up/down) | same entry, low word: `walk_speed.KEY_depth`                                     | `0x0100` 1.0   | 1.0             | 1.0          | 1.0           | 1.0          |
| Dash speed X                  | `0x337FA + class×2` (row 0, read by `003BE8`): `move_speed.dash_KEY`             | `0x0300` 3     | `0x0400` 4      | `0x0500` 5   | `0x0400` 4    | `0x0680`     |
| Jump velocity up              | `0x33818 + class×2` (row 1, used at `004B74`): `move_speed.jump_KEY`             | `0x05C0`       | `0x05F0`        | `0x0600`     | `0x0600`      | `0x0600`     |
| Dash-jump velocity up         | `0x33836 + class×2` (row 2): `move_speed.dash_jump_KEY`                          | `0x06C0`       | `0x06F0`        | `0x0700`     | `0x0700`      | `0x0700`     |
| Steering in the air           | `0x33854 + class×2` (row 3, only while left/right is held): `move_speed.air_KEY` | `0x0200` 2     | 2               | 2            | 2             | 2            |

Rows of `0x337FA` are 15 words (classes 0–14), `0x1E` bytes apart.

Measured in the emulator (original ROM): walking 1.359 / 1.564 / 2.000 /
1.769 px per frame for Proud / Kain / Chronos / Sarah; dashing exactly 3 / 4 /
5 / 4 px per frame; a standing jump peaks at 64 / 68 / 69 / 69 px after
22–23 frames (44–46 frames in the air), a dash jump at 88 / 93 / 95 / 95 px
(52–54 frames). Diagonal walking is not normalised: X and depth both move at
full speed.

Shared by every hero (single constants in the code):

| Parameter                    | Where                                                | Value                                                                   |
|------------------------------|------------------------------------------------------|-------------------------------------------------------------------------|
| Gravity                      | `008B92`: `$FFC0` → `+0x1A` (operand at `0x8BA0`)    | −0.25 px/frame²                                                         |
| Fall speed limit             | `$F980` → `+0x1C` (operand at `0x8B9A`)              | −6.5 px/frame                                                           |
| Double-tap window for a dash | byte at `0x795` (`cmpi.b #$1E,$151(a0)` at `000792`) | 30 frames                                                               |
| Dash allowed                 | byte table `0x74C + class` (read at `00075E`)        | 0 for all heroes (non-zero disables the dash; enemies 12 and 13 have 1) |

### Valid values

Tested on patched copies of the image (Kain unless stated):

| Parameter          | Format allows                     | Works in game                                                             | What happens outside                                                                                                                                                                                        |
|--------------------|-----------------------------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Walk speed X       | signed 8.8, −128…+127.99 px/frame | `0x0001`–about `0x1000` (16 px/frame); `0x0320` doubles the speed cleanly | 0: cannot walk sideways; negative: controls reversed; the screen-edge check runs after the step, so from about `0x3000` the hero leaves the screen; `0x8000`/`0x7FFF` break the arithmetic (sign, overflow) |
| Depth speed        | same                              | `0x0001`–`0x0800`                                                         | from `0x0900` the hero walks through the back wall                                                                                                                                                          |
| Jump velocity      | same                              | about `0x0100`–`0x0C00` (`0x0BE0`: 276 px high)                           | 0 or negative: never leaves the ground; `0x7F00`: flies off the stage                                                                                                                                       |
| Dash-jump velocity | same                              | as jump (`0x0DE0`: 378 px high)                                           | as jump                                                                                                                                                                                                     |
| Dash speed         | same                              | like walk speed (same screen-edge rule)                                   | as walk speed                                                                                                                                                                                               |
| Air steering       | same                              | `0x0400` doubles the air travel (160 px instead of 90)                    | 0: no steering in the air                                                                                                                                                                                   |
| Double-tap window  | byte, frames                      | 2 … 60 tested (`0x3C`)                                                    | 1: the dash never triggers                                                                                                                                                                                  |
| Dash allowed       | byte                              | 0                                                                         | non-zero: no dash for that class                                                                                                                                                                            |

Not proven: the purpose of RAM `$C72A` bit 2 (it forces walking left at 1.0,
maybe a scripted walk).

## Attacks

### How a hit is made

1. Each animation frame of a hero has a hitbox entry (tables at object `+0x4C`,
   indexed by the sprite frame `+0x14`; Proud `0x3426E`, class 1 `0x344C8`,
   Kain `0x345CA`, Chronos `0x3488E`, Sarah `0x34C36`): the body box and, for
   attacking frames, `[kind, x, y, half-width, half-height, record]`.
2. `007212–007242` looks the record up in the attack table `0x0EED40`: a word
   offset per class → block `[record size][records]`; a hero record is two
   bytes, **type** (→ `+0x72`) and **power** (→ `+0x73`). Enemies (class 5+)
   have 8-byte records: a type and 7 power columns chosen by `+0x82`.
3. A box must exist 3 frames before it can connect; the hit lands on its 4th
   frame. Each new attack instance hits a given victim once.
4. Damage (`000DE6`, `000E56`): `d1 = power + (victim +0x83 & 1)`, the victim
   keeps `d1` in `+0x83`, damage = `d1 >> 1` — **half the power**, the odd half
   carried to the next hit on that victim. There is no defence factor.
5. Clashes: the higher **type** wins, equal types trade hits. Types: `0A` normal,
   `0E` air, `16` low, `1A` B+C, `1E` dash, `20` heavy air, `2E` special,
   `36` guard, `3E` roll, `00` grab. The guard (Back+B held) blocks types up to
   `0x36`.

### Power of every move (damage = power ÷ 2)

| Move (input)                                      | Proud                    | Kain        | Chronos     | Sarah       |
|---------------------------------------------------|--------------------------|-------------|-------------|-------------|
| Combo hit 1 and 2 (B, B)                          | 8                        | 6           | 4           | 5           |
| Combo finisher (3rd B, knocks down)               | 16                       | 12          | 8           | 10          |
| Close finisher with Fwd (launch)                  | **24**                   | **18**      | **12**      | **15**      |
| Down+B (low, knocks down)                         | 8                        | 6           | 4           | 5           |
| Dash attack (double-tap, B)                       | 16                       | 12          | 8           | 10          |
| Jump attack (C, then B)                           | 24                       | 12          | 8           | 10          |
| Jump Down+B                                       | 16                       | 18          | 12          | 10 + 10     |
| Dash-jump attack                                  | 24                       | 18          | 12          | 15          |
| B+C (front, then rear)                            | 10 (one box, both sides) | 10 + 10     | 10 + 10     | 10 + 10     |
| Fwd+B+C special                                   | 30                       | 30          | 15 + 15     | 30          |
| Back, Fwd+B+C (Chronos only, a roll with 4 boxes) | —                        | —           | 20          | —           |
| Grab: hold hits (B, up to 3) / throw / jump throw | 5 / 20 / 25              | 5 / 20 / 20 | 5 / 20 / 20 | 5 / 20 / 20 |

The block of each hero: Proud `0x0EEDBE`, Kain `0x0EED5E`, Chronos `0x0EEDEC`,
Sarah `0x0EED8C`, class 1 `0x0EEF4A` (its moves: 6 / 12 / 18, dash jump 18).
The record of the first combo hit and of the launch are the constants
`KEY_hit` / `KEY_super` (`proud_hit` …, `data/gameplay.yml`): Proud records 2
and 6, Kain 6 and 9, Chronos 4 and 7, Sarah 2 and 5 of their blocks. The other
moves keep their own records.
Grab powers come from the tables at `0x006ABA` (hold), `0x006AD6` (throw),
`0x006AF2` (jump throw); a thrown body hitting others does 8 (`001164`).
Records with types `46`, `4A`, `4C` (power 20 and 48, probably attacks while
riding a beast) and a few unreferenced type-`12` records were never reached:
unproven.

### Speed of attacks

Animation scripts are `(frame, duration)` byte pairs ending in `FF xx` (`FE`
loops); duration bits 0–5 are frames (0 means 256), bit 6 is a flag (probably
the combo input window, unproven). Measured from the button press (frames at
60 Hz):

| Hero    | First hit lands | Far combo: hits at | Whole combo until free | Close combo: hits at |
|---------|-----------------|--------------------|------------------------|----------------------|
| Proud   | +9              | +9 / +31 / +69     | 79                     | +9 / +31 / +57       |
| Kain    | +7              | +7 / +27 / +53     | 77                     | +10 / +24 / +42      |
| Chronos | +9              | +9 / +27 / +47     | 57                     | +13 / +33 / +53      |
| Sarah   | +11             | +11 / +27 / +41    | 47                     | +11 / +35 / +59      |

Kain's scripts: hit 1 `0x0333B0`, hit 2 `0x0333BE`, finisher `0x0333C8`; Sarah
`0x03346A…`, Proud `0x033304…`, Chronos `0x033414…` (script pointer tables
`0x332A0` close set, `0x332BE` far set, per class).

Reach (to the victim's centre) = |box x| + box half-width + the victim's half
width: the longest jab reaches Kain 76, Chronos 70, Sarah 68, Proud 64 px.

### Defence and recovery (the same for every hero)

| Parameter              | Where                                                                                                                                        | Value                                                                                                   |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Stagger after a hit    | victim state 1                                                                                                                               | 30 frames, still hittable                                                                               |
| Knock-down             | kind 2                                                                                                                                       | 115 frames from the hit to control (untouchable), then 10 frames of invulnerability (`+0xA9`, `006386`) |
| Launch                 | kind 3                                                                                                                                       | 147 frames                                                                                              |
| After losing a life    | `+0xA8` = 60 (`003ED0`)                                                                                                                      | 60 frames of blinking invulnerability                                                                   |
| Stamina (players only) | `+0x11E`: starts at 1000, +1 every 3 frames; a hit takes power × 4 (× 8 from enemies); under 600 sets "dizzy" (`+4` bit 6) and resets to 520 | the dizzy effect itself is partly unproven                                                              |

### Valid values

| Field                | Format                               | Tested                                                                                                                                                                                           |
|----------------------|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Power                | unsigned byte                        | 0: no damage, still a stagger; 1: 0 then 1; `0x7F`: 63 a hit; `0xFE`–`0xFF`: 127 a hit (a KO from 75). Stock values stay ≤ 48. Up to `0x64` keeps the stamina meter sane (`0x32` on the ×8 path) |
| Type                 | unsigned byte, compared for priority | above `0x36` breaks the guard                                                                                                                                                                    |
| Duration in a script | 6 bits of frames (0 = 256)           | 1: a swing every 8 frames, but a 1-frame box never connects (it needs 4 frames)                                                                                                                  |
| Box x / half-width   | signed / unsigned byte               | Kain's jab half-width 20 → 40 reaches 96 px, as computed; keep ≤ 127                                                                                                                             |

A power of `0xFF` plus the odd-half carry deals 128, which a signed byte reads
as −128: the base ROM's `bpl` then clears HP (a KO); the kill counter's hooks
used `bgt` and left HP at 203 until they switched to `bhi` (PR #25).

## Magic

The same rules and damage for every hero; only the picture differs.

| Parameter            | Where                                                                                                                                                                                                       | Value                                                                               |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| Can cast             | `0052E0`: potions (`+0x140`) ≠ 0, no spell running (`$DC4A` = 0), RAM `$C72A` bit 5                                                                                                                         | —                                                                                   |
| Level and cost       | `00F608–00F624` (thresholds are `cmpi.b` operands, costs `moveq`)                                                                                                                                           | 1–2 potions: level 0, costs 1; 3–5: level 1, costs 3; 6+: level 2, costs 6          |
| Team spell (level 3) | `00F5D2`: both players crossed weapons (`$DC44` = 2, 180-frame window from `00F4EC`) and caster + partner potions ≥ 10                                                                                      | the caster's potions are cleared, the partner pays the rest of 10                   |
| Damage by level      | byte table `0x00F91A` (22 bytes), index `$DC52` = class × 4 + level, plus `0x14` for an enemy caster (20 to each player); constants `magic_l0` … `magic_team` (one value for all classes) and `enemy_magic` | 6 / 16 / 32 / 56 for every hero; hits the four enemy slots from `FFCA64` (`00F8BC`) |
| Effect by level      | byte table `0x00F7CE` (same index) → effect jump table `011C0C`                                                                                                                                             | Proud `08–0B`, Kain `00–03`, Chronos `0C–0F`, Sarah `04–07`                         |
| Sound by level       | table `0x00F942`                                                                                                                                                                                            | Proud `C9–CC`, Kain `C5–C8`, Chronos `D1–D4`, Sarah `CD–D0`                         |

What each spell looks like (emulator frames, all four levels), and a name for
the select screen:

| Hero    | Levels 0 → 2, team                                                      | Name                 |
|---------|-------------------------------------------------------------------------|----------------------|
| Chronos | storm clouds → fog → lightning strikes; a hooded reaper in a storm      | Гроза (lightning)    |
| Kain    | water geysers → hail and ice → a huge waterspout; a flood wave          | Вода (water and ice) |
| Sarah   | fireballs → blazing suns → a dragon skull breathing fire; a falling sun | Огонь (fire)         |
| Proud   | pebbles → rocks and a spiked boulder → huge boulders; a stone golem     | Земля (earth)        |

Valid values: damage bytes `0x00–0x7F`. From `0x80` the subtraction leaves a
"negative" HP that `bpl` turns into 0: an instant kill. The thresholds and
costs are bytes; the team sum is an 8-bit add (potions `FF` + `01` wraps).

## Potions

| Parameter                                  | Where                                                                                                                                   | Value                             | Valid                                                                                                                |
|--------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|----------------------------------------------------------------------------------------------------------------------|
| Potions                                    | object `+0x140` (byte)                                                                                                                  | —                                 | 0–6 shown by the HUD; 7–9 work in play but the HUD draws garbage (its tile table `0x0518EC` is indexed by count × 2) |
| At the start, after a death and a continue | `00E476` sets 1 when the count is 0; patch `options` gives OPTIONS → БАНКИ МАГИИ instead, its default the constant `potions` (`00E47C`) | 0 (base game and attract demo: 1) | 0–6 (`max: 6`); any other count is kept through a death                                                              |
| Cap on pick-up                             | `000A16`: `cmpi.b #6,$140(a1)`                                                                                                          | 6                                 | the HUD limit above                                                                                                  |
| Pick-up                                    | `0009D6`, item kind (`+0x14` of the item) 0                                                                                             | +1                                | —                                                                                                                    |

## Health

| Parameter             | Where                                                                | Value                                                    | Valid                                                                                                                                                                   |
|-----------------------|----------------------------------------------------------------------|----------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| HP                    | object `+0x142` (byte)                                               | —                                                        | `0x00–0x7F`: from `0x80` the first hit clears it (the damage is `sub.b` then `bpl`) and the hero dies                                                                   |
| Max-HP level          | object `+0x144` (byte, 0–3)                                          | 0 at the start for **every** hero                        | an item of kind ≥ 3 adds 1, up to 3 (`0009FA`); a duel sets 3 (`00DB42`)                                                                                                |
| Max HP by level       | `hp_table` `0x00E492` (4 bytes), index = the level, **not the hero** | 51 / 59 / 67 / 75                                        | the HUD bar holds 51 + 8 × level (it has 7 + level cells, `010514`); a larger value draws garbage at the bar's end, so raising the table needs the bar code changed too |
| Healing               | `00E496`: HP = min(HP + gain, table[level])                          | item kind 1: +24, kind 2: +12, kind ≥ 3: +75 and a level | —                                                                                                                                                                       |
| A death or a continue | refills HP to table[level]; the level is kept                        | —                                                        | —                                                                                                                                                                       |

Defence is the same for every hero: the damage a hero takes (`000E56–000E74`)
depends only on the attacker's power (`+0x73`); the victim's class is never
read. Measured from one savestate: the same enemy does 2 / 1 / 2 … to all four.

## Lives and extra lives

| Parameter           | Where                                                                                                                                                                                                                                                                          | Value                         |
|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------|
| Spare lives         | object `+0x13C`; gameplay constant `lives` (`00E420`, `00E6E8`)                                                                                                                                                                                                                | 2 (one digit in the HUD, 0–9) |
| Freed prisoners     | object `+0x13E` (`+1` at `00A2E4`/`00A2F2` when a chained villager is freed); `+0x138` is the copy the HUD draws (up to 5 icons)                                                                                                                                               | —                             |
| Extra life          | `0103F2`: when `+0x13E` reaches 5, subtract 5 and add a life (`010416`), sound `DF`, the icons blink; OPTIONS → 100 ВРАГОВ: the same every 100 kills (patch `kill_counter`, up to 9 lives)                                                                                     | every 5 prisoners = +1 life   |
| Credits (continues) | `FFC77C`; gameplay constant `credits` (`0003B6`)                                                                                                                                                                                                                               | 4                             |
| Continue countdown  | «ИГРАЕМ? 9» after the last death: `FFC783` (the continue state at `FFC780`, `+3`), set by `00E650` — constant `countdown`; a count lasts `countdown_frames` frames (`00E65C`, `00E71A`: 60), A, B or C ends the second at once (`00E70E`); at 0, `00E726` starts the game over | 9 seconds                     |
