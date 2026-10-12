; Kill counter: enemies killed by each player, shown next to their HUD.
;
; Assembled by ga3.m68k when the kill_counter patch segments are built. Every
; upper-case name is a symbol from rom_map.yml (an address or a constant), and
; each `section` is placed at the start of the segment of that name, so this
; file holds no ROM or RAM address of its own. GLYPHS and NIBBLES are tables
; the build appends to the tiles section from the font art.
;
; Counting: the three places that take hit points from an object jump here.
; Each subtracts as before and marks the enemy with the player who hit it;
; when the enemy dies (HP to zero, or freed alive because it fell off the
; stage), the marked player's counter goes up (to 99).
; Display: every frame, just before the game waits for VBlank, the sprite list
; is walked; for each player whose HUD is on screen (its sprites and its art in
; VRAM) two digit tiles go to free VRAM and one 2x1 sprite is appended right of
; the HUD.
; Reset: choosing a game mode in the main menu clears both counters.

; ---------------------------------------------------------------- counting

        section count

; Every hit by a player marks the victim with that player (LAST_HIT: 1 or 2);
; the kill goes to the mark, whether the enemy's HP runs out or it falls off
; the stage alive (its object is freed with HP left). No mark, no kill.

; victim a0, attacker a1, damage d1; replaces sub/bpl/clr, the caller then rts
melee_a0:
        tst.b   HP(a0)
        beq.s   .done
        bsr.w   mark
        sub.b   d1,HP(a0)
        bgt.s   .done
        clr.b   HP(a0)
        bsr.w   kill
.done:  rts

; victim a1, attacker a0, damage d1
melee_a1:
        exg     a0,a1
        tst.b   HP(a0)
        beq.s   .done
        bsr.w   mark
        sub.b   d1,HP(a0)
        bgt.s   .done
        clr.b   HP(a0)
        bsr.w   kill
.done:  exg     a0,a1
        rts

; magic: victim a0, damage d0, caster in CASTER (0 player 1, 1 player 2)
magic:
        tst.b   HP(a0)
        beq.s   .back
        move.l  a1,-(sp)
        lea     P1.w,a1
        tst.w   CASTER.w
        beq.s   .who
        lea     P2.w,a1
        cmpi.w  #1,CASTER.w
        beq.s   .who
        suba.l  a1,a1                   ; an enemy's magic marks nobody
.who:   bsr.w   mark
        movea.l (sp)+,a1
        sub.b   d0,HP(a0)
        bgt.s   .back
        clr.b   HP(a0)
        bsr.w   kill
.back:  jmp     MAGIC_BACK

; an object is freed (replaces the first six bytes of the clear routine):
; marked and still alive means it fell after a player's hit
on_free:
        tst.b   LAST_HIT(a0)
        beq.s   .orig
        tst.b   HP(a0)
        beq.s   .orig                   ; died of a hit: counted then
        bsr.s   kill
.orig:  movea.l a0,a1
        moveq   #0,d2
        move.w  $E(a0),d1
        jmp     FREE_BACK

; victim a0, attacker a1: mark an enemy with the player who hit it
mark:
        cmpa.w  #P1,a0
        beq.s   .done
        cmpa.w  #P2,a0
        beq.s   .done
        cmpa.w  #P1,a1
        bne.s   .p2
        move.b  #1,LAST_HIT(a0)
        bra.s   .done
.p2:    cmpa.w  #P2,a1
        bne.s   .done
        move.b  #2,LAST_HIT(a0)
.done:  rts

; enemy a0 is dead: count it for the player in its mark (to 99), clear the mark
kill:
        move.l  a2,-(sp)
        lea     KILLS.w,a2
        cmpi.b  #1,LAST_HIT(a0)
        beq.s   .count
        addq.w  #1,a2
        cmpi.b  #2,LAST_HIT(a0)
        bne.s   .done
.count: cmpi.b  #99,(a2)
        bcc.s   .done
        addq.b  #1,(a2)
.done:  clr.b   LAST_HIT(a0)
        movea.l (sp)+,a2
        rts

; ---------------------------------------------------------------- reset

; replaces `move.w MODE_SRC.w,MODE.w` when a game mode is chosen; the caller then rts
new_game:
        move.w  MODE_SRC.w,MODE.w
        clr.w   KILLS.w
        rts

; ---------------------------------------------------------------- display

        section hud

; replaces the first six bytes of the frame wait (move #$2000,sr; bclr ...)
frame:
        movem.l d0-d3/a0-a5,-(sp)
        move.w  #$2700,sr
        bsr.s   hud
        movem.l (sp)+,d0-d3/a0-a5
        move.w  #$2000,sr
        bclr    #0,VBLANK_FLAG.w
        jmp     WAIT_BACK

; Registers in hud: a0 sprite list, a4 last sprite, d2 sprites in the list,
; a2 / a3 the HUD block of player 1 / 2 (0 when that HUD is not shown).
; The game adds sprites in order (sprite n links to n+1) and keeps their number
; in SPR_COUNT, which its own end-of-list code uses as well, so the
; HUD is found among the first sprites and the list is never walked.
hud:
        lea     SPRITES.w,a0
        suba.l  a2,a2
        suba.l  a3,a3
        move.w  SPR_COUNT.w,d2
        beq.s   .show
        cmpi.w  #MAX_SPRITES,d2
        bhi.s   .show                   ; not a sprite list we know: no HUD
        move.w  d2,d1
        lsl.w   #3,d1
        lea     -8(a0,d1.w),a4          ; last sprite
        moveq   #0,d0                   ; sprite index
.scan:  cmp.w   d2,d0
        bcc.s   .show
        cmpi.w  #HUD_SCAN,d0            ; HUD blocks are among the first sprites
        bcc.s   .show
        move.w  d0,d1
        lsl.w   #3,d1
        lea     0(a0,d1.w),a1
        addq.w  #1,d0
        cmpi.b  #HUD_SIZE,2(a1)         ; 4 x 3 cells
        bne.s   .scan
        move.w  4(a1),d1
        andi.w  #$07FF,d1
        cmpi.w  #HUD_P1,d1
        bne.s   .not1
        movea.l a1,a2
.not1:  cmpi.w  #HUD_P2,d1
        bne.s   .scan
        movea.l a1,a3
        bra.s   .scan
.show:  move.l  a2,d1
        beq.s   .hide1
        move.w  #HUD_P1,d1
        jsr     loaded
        beq.s   .hide1
        moveq   #0,d3
        move.b  KILLS.w,d3
        cmp.b   SHOWN.w,d3              ; digit tiles already hold this number?
        beq.s   .same1
        move.b  d3,SHOWN.w
        moveq   #0,d1                   ; tiles 0 and 1
        jsr     tiles
.same1: movea.l a2,a1
        moveq   #0,d1
        bsr.s   sprite
        bra.s   .p2
.hide1: move.b  #-1,SHOWN.w             ; upload again when the HUD is back
.p2:    move.l  a3,d1
        beq.s   .hide2
        move.w  #HUD_P2,d1
        jsr     loaded
        beq.s   .hide2
        moveq   #0,d3
        move.b  KILLS+1.w,d3
        cmp.b   SHOWN+1.w,d3
        beq.s   .same2
        move.b  d3,SHOWN+1.w
        moveq   #2,d1                   ; tiles 2 and 3
        jsr     tiles
.same2: movea.l a3,a1
        moveq   #2,d1
        bra.s   sprite
.hide2: move.b  #-1,SHOWN+1.w
        rts

; append a 2x1 sprite right of the HUD block at a1, tiles d1 and d1+1;
; a4 = last sprite so far, d2 = its index + 1; both move on to the new sprite.
; Rewriting the same slots every frame is harmless when the game has not
; rebuilt its list in between: the old last sprite then links to them again.
sprite:
        cmpi.w  #MAX_SPRITES,d2
        bcc.s   .done
        move.b  d2,3(a4)                ; link the old last sprite to the new one
        move.w  d2,d3
        lsl.w   #3,d3
        lea     0(a0,d3.w),a4
        move.w  (a1),d3                 ; y of the HUD block
        addi.w  #COUNTER_DY,d3
        move.w  d3,(a4)
        move.b  #COUNTER_SIZE,2(a4)
        clr.b   3(a4)                   ; end of the list
        addi.w  #COUNTER_ATTR,d1
        move.w  d1,4(a4)
        move.w  6(a1),d3                ; x of the HUD block
        addi.w  #COUNTER_DX,d3
        move.w  d3,6(a4)
        addq.w  #1,d2
.done:  rts

        section tiles

; upload two digit tiles for the number d3 (0..99) at tile slot d1
tiles:
        lsl.w   #5,d1                   ; 32 bytes a tile
        addi.w  #DIGITS_VRAM,d1
        moveq   #0,d0
        move.w  d1,d0
        lsl.l   #2,d0                   ; VDP command: A13-A0 in the high word,
        lsr.w   #2,d0                   ; A15-A14 in the low word, CD0 = 1
        ori.w   #$4000,d0
        swap    d0
        move.l  d0,VDP_CTRL
        moveq   #0,d0
        move.w  d3,d0
        divu.w  #10,d0                  ; quotient: tens, remainder: ones
        move.w  d0,d1
        bne.s   .tens
        moveq   #BLANK_GLYPH,d1         ; no leading zero
.tens:  bsr.s   glyph
        swap    d0
        move.w  d0,d1
; one tile for glyph d1 (0-9 or BLANK_GLYPH): 8 rows of 1bpp art, 2 words a row
glyph:
        lea     GLYPHS(pc),a1
        lea     NIBBLES(pc),a5
        lsl.w   #3,d1
        adda.w  d1,a1
        moveq   #7,d1
.row:   moveq   #0,d3
        move.b  (a1),d3
        lsr.w   #4,d3
        add.w   d3,d3
        move.w  0(a5,d3.w),VDP_DATA
        moveq   #0,d3
        move.b  (a1)+,d3
        andi.w  #$000F,d3
        add.w   d3,d3
        move.w  0(a5,d3.w),VDP_DATA
        dbra    d1,.row
        rts

; is the art of the HUD whose third block starts at tile d1 in VRAM? ne: yes.
; A spell clears the HUD tiles, and the game reloads them a few frames after
; the HUD sprites are back; until then the counter would float on its own.
; Each block (third, second, first: 16 tiles apart) begins with a border row.
loaded:
        moveq   #2,d3
.block: moveq   #0,d0
        move.w  d1,d0
        lsl.l   #7,d0                   ; VDP read command for tile d1:
        lsr.w   #2,d0                   ; 32 bytes a tile, then as in `tiles`
        swap    d0                      ; with CD0 = 0
        move.l  d0,VDP_CTRL
        tst.w   VDP_DATA
        beq.s   .no
        subi.w  #$10,d1
        dbra    d3,.block
        moveq   #1,d0
        rts
.no:    moveq   #0,d0
        rts
