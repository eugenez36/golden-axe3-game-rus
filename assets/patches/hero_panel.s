; Hero stats on the character select: the name, magic, health, hit / super,
; tempo and walking speed of the hero under each player's cursor, drawn over
; the title (variant B: each number with a bar). One full-width panel in a
; one-player game, a half panel for each player in a two-player game; nothing
; on the duel select.
;
; Assembled by ga3.m68k. Upper-case names are rom_map.yml symbols; PANEL_TILES,
; PANEL_FULL, PANEL_HALF and their sizes are generated from data/hero_panel.yml
; by src/ga3/hero_panel.py and appended to this section by the build.

        section panel

; replaces `move.w d0,$14(a0); mulu.w #6,d0` in the select screen's per-frame
; cursor routine (it runs once a frame for each player): a0 = the player's
; cursor block, d0 = the cursor 0..3. Returns past the mulu.
cursor:
        move.w  d0,$14(a0)
        movem.l d0-d5/a0-a2,-(sp)
        cmpi.w  #DUEL,MODE.w            ; the duel select is another screen
        bcc.s   .out
        move.w  #$2700,sr               ; no VBlank between our VDP accesses
        bsr.s   panel
        move.w  #$2000,sr
.out:   movem.l (sp)+,d0-d5/a0-a2
        mulu.w  #6,d0
        jmp     CURSOR_BACK

; Draw this player's panel unless the screen already shows it: the same hero,
; our tiles still in VRAM (the first word of the first tile) and our top-left
; cell still on plane A (the game redraws the screen when it returns to it).
; Registers: d2 player 0/1, d4 VRAM address of the panel's top-left cell,
; a2 the player's byte in SHOWN.
panel:
        moveq   #0,d2
        cmpa.w  #CURSOR_P1,a0
        beq.s   .p1
        moveq   #1,d2
.p1:    lea     SHOWN.w,a2
        adda.w  d2,a2
        move.l  #PANEL_READ,VDP_CTRL
        cmpi.w  #PANEL_SIG,VDP_DATA
        beq.s   .tiles
        bsr.w   upload
        move.w  #-1,SHOWN.w             ; both panels must be drawn again
.tiles: moveq   #0,d4                   ; column 0, or HALF_W for player 2 of two
        tst.w   MODE.w
        beq.s   .col
        moveq   #HALF_W,d4
        mulu.w  d2,d4
.col:   add.w   d4,d4
        addi.w  #PLANE_A,d4
        move.w  d4,d1
        bsr.s   command
        move.l  d1,VDP_CTRL
        cmpi.w  #PANEL_CORNER,VDP_DATA
        bne.s   .draw
        cmp.b   (a2),d0
        beq.s   .done
.draw:  move.b  d0,(a2)
        tst.w   MODE.w
        bne.s   .half
        lea     PANEL_FULL(pc),a1
        mulu.w  #FULL_SIZE,d0
        moveq   #FULL_H-1,d2
        moveq   #FULL_W-1,d3
        bra.s   .map
.half:  lea     PANEL_HALF(pc),a1
        mulu.w  #HALF_SIZE,d0
        moveq   #HALF_H-1,d2
        moveq   #HALF_W-1,d3
.map:   adda.w  d0,a1
.row:   move.w  d4,d1
        bsr.s   command
        ori.l   #$40000000,d1           ; CD0: a write
        move.l  d1,VDP_CTRL
        move.w  d3,d5
.cell:  move.w  (a1)+,VDP_DATA
        dbra    d5,.cell
        addi.w  #PLANE_ROW,d4
        dbra    d2,.row
.done:  rts

; d1.w = VRAM address -> d1.l = the VDP command that reads it (A13-A0 in the
; high word, A15-A14 in the low word)
command:
        swap    d1
        clr.w   d1
        swap    d1
        lsl.l   #2,d1
        lsr.w   #2,d1
        swap    d1
        rts

; copy the panel's tiles to free VRAM
upload:
        move.l  #PANEL_WRITE,VDP_CTRL
        lea     PANEL_TILES(pc),a1
        move.w  #PANEL_TILE_WORDS-1,d1
.word:  move.w  (a1)+,VDP_DATA
        dbra    d1,.word
        rts
