; Menus in the style of docs/branding/banner.svg: the title's new art (sky,
; logo, "III", cursor; assets/gfx/screens/, drawn by ga3 banner-art), a slow
; cloud drift instead of the fast parallax, and the bottom bar of the title
; and the main menu.
;
; Assembled by ga3.m68k when the menus patch segments are built. Every
; upper-case name is a symbol from rom_map.yml or a label of the art section
; the build generates from the PNGs (LOGO_TILES, SKY_MAP, LOGO_PAL ...). Most
; of the work is the `pointers:` list there: the game's own loaders, pointed at
; the new data. The code below is what pointers cannot do.

        section code

; ---------------------------------------------------------------- sky drift

; replaces `lea $ff0002.l,a0` where both entries of the plane B scroll routine
; meet: d0 = the first row group's step, d1 = its change. The title's entry
; (d0 = -5) moves the clouds every DRIFT_FRAMES frames by DRIFT_STEP pixels,
; all rows alike; the intro's fast sweep (d0 = $12) stays as it is.
drift:
        cmpi.w  #-5,d0
        bne.s   .go
        subq.b  #1,DRIFT.w
        bpl.s   .wait
        move.b  #DRIFT_FRAMES-1,DRIFT.w
        moveq   #DRIFT_STEP,d0
        moveq   #0,d1
.go:    lea     $FF0002,a0
        jmp     SCROLL_BACK
.wait:  rts

; ---------------------------------------------------------------- the cursor tile

; replaces `lea $1585c(pc),a0` and the first word of `move.w #$10,d0`: the
; game uploads the 32 words at a0 to tiles $10 (the menus' cursor) and $11
; (blank; the game sent the code after its cursor there)
cursor:
        lea     CURSOR_TILE,a0
        move.w  #$10,d0
        jmp     CURSOR_BACK

; ---------------------------------------------------------------- the bottom bar

; The title's plane A slides in column by column (V-scroll, 014D8C) after its
; setup, so the bar is drawn where the slide has finished: at the three places
; that then wrote "TM", each replacing `move.l #$44ae0003,$c00004.l` (a6 = VDP
; control): the title after the intro, the title when START skips the intro,
; and the main menu on the way back from the options. The middle is the game's
; blinking НАЖМИ СТАРТ on the title, the version line in the menu.
bar_intro:
        bsr.w   sides
        move.l  #TM_CELL,(a6)
        jmp     INTRO_BACK
bar_skip:
        bsr.w   sides
        move.l  #TM_CELL,(a6)
        jmp     SKIP_BACK
bar_options:
        bsr.w   sides
        move.l  #TM_CELL,(a6)
        jmp     OPTIONS_BACK

; replaces `move.l #$49960003,d0` as the title turns into the main menu: the
; middle of the bar cleared for the version line
menu:
        movem.l d0/d7,-(a7)
        move.w  #BAR_MIDDLE,d0
        jsr     TO_VDP
        move.l  d0,(a6)
        moveq   #MIDDLE_WIDTH-1,d7
.clear: move.w  #0,-4(a6)
        dbra    d7,.clear
        movem.l (a7)+,d0/d7
        move.l  #$49960003,d0
        jmp     MENU_BACK

; ---------------------------------------------------------------- the options screen

; replaces `move.w #$0,d0` and the first word of `lea $f200.w,a2`, which begin
; blacking out palette 0 as the options screen opens: the sky stays
options_sky:
        jmp     SKY_KEPT

; replaces `bsr.w $120e6` (the planes cleared) and the first word of
; `lea $1512c(pc),a0` (the labels): the bar's sides on the cleared plane A,
; then the first label, the screen's title ОПЦИИ, in gold the way the game
; draws a label (column, row, text, FF); the game draws the rest, one fewer
; (the moveq after the lea, in `pointers:`)
options_bar:
        jsr     CLEAR
        bsr.w   sides
        lea     LABELS_TABLE,a0
        move.w  #$C000,d0
        add.b   (a0),d0
        add.b   (a0)+,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.w   #7,d1
        add.w   d1,d0
        jsr     TO_VDP
        move.l  d0,(a6)
.char:  moveq   #0,d1
        move.b  (a0)+,d1
        bmi.s   .done
        addi.w  #GOLD_ATTR,d1
        move.w  d1,-4(a6)
        bra.s   .char
.done:  jmp     LABELS_BACK

; ---------------------------------------------------------------- the character select

; replaces `lea $15a06(pc),a0` and the first word of `move.w #$c18e,d0`, after
; the select screen has loaded its palettes: colours 0-7 of palette 3 become
; the sky's (its plane B map, in `pointers:`, is the sky's in palette 3; the
; "1P"/"2P" markers keep 8-11). A duel has no plane B map and uses the sky's
; VRAM; there palette 3 is its title ВЫБОР ГЕРОЯ (1-7), which turns gold, and
; stays gold on the duel's next screen, ВЫБОР ЭТАПА, which keeps palette 3. The
; duel's teal backdrop stays: shadow/highlight is on there, and the game hides
; it under boxes of the font's background colour ($640, half of $C80).
select_sky:
        lea     SELECT_PAL,a1
        move.w  (a1),$F200.w            ; the backdrop: the sky's colour 0, which is transparent
        cmpi.w  #DUEL,MODE.w
        bcs.s   .copy
        lea     DUEL_TITLE_PAL,a1       ; (a duel sets its own backdrop afterwards, 015ABC)
.copy:  lea     $F260.w,a2
        moveq   #SELECT_PAL_COLOURS-1,d7
        jsr     COPY_PAL
        lea     MARKERS,a0
        move.w  #$C18E,d0
        jmp     SELECT_BACK

sides:
        move.w  #BAR_LEFT,d0
        lea     BAR_TEXT,a0
        moveq   #LEFT_WIDTH-1,d7
        bsr.s   .put
        move.w  #BAR_RIGHT,d0
        lea     BAR_TEXT+LEFT_WIDTH,a0
        moveq   #RIGHT_WIDTH-1,d7
.put:   jsr     TO_VDP
        move.l  d0,(a6)
.char:  move.w  #BAR_ATTR,d1
        add.b   (a0)+,d1
        move.w  d1,-4(a6)
        dbra    d7,.char
        rts

; ---------------------------------------------------------------- "III"

; the title's "III" sprite (object 01587C): its mapping in the game's format --
; pieces - 1, a flag byte, then per piece y, size (width - 1 << 2 | height - 1),
; tile, x, x when mirrored, y when flipped, 0. The art (III_TILES) is 10 x 6
; cells cut into these pieces, centred on the object's x, its top -III_TOP
; pixels above the object's y.
        even
III_SPRITE:
        dc.b    5, 0
        dc.b    III_TOP, $0F
        dc.w    0
        dc.b    -40, 8, -III_TOP-32, 0
        dc.b    III_TOP, $0F
        dc.w    16
        dc.b    -8, -24, -III_TOP-32, 0
        dc.b    III_TOP, $07
        dc.w    32
        dc.b    24, -40, -III_TOP-32, 0
        dc.b    III_TOP+32, $0D
        dc.w    40
        dc.b    -40, 8, -III_TOP-48, 0
        dc.b    III_TOP+32, $0D
        dc.w    48
        dc.b    -8, -24, -III_TOP-48, 0
        dc.b    III_TOP+32, $05
        dc.w    56
        dc.b    24, -40, -III_TOP-48, 0
