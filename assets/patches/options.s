; Options screen: items after the game's own. БАНКИ МАГИИ: the magic potions a
; player gets when they have none. 100 ВРАГОВ: an extra life for every hundred
; enemies a player kills (patch kill_counter counts them and gives the life).
;
; Assembled by ga3.m68k when the options patch segments are built. Every
; upper-case name is a symbol from rom_map.yml; LABELS (the new items' labels,
; LABEL_WIDTH characters each, then the two values of 100 ВРАГОВ,
; VALUE_WIDTH characters each) is appended to the labels section by the build
; from text/options.txt.
;
; The game's options screen has five items, the cursor (CURSOR) 0..4: СЛОЖНОСТЬ,
; КНОПКИ, МУЗ., ЗВУК, МЕНЮ. The new items go in before МЕНЮ; below КНОПКИ every
; item is two rows from the next (МУЗ., ЗВУК and МЕНЮ moved: their label rows in
; text/menu.txt, the cells of the two values in pointers). Both settings live in
; POT, a byte the game keeps over a soft reset, with the difficulty, and clears
; at power-on: bits 0-6 hold the potions minus the default (the constant
; `potions`, read from the operand of the instruction this patch bypasses),
; bit LIFE_BIT is 100 ВРАГОВ, so power-on gives the default potions and ВЫКЛ.
; The demo plays the base game: one potion (and kill_counter gives no life).

        section menu

; ---------------------------------------------------------------- screen entry

; replaces `addq.w #1,$f102.w; clr.w $f160.w` (first word) after the labels
; are drawn, a6 = VDP control port: the new labels and their values
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
        move.w  #LIFE_LABEL,d0
        jsr     TO_VDP
        move.l  d0,(a6)
        moveq   #LABEL_WIDTH-1,d7
.char2: move.w  #$E000,d1
        add.b   (a0)+,d1                ; the second label follows the first
        move.w  d1,-4(a6)
        dbra    d7,.char2
        moveq   #0,d1
        bsr.w   potions
        moveq   #0,d1
        bsr.w   life
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
.rows:  dc.b    $08, $0B, $0F, $11, $13, $15, $18
        even

; ---------------------------------------------------------------- left/right

; replaces `move.w $f160.w,d0; add.w d0,d0` before the jump table of the
; items' left/right routines (d1 = -1 or +1): the game's items through it, the
; new ones here, МЕНЮ nothing
item:
        move.w  CURSOR.w,d0
        cmpi.w  #POT_ITEM,d0
        beq.s   potions
        cmpi.w  #LIFE_ITEM,d0
        beq.s   life
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
        andi.b  #POT_MASK,d0            ; bit LIFE_BIT is the other item
        add.b   d1,d0
        bpl.s   .top
        moveq   #POT_MAX,d0
.top:   cmpi.b  #POT_MAX,d0
        bls.s   .set
        moveq   #0,d0
.set:   btst    #LIFE_BIT,POT.w
        beq.s   .keep
        ori.b   #LIFE_FLAG,d0
.keep:  move.b  d0,POT.w
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
        andi.b  #POT_MASK,d0
        add.b   DEFAULT,d0
        cmpi.b  #POT_MAX,d0
        bls.s   .ok
        subi.b  #POT_MAX+1,d0
.ok:    rts

; d1 = -1, 0 or +1: left or right switches 100 ВРАГОВ, 0 only draws it
life:
        tst.w   d1
        beq.s   .draw
        bchg    #LIFE_BIT,POT.w
.draw:  lea     LABELS+LABEL_WIDTH+LABEL_WIDTH,a0   ; ВЫКЛ, then ВКЛ
        btst    #LIFE_BIT,POT.w
        beq.s   .off
        addq.w  #VALUE_WIDTH,a0
.off:   move.w  #LIFE_CELL,d0
        jsr     TO_VDP
        move.l  d0,(a6)
        moveq   #VALUE_WIDTH-1,d7
.char:  move.w  #$E000,d1
        add.b   (a0)+,d1
        move.w  d1,-4(a6)
        dbra    d7,.char
        rts

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
