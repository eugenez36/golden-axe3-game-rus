; Options screen: items after the game's own, first of them БАНКИ МАГИИ, the
; magic potions a player gets when they have none.
;
; Assembled by ga3.m68k when the options patch segments are built. Every
; upper-case name is a symbol from rom_map.yml; LABELS (the new items' labels,
; LABEL_WIDTH characters each) is appended to the labels section by the build
; from text/options.txt.
;
; The game's options screen has five items, the cursor (CURSOR) 0..4: СЛОЖНОСТЬ,
; КНОПКИ, МУЗ., ЗВУК, МЕНЮ. The new item goes in before МЕНЮ, at МЕНЮ's row;
; МЕНЮ moves three rows down (its row byte in text/menu.txt). Its value lives in
; POT, a byte the game keeps over a soft reset, with the difficulty, and clears
; at power-on: it holds the count minus the default (the constant `potions`,
; read from the operand of the instruction this patch bypasses), so power-on
; gives the default. The demo plays the base game: one potion.

        section menu

; ---------------------------------------------------------------- screen entry

; replaces `addq.w #1,$f102.w; clr.w $f160.w` (first word) after the labels
; are drawn, a6 = VDP control port: the new label and the new value
draw:
        move.w  #POT_LABEL,d0
        jsr     TO_VDP                  ; d0: the cell's VRAM write command
        move.l  d0,(a6)
        lea     LABELS,a0
        moveq   #LABEL_WIDTH-1,d7
.char:  move.w  #$E000,d1               ; priority, palette 3, as the game draws it
        add.b   (a0)+,d1
        move.w  d1,-4(a6)
        dbra    d7,.char
        moveq   #0,d1
        bsr.w   potions
        addq.w  #1,$F102.w
        clr.w   CURSOR.w
        jmp     ENTRY_BACK

; ---------------------------------------------------------------- the cursor

; replaces `add.w d1,$f160.w; bpl` and the rest of the cursor routine, d1 = -1,
; 0 or +1 (up, redraw, down): the same, over ITEMS rows
cursor:
        add.w   d1,CURSOR.w
        bpl.s   .top
        move.w  #ITEMS-1,CURSOR.w       ; above the first item: the last
.top:   cmpi.w  #ITEMS-1,CURSOR.w
        bls.s   .draw
        clr.w   CURSOR.w                ; below the last item: the first
.draw:  move.l  #CURSOR_CLEAR,d0        ; clear the cursor column, rows 8 down
        moveq   #0,d1
        moveq   #ROWS-1,d2
        move.w  #0,d4
        jsr     FILL
        move.w  #CURSOR_CELL,d0
        move.w  CURSOR.w,d1
        lea     .rows(pc),a1
        move.b  (a1,d1.w),d1
        lsl.w   #7,d1
        add.w   d1,d0
        jsr     TO_VDP
        move.l  d0,(a6)
        move.w  #$A010,-4(a6)           ; the cursor tile
        rts
.rows:  dc.b    $08, $0B, $10, $13, $16, $19
        even

; ---------------------------------------------------------------- left/right

; replaces `move.w $f160.w,d0; add.w d0,d0` before the jump table of the
; items' left/right routines (d1 = -1 or +1): the game's items through it, the
; new one here, МЕНЮ nothing
item:
        move.w  CURSOR.w,d0
        cmpi.w  #POT_ITEM,d0
        beq.s   potions
        bhi.s   .none
        add.w   d0,d0
        jmp     ITEM_BACK               ; the lea of the jump table
.none:  rts

; replaces `cmpi.w #4,$f160.w`, the test for МЕНЮ when a button is pressed
leave:
        cmpi.w  #MENU_ITEM,CURSOR.w
        bne.s   .stay
        jmp     MENU_EXIT
.stay:  jmp     LEAVE_BACK

; ---------------------------------------------------------------- the value

; d1 = -1, 0 or +1: change the count by d1 (0..POT_MAX, around) and draw it
potions:
        move.b  POT.w,d0
        add.b   d1,d0
        bpl.s   .top
        moveq   #POT_MAX,d0
.top:   cmpi.b  #POT_MAX,d0
        bls.s   .set
        moveq   #0,d0
.set:   move.b  d0,POT.w
        bsr.s   count
        move.w  d0,d1
        move.w  #POT_CELL,d0
        jsr     TO_VDP
        move.l  d0,(a6)
        addi.w  #$E030,d1               ; the digit, as the game draws МУЗ. and ЗВУК
        move.w  d1,-4(a6)
        rts

; d0.w: the potions the setting gives, 0..POT_MAX
count:
        moveq   #0,d0
        move.b  POT.w,d0
        add.b   DEFAULT,d0
        cmpi.b  #POT_MAX,d0
        bls.s   .ok
        subi.b  #POT_MAX+1,d0
.ok:    rts

; ---------------------------------------------------------------- the game

; replaces `tst.b $140(a0); bne` of the routine that gives a player (a0) the
; potions when they have none: at the start, after a death, after a continue
refill:
        tst.b   $140(a0)
        bne.s   .back
        btst    #0,DEMO.w
        bne.s   .demo
        bsr.s   count
        move.b  d0,$140(a0)
        bra.s   .back
.demo:  move.b  #DEMO_POTIONS,$140(a0)
.back:  jmp     REFILL_BACK
