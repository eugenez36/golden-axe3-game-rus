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
; rider) is queued once more. The copy is spawned by the game's own routine,
; where the original came in, as soon as an enemy slot is free.
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

; queue the entry d0/d1 to come in where the game just placed it: X (d3, high
; word) becomes the entry's absolute position (placement 0), so the copy uses a
; spot the stage's own data chose, never one inside a wall
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
; if an enemy slot is free
frame:
        lea     SPAWNER.w,a6
        tst.b   Q_COUNT.w
        beq.s   .go
        btst    #1,2(a6)                ; the spawner is held
        bne.s   .go
        lea     ENEMIES.w,a1
        moveq   #ENEMY_SLOTS-1,d7
.slot:  tst.b   (a1)
        beq.s   .free
        lea     OBJ_SIZE(a1),a1
        dbra    d7,.slot
        bra.s   .go                     ; all slots busy: wait
.free:  bsr.w   pop
.go:    btst    #1,2(a6)
        bne.s   .skip
        jmp     FRAME_GO
.skip:  jmp     FRAME_SKIP

; spawn the queue head through the game's own routine; it stays queued if the
; routine found no slot (bit 4 of 2(a6) is the routine's "done" flag)
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
        move.b  #1,COPYING.w
        jsr     SPAWN_ONE
        clr.b   COPYING.w
        btst    #4,2(a6)
        beq.s   .kept
        move.b  Q_HEAD.w,d2
        addq.b  #1,d2
        andi.b  #Q_LEN-1,d2
        move.b  d2,Q_HEAD.w
        subq.b  #1,Q_COUNT.w
.kept:  move.b  (sp)+,2(a6)
        movem.l (sp)+,d0-d7/a0-a5
        rts

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
        lea     STATE.w,a0
        move.w  #STATE_WORDS-1,d0
        jmp     CLEAR_BACK

; even types the spawn data gives ordinary enemies (handler 007954); 0 ends
ORDINARY_TYPES:
        dc.b    $10, $12, $14, $16, $18, $1A, $1C, $2C, $34, $36, $38, 0
        even
