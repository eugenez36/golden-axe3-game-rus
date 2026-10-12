; Kill counter: enemies killed by each player, shown next to their HUD.
;
; Assembled by ga3.m68k when the kill_counter patch segments are built. Every
; upper-case name is a symbol from rom_map.yml (an address or a constant), and
; each `section` is placed at the start of the segment of that name, so this
; file holds no ROM or RAM address of its own. GLYPHS and NIBBLES are tables
; the build appends to the tiles section from the font art.
;
; Counting: the three places that take hit points from an object jump here.
; Each subtracts as before; when an enemy's HP goes from above zero to zero
; and the hit came from a player, that player's counter goes up (to 99).
; Display: every frame, just before the game waits for VBlank, the sprite list
; is walked; for each player whose HUD is on screen two digit tiles go to free
; VRAM and one 2x1 sprite is appended right of the HUD.
; Reset: choosing a game mode in the main menu clears both counters.

; ---------------------------------------------------------------- counting

        section count

; victim a0, attacker a1, damage d1; replaces sub/bpl/clr, the caller then rts
melee_a0:
        tst.b   HP(a0)
        beq.s   .done
        sub.b   d1,HP(a0)
        bgt.s   .done
        clr.b   HP(a0)
        bsr.s   credit
.done:  rts

; victim a1, attacker a0, damage d1
melee_a1:
        tst.b   HP(a1)
        beq.s   .done
        sub.b   d1,HP(a1)
        bgt.s   .done
        clr.b   HP(a1)
        exg     a0,a1
        bsr.s   credit
        exg     a0,a1
.done:  rts

; magic: victim a0, damage d0, caster in CASTER (0 player 1, 1 player 2)
magic:
        tst.b   HP(a0)
        beq.s   .back
        sub.b   d0,HP(a0)
        bgt.s   .back
        clr.b   HP(a0)
        move.l  a1,-(sp)
        lea     P1.w,a1
        tst.w   CASTER.w
        beq.s   .who
        lea     P2.w,a1
        cmpi.w  #1,CASTER.w
        bne.s   .skip
.who:   bsr.s   credit
.skip:  movea.l (sp)+,a1
.back:  jmp     MAGIC_BACK

; victim a0, attacker a1: count the kill when an enemy falls to a player
credit:
        move.l  a2,-(sp)
        cmpa.w  #P1,a0
        beq.s   .done
        cmpa.w  #P2,a0
        beq.s   .done
        lea     KILLS.w,a2
        cmpa.w  #P1,a1
        beq.s   .count
        addq.w  #1,a2
        cmpa.w  #P2,a1
        bne.s   .done
.count: cmpi.b  #99,(a2)
        bcc.s   .done
        addq.b  #1,(a2)
.done:  movea.l (sp)+,a2
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

; Registers in hud: a0 sprite list, a4 last sprite, d2 next free index,
; a2 / a3 the HUD block of player 1 / 2 (0 when that HUD is not shown).
hud:
        lea     SPRITES.w,a0
        suba.l  a2,a2
        suba.l  a3,a3
        moveq   #0,d0                   ; current sprite index
        moveq   #0,d2                   ; sprites seen
.walk:  move.w  d0,d1
        lsl.w   #3,d1
        lea     0(a0,d1.w),a4
        cmpi.w  #HUD_SCAN,d2            ; HUD blocks are among the first sprites
        bcc.s   .next
        cmpi.b  #HUD_SIZE,2(a4)         ; 4 x 3 cells
        bne.s   .next
        move.w  4(a4),d1
        andi.w  #$07FF,d1
        cmpi.w  #HUD_P1,d1
        bne.s   .not1
        movea.l a4,a2
.not1:  cmpi.w  #HUD_P2,d1
        bne.s   .next
        movea.l a4,a3
.next:  addq.w  #1,d2
        moveq   #0,d1
        move.b  3(a4),d1
        andi.b  #$7F,d1
        beq.s   .last
        cmpi.w  #MAX_SPRITES,d2
        bcc.s   .done
        move.w  d1,d0
        bra.s   .walk
.last:  move.l  a2,d1
        beq.s   .p2
        moveq   #0,d3
        move.b  KILLS.w,d3
        moveq   #0,d1                   ; tiles 0 and 1
        jsr     tiles
        movea.l a2,a1
        moveq   #0,d1
        bsr.s   sprite
.p2:    move.l  a3,d1
        beq.s   .done
        moveq   #0,d3
        move.b  KILLS+1.w,d3
        moveq   #2,d1                   ; tiles 2 and 3
        jsr     tiles
        movea.l a3,a1
        moveq   #2,d1
        bsr.s   sprite
.done:  rts

; append a 2x1 sprite right of the HUD block at a1, tiles d1 and d1+1;
; a4 = last sprite so far, d2 = its index + 1; both move on to the new sprite
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
