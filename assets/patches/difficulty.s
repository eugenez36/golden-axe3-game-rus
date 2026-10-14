; Difficulty «ЖЕСТЬ)»: the hard enemy set, and every ordinary enemy twice.
;
; Assembled by ga3.m68k when the difficulty patch segments are built. Every
; upper-case name is a symbol from rom_map.yml; NAMES (the three menu names,
; NAME_WIDTH characters each) is appended to the names section by the build
; from text/difficulty.txt.
;
; DIFF is 0 normal, 1 hard, HARD (2) the new one. The game reads it in one
; place: the spawn walker skips an entry whose level is above DIFF (plus one
; with two players). At HARD that level is the hard one, and each ordinary
; enemy the game spawns (a plain entry of an ordinary type, never a boss or a
; rider) is queued once more. The copy is spawned by the game's own routine
; as soon as an enemy slot is free, one at a time (GAP_FRAMES apart), just past
; an edge of the screen and on ground at the player's level, found in the
; stage's collision boxes: never behind the camera, inside a wall or over a
; drop, where it could not reach the player or would fall through the floor.
; The game drops an enemy that finds no free slot; at HARD such an ordinary
; enemy is queued instead, with its copy, so the copies never cost an original;
; a wave (and a stage end) does not count as cleared while copies wait, so the
; next wave starts after them. Clearing the game state empties the queue.

        section menu

; ---------------------------------------------------------------- options menu

; replaces `add.b d1,DIFF.w; andi.b #1,DIFF.w` and the drawing after it, reached
; by bsr with d1 = -1, 0 or +1 (left, redraw, right) and a6 = VDP control port
menu:
        moveq   #0,d0
        move.b  DIFF.w,d0
        add.b   d1,d0
        bpl.s   .top
        moveq   #HARD,d0                ; left of the first value: the last
        bra.s   .set
.top:   cmpi.b  #HARD,d0
        bls.s   .set
        moveq   #0,d0                   ; right of the last value: the first
.set:   move.b  d0,DIFF.w
        mulu.w  #NAME_WIDTH,d0
        lea     NAMES,a0
        adda.w  d0,a0
        move.w  #MENU_CELL,d0
        jsr     TO_VDP                  ; d0: the cell's VRAM write command
        move.l  d0,(a6)
        moveq   #NAME_WIDTH-1,d7
.char:  move.w  #$E000,d1               ; priority, palette 3, as the game draws it
        add.b   (a0)+,d1
        move.w  d1,-4(a6)
        dbra    d7,.char
        rts

        section spawn

; ---------------------------------------------------------------- enemy level

; replaces `move.b DIFF.w,d6` and the first word of `btst #0,DEMO.w`:
; HARD spawns the entries of the hard level, no more. A queued entry passed
; this test when it first came up (the two-player bonus can change since), so
; it is not tested again: any level passes
gate:
        move.b  DIFF.w,d6
        cmpi.b  #1,d6
        bls.s   .ok
        moveq   #1,d6
.ok:    tst.b   COPYING.w
        beq.s   .test
        moveq   #3,d6                   ; the highest level there is
.test:  btst    #0,DEMO.w
        jmp     GATE_BACK               ; the beq after the btst

; ---------------------------------------------------------------- the copies

; replaces `move.w SPAWN_D1.w,d1; lsr.w #1,d1` right after a plain entry got an
; enemy slot: a1 the new enemy, d0/d1 the entry, d3 its X (high word)
spawned:
        tst.b   COPYING.w               ; this is a copy: no copy of a copy
        bne.s   .back
        cmpi.b  #HARD,DIFF.w
        bne.s   .back
        btst    #0,DEMO.w               ; the demo plays the normal game
        bne.s   .back
        movem.l d0-d2/a0,-(sp)
        bsr.w   ordinary
        bne.s   .done
        bsr.w   push                    ; the copy
.done:  movem.l (sp)+,d0-d2/a0
.back:  move.w  SPAWN_D1.w,d1
        lsr.w   #1,d1
        jmp     SPAWN_BACK

; replaces `jsr ENEMY_SLOT; beq` (the free-slot search of a plain entry):
; no slot drops the entry, except an ordinary enemy at HARD, which is queued
; with its copy and marked done (bit 4 of 2(a6)) so the game does not retry it
alloc:
        jsr     ENEMY_SLOT              ; Z set: a1 is a free enemy slot
        bne.s   .none
        jmp     ALLOC_BACK
.none:  tst.b   COPYING.w               ; a queued copy stays queued
        bne.s   .drop
        cmpi.b  #HARD,DIFF.w
        bne.s   .drop
        btst    #0,DEMO.w
        bne.s   .drop
        movem.l d0-d2/a0,-(sp)
        bsr.w   ordinary
        bne.s   .keep
        bsr.w   push                    ; the original
        bsr.w   push                    ; its copy
        bset    #4,2(a6)
.keep:  movem.l (sp)+,d0-d2/a0
.drop:  rts

; Z set when the type in d0.b is an ordinary enemy
ordinary:
        lea     ORDINARY_TYPES,a0
.next:  move.b  (a0)+,d2
        beq.s   .no
        cmp.b   d0,d2
        bne.s   .next
        rts                             ; Z set by the cmp
.no:    moveq   #1,d2                   ; Z clear
        rts

; queue the entry d0/d1 with the X the game just gave it (d3, high word) in
; bits 19..8: pop (place) takes the edge nearer to it
push:
        moveq   #0,d2
        move.b  Q_COUNT.w,d2
        cmpi.b  #Q_LEN,d2
        bcc.s   .full                   ; a full queue drops the entry
        andi.l  #$000000FF,d0           ; keep the type
        move.l  d3,d2
        clr.w   d2
        lsr.l   #8,d2                   ; X into bits 19..8
        andi.l  #$000FFF00,d2
        add.l   d2,d0
        andi.l  #$FFFFFFC0,d1           ; a plain spawn: an enemy a command
                                        ; handler spawned keeps its command here
.put:   moveq   #0,d2
        move.b  Q_HEAD.w,d2
        add.b   Q_COUNT.w,d2
        andi.w  #Q_LEN-1,d2
        lsl.w   #3,d2
        lea     Q_DATA.w,a0
        adda.w  d2,a0
        move.l  d0,(a0)+
        move.l  d1,(a0)
        addq.b  #1,Q_COUNT.w
.full:  rts

; replaces `lea SPAWNER.w,a6` and the first word of `btst #1,2(a6)` in the
; spawner's frame routine (not run while magic plays): spawn the oldest copy
; if an enemy slot is free and the last copy came in GAP_FRAMES ago
frame:
        lea     SPAWNER.w,a6
        tst.b   Q_COUNT.w
        beq.s   .go
        tst.b   GAP.w                   ; one at a time
        beq.s   .ready
        subq.b  #1,GAP.w
        bra.s   .go
.ready: btst    #1,2(a6)                ; the spawner is held
        bne.s   .go
        lea     ENEMIES.w,a1
        moveq   #ENEMY_SLOTS-1,d7
.slot:  tst.b   (a1)
        beq.s   .free
        lea     OBJ_SIZE(a1),a1
        dbra    d7,.slot
        bra.s   .go                     ; all slots busy: wait
.free:  jsr     pop
.go:    btst    #1,2(a6)
        bne.s   .skip
        jmp     FRAME_GO
.skip:  jmp     FRAME_SKIP

; replace `lea ENEMIES.w,a1; moveq #3,d7` of the "wave cleared" check (all
; enemies gone or dying) and of the "no enemy left" check: not while copies wait
wave_clear:
        tst.b   Q_COUNT.w
        bne.s   busy
        lea     ENEMIES.w,a1
        moveq   #ENEMY_SLOTS-1,d7
        jmp     WAVE_BACK

no_enemy:
        tst.b   Q_COUNT.w
        bne.s   busy
        lea     ENEMIES.w,a1
        moveq   #ENEMY_SLOTS-1,d7
        jmp     EMPTY_BACK

busy:   moveq   #1,d7                   ; Z clear: not yet
        rts

; replaces `lea STATE.w,a0` and the first word of `move.w #STATE_WORDS-1,d0`
; of the routine that clears the game state (stage start, game over, title)
reset:
        clr.b   Q_COUNT.w
        clr.b   Q_HEAD.w
        clr.b   COPYING.w
        clr.b   GAP.w
        clr.b   WAIT.w
        lea     STATE.w,a0
        move.w  #STATE_WORDS-1,d0
        jmp     CLEAR_BACK

; even types the spawn data gives ordinary enemies (handler 007954); 0 ends
ORDINARY_TYPES:
        dc.b    $10, $12, $14, $16, $18, $1A, $1C, $2C, $34, $36, $38, 0
        even

        section place

; ---------------------------------------------------------------- where a copy comes in

; spawn the queue head through the game's own routine, just past an edge of the
; screen, on ground at the player's level (place); it stays queued if the
; routine found no slot (bit 4 of 2(a6) is the routine's "done" flag) or no
; edge has such ground, and is dropped after WAIT_FRAMES frames without one
pop:
        movem.l d0-d7/a0-a5,-(sp)
        move.b  2(a6),-(sp)
        bclr    #4,2(a6)
        moveq   #0,d2
        move.b  Q_HEAD.w,d2
        lsl.w   #3,d2
        lea     Q_DATA.w,a0
        adda.w  d2,a0
        move.l  (a0)+,d0
        move.l  (a0),d1
        bsr.w   place
        beq.s   .none
        move.b  #1,COPYING.w
        jsr     SPAWN_ONE
        clr.b   COPYING.w
        btst    #4,2(a6)
        beq.s   .kept
        move.b  #GAP_FRAMES,GAP.w
.next:  clr.b   WAIT.w
        move.b  Q_HEAD.w,d2
        addq.b  #1,d2
        andi.b  #Q_LEN-1,d2
        move.b  d2,Q_HEAD.w
        subq.b  #1,Q_COUNT.w
.kept:  move.b  (sp)+,2(a6)
        movem.l (sp)+,d0-d7/a0-a5
        rts
.none:  addq.b  #1,WAIT.w
        cmpi.b  #WAIT_FRAMES,WAIT.w
        bcs.s   .kept
        bra.s   .next                   ; no ground for it: drop it

; rewrite the entry d0/d1 to come in past the edge nearer to where the original
; came in, else past the other edge: at the player's depth or else the entry's,
; just above the ground found there, at that absolute X. Z clear when found
place:
        lea     PLAYER1.w,a2            ; the reference: player 1, else player 2
        tst.b   (a2)
        bne.s   .ref
        lea     PLAYER2.w,a2
        tst.b   (a2)
        beq.s   .no
.ref:   move.w  CAMERA.w,d5
        move.l  d0,d2
        lsr.l   #8,d2
        andi.w  #$0FFF,d2
        sub.w   d5,d2                   ; the original's X on screen
        moveq   #0,d6                   ; right edge first
        lea     RIGHT_X,a0
        cmpi.w  #$00A0,d2
        bge.s   .try
        moveq   #1,d6                   ; left edge first
        lea     LEFT_X,a0
.try:   bsr.s   try
        bne.s   .yes
        lea     LEFT_X,a0
        tst.b   d6
        beq.s   .other
        lea     RIGHT_X,a0
.other: bsr.s   try
        bne.s   .yes
.no:    moveq   #0,d7                   ; Z set: nowhere yet
        rts
.yes:   andi.l  #$000000FF,d0           ; the type, placement 0 (absolute X)
        moveq   #0,d7
        move.w  d2,d7
        andi.w  #$0FFF,d7
        lsl.l   #8,d7                   ; X into bits 19..8
        add.l   d7,d0
        andi.l  #$C00001C0,d1           ; keep the level and the variant
        moveq   #0,d7
        move.w  d4,d7
        andi.w  #$01FF,d7
        swap    d7
        lsl.l   #3,d7                   ; depth into bits 27..19
        add.l   d7,d1
        moveq   #0,d7
        move.w  d3,d7
        addq.w  #2,d7                   ; just above the ground: falls onto it
        lsr.w   #1,d7
        andi.w  #$03FF,d7
        lsl.l   #8,d7
        lsl.l   #1,d7                   ; height / 2 into bits 18..9
        add.l   d7,d1
        moveq   #1,d7                   ; Z clear
        rts

; the X offsets from the camera tried at an edge (a0), the first past the edge
; where the game's own placement puts an enemy, then around it; ends with END_X.
; Z clear and d2 the X, d3 the ground, d4 the depth when found
try:
.next:  move.w  (a0)+,d2
        cmpi.w  #END_X,d2
        beq.s   .no
        add.w   d5,d2
        bmi.s   .next                   ; left of the stage start
        move.w  DEPTH(a2),d4
        bsr.s   floor
        bne.s   .yes
        move.l  d1,d4
        swap    d4
        lsr.w   #3,d4
        andi.w  #$01FF,d4               ; the entry's depth
        bsr.s   floor
        beq.s   .next
.yes:   rts
.no:    moveq   #0,d7
        rts

RIGHT_X:
        dc.w    $0150, $0168, $0138, $0180, $0120, END_X
LEFT_X:
        dc.w    -$0010, -$0028, $0008, -$0040, $0020, END_X

; ground at X d2, depth d4 in the stage's collision boxes (TERRAIN, the table
; the physics step reads at 002CAC: a word list per 64-pixel column, boxes of
; centre/half-size words for X, depth, height, then a type word). The ground
; is the highest plain box top no more than UP above the player's ground
; (FLOOR of a2) and no more than DOWN below it, with no box over it within BODY
; (a wall, a ledge) and no special box at all. Z clear and d3 the ground
floor:
        lea     TERRAIN,a5
        move.w  STAGE.w,d7
        add.w   d7,d7
        adda.w  0(a5,d7.w),a5
        move.w  SUBSTAGE.w,d7
        add.w   d7,d7
        adda.w  0(a5,d7.w),a5
        move.w  d2,d7
        lsr.w   #6,d7
        add.w   d7,d7
        adda.w  0(a5,d7.w),a5
        movea.l a5,a4                   ; the column's list; offsets from it
        movea.w FLOOR(a2),a1
        lea     UP(a1),a1               ; the highest ground taken
        move.w  #$8000,d3               ; no ground yet
.box1:  move.w  (a5)+,d7
        move.w  d7,-(sp)                ; bit 15: the column's last box
        andi.w  #$7FFF,d7
        lea     0(a4,d7.w),a3
        bsr.s   inside
        beq.s   .next1
        tst.w   12(a3)
        bne.s   .next1
        cmpa.w  d7,a1
        blt.s   .next1                  ; too high above the player
        cmp.w   d3,d7
        ble.s   .next1
        move.w  d7,d3
.next1: tst.w   (sp)+
        bpl.s   .box1
        move.w  FLOOR(a2),d7
        subi.w  #DOWN,d7
        cmp.w   d7,d3
        blt.s   .no                     ; none, or too far below the player
        movea.l a4,a5
.box2:  move.w  (a5)+,d7
        move.w  d7,-(sp)
        andi.w  #$7FFF,d7
        lea     0(a4,d7.w),a3
        bsr.s   inside
        beq.s   .next2
        tst.w   12(a3)
        bne.s   .wall                   ; a special box: keep away
        cmp.w   d3,d7
        ble.s   .next2                  ; at or under the ground
        move.w  8(a3),d7
        sub.w   10(a3),d7
        subi.w  #BODY,d7
        cmp.w   d3,d7
        blt.s   .wall                   ; its bottom is within BODY of the ground
.next2: tst.w   (sp)+
        bpl.s   .box2
        moveq   #1,d7                   ; Z clear: ground
        rts
.wall:  addq.l  #2,sp
.no:    moveq   #0,d7
        rts

; Z clear when X d2, depth d4 are inside box a3 (|X - centre| < half size, the
; same for depth); d7 its top (centre + half size of the height)
inside:
        move.w  d2,d7
        sub.w   (a3),d7
        bpl.s   .x
        move.w  (a3),d7
        sub.w   d2,d7
.x:     cmp.w   2(a3),d7
        bcc.s   .out
        move.w  d4,d7
        sub.w   4(a3),d7
        bpl.s   .z
        move.w  4(a3),d7
        sub.w   d4,d7
.z:     cmp.w   6(a3),d7
        bcc.s   .out
        move.w  8(a3),d7
        add.w   10(a3),d7               ; a top is never 0
        rts
.out:   moveq   #0,d7
        rts
