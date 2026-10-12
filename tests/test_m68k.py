"""ga3.m68k: every supported form is checked by disassembling it again (Capstone)."""

from __future__ import annotations

import pytest

from ga3 import m68k

capstone = pytest.importorskip("capstone")

from ga3 import disasm  # noqa: E402 - after the capstone skip

ORIGIN = 0x1000
SYMS = {"RAM": 0xC7A4, "FAR": 0x00F8C6, "PORT": 0xC00004, "OFF": 0x142, "SEVEN": 7}


def _listing(code: bytes, origin: int = ORIGIN) -> list[str]:
    rows = disasm.disasm(bytes(origin) + code, origin, end=origin + len(code))
    return [f"{mn} {ops}".strip() for _a, _b, mn, ops in rows]


# source line -> what Capstone prints for it
FORMS = [
    ("tst.b OFF(a0)", "tst.b $142(a0)"),
    ("tst.w RAM.w", "tst.w $c7a4.w"),
    ("tst.w PORT", "tst.w $c00004.l"),
    ("clr.b 3(a4)", "clr.b $3(a4)"),
    ("clr.w RAM.w", "clr.w $c7a4.w"),
    ("clr.l RAM.w", "clr.l $c7a4.w"),
    ("clr.w d1", "clr.w d1"),
    ("tst.w d0", "tst.w d0"),
    ("sub.b d1,OFF(a1)", "sub.b d1, $142(a1)"),
    ("add.w d3,d3", "add.w d3, d3"),
    ("cmp.b RAM.w,d3", "cmp.b $c7a4.w, d3"),
    ("cmp.w RAM.w,d3", "cmp.w $c7a4.w, d3"),
    ("cmp.w d2,d0", "cmp.w d2, d0"),
    ("exg a0,a1", "exg.l a0, a1"),
    ("move.l a1,-(sp)", "move.l a1, -(a7)"),
    ("movea.l (sp)+,a1", "movea.l (a7)+, a1"),
    ("movea.l a4,a2", "movea.l a4, a2"),
    ("move.l a2,d1", "move.l a2, d1"),
    ("move.w RAM.w,RAM+2.w", "move.w $c7a4.w, $c7a6.w"),
    ("move.b d2,3(a4)", "move.b d2, $3(a4)"),
    ("move.b #4,2(a4)", "move.b #$4, $2(a4)"),
    ("move.b #-1,RAM.w", "move.b #$ff, $c7a4.w"),
    ("move.w #-1,RAM.w", "move.w #$ffff, $c7a4.w"),
    ("move.w RAM.w,d3", "move.w $c7a4.w, d3"),
    ("move.w d3,RAM.w", "move.w d3, $c7a4.w"),
    ("move.w #SEVEN,d1", "move.w #$7, d1"),
    ("move.l d0,d1", "move.l d0, d1"),
    ("move.b (a1)+,d3", "move.b (a1)+, d3"),
    ("move.w (a1),d3", "move.w (a1), d3"),
    ("move.w d3,6(a4)", "move.w d3, $6(a4)"),
    ("move.l d0,PORT", "move.l d0, $c00004.l"),
    ("move.w 0(a5,d3.w),PORT", "move.w (a5, d3.w), $c00004.l"),
    ("move.w #$2700,sr", "move.w #$2700, sr"),
    ("moveq #-1,d7", "moveq #$ff, d7"),  # 7EFF; Capstone prints the raw byte
    ("lea RAM.w,a1", "lea.l $c7a4.w, a1"),
    ("lea 0(a0,d1.w),a4", "lea.l (a0, d1.w), a4"),
    ("lea -8(a0,d1.w),a4", "lea.l -$8(a0, d1.w), a4"),
    ("cmpi.w #1,RAM.w", "cmpi.w #$1, $c7a4.w"),
    ("cmpi.b #99,(a2)", "cmpi.b #$63, (a2)"),
    ("cmpi.w #999,(a2)", "cmpi.w #$3e7, (a2)"),
    ("cmpi.b #$0E,2(a4)", "cmpi.b #$e, $2(a4)"),
    ("cmpi.w #80,d2", "cmpi.w #$50, d2"),
    ("cmpa.w #RAM,a0", "cmpa.w #$c7a4, a0"),
    ("suba.l a2,a2", "suba.l a2, a2"),
    ("adda.w d1,a1", "adda.w d1, a1"),
    ("addq.w #1,a2", "addq.w #$1, a2"),
    ("addq.b #1,(a2)", "addq.b #$1, (a2)"),
    ("addq.w #1,(a2)", "addq.w #$1, (a2)"),
    ("addq.w #2,a2", "addq.w #$2, a2"),
    ("addi.w #$86B8,d1", "addi.w #$86b8, d1"),
    ("subi.w #$10,d1", "subi.w #$10, d1"),
    ("andi.w #$07FF,d1", "andi.w #$7ff, d1"),
    ("andi.b #$7F,d1", "andi.b #$7f, d1"),
    ("ori.w #$4000,d0", "ori.w #$4000, d0"),
    ("bclr #0,RAM.w", "bclr.b #$0, $c7a4.w"),
    ("lsl.w #3,d1", "lsl.w #$3, d1"),
    ("lsl.l #2,d0", "lsl.l #$2, d0"),
    ("lsl.l #7,d0", "lsl.l #$7, d0"),
    ("lsr.w #4,d3", "lsr.w #$4, d3"),
    ("swap d0", "swap d0"),
    ("divu.w #10,d0", "divu.w #$a, d0"),
    ("divu.w #100,d0", "divu.w #$64, d0"),
    ("movem.l d0-d3/a0-a5,-(sp)", "movem.l d0-d3/a0-a5, -(a7)"),
    ("movem.l (sp)+,d0-d3/a0-a5", "movem.l (a7)+, d0-d3/a0-a5"),
    ("jmp FAR", "jmp $f8c6.l"),
    ("jsr FAR", "jsr $f8c6.l"),
    ("rts", "rts"),
]


@pytest.mark.parametrize("source, expected", FORMS, ids=[s for s, _e in FORMS])
def test_each_form_disassembles_to_itself(source, expected):
    code, _labels = m68k.assemble(f"        {source}\n", ORIGIN, SYMS)
    assert _listing(code) == [expected]


def test_branches_labels_and_pc_relative_data():
    src = """
start:  moveq   #SEVEN,d1
.loop:  move.b  (a1)+,d3
        dbra    d1,.loop
        bne.s   .out
        beq.w   start
        bsr.s   sub
        lea     table(pc),a1
.out:   bra.s   start
sub:    rts
table:  dc.b    1,2,3
        even
        dc.w    $1234
"""
    code, labels = m68k.assemble(src, ORIGIN, SYMS)
    assert labels["start"] == ORIGIN and labels["start.loop"] == ORIGIN + 2
    lines = _listing(code[: labels["table"] - ORIGIN])
    assert lines == [
        "moveq #$7, d1",
        "move.b (a1)+, d3",
        f"dbra d1, ${ORIGIN + 2:x}",
        f"bne.b ${labels['start.out']:x}",
        f"beq.w ${ORIGIN:x}",
        f"bsr.b ${labels['sub']:x}",
        f"lea.l ${labels['table']:x}(pc), a1",
        f"bra.b ${ORIGIN:x}",
        "rts",
    ]
    assert code[labels["table"] - ORIGIN :] == bytes([1, 2, 3, 0, 0x12, 0x34])


def test_sections_place_code_and_resolve_across_them():
    src = """
        section a
one:    jsr     two
        rts
        section b
two:    bra.s   .x
        rts
.x:     jmp     one
"""
    out, labels = m68k.assemble_sections(src, {"a": 0x2000, "b": 0x8000})
    assert labels == {"one": 0x2000, "two": 0x8000, "two.x": 0x8004}
    assert _listing(out["a"], 0x2000) == ["jsr $8000.l", "rts"]
    assert _listing(out["b"], 0x8000) == ["bra.b $8004", "rts", "jmp $2000.l"]


@pytest.mark.parametrize(
    "src, match",
    [
        ("        jmp NOWHERE\n", "unknown symbol 'NOWHERE'"),
        ("        bra.s FAR\n", "short branch"),
        ("a:      bra.s b\nb:      rts\n", "short branch"),  # displacement 0 means .w
        ("        moveq #200,d0\n", "moveq value 200"),
        ("        addq.w #9,d0\n", "addq value 9"),
        ("        dc.b 1\n        rts\n", "odd address"),
        ("        nop\n", "unsupported instruction"),
        ("        move.b d0,a0\n", "movea.b"),
        ("        lea $123456.w,a0\n", "no 16-bit absolute form"),
        ("x:\nx:\n", "defined twice"),
        ("        section nope\n", "unknown section"),
    ],
)
def test_errors_name_the_line(src, match):
    with pytest.raises(m68k.AsmError, match=match):
        m68k.assemble(src, ORIGIN, SYMS)
