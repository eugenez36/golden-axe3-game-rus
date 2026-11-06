"""A small two-pass 68000 assembler for the patches in ``assets/patches/*.s``.

It knows the instructions and addressing modes those patches use and nothing
else; anything outside that set is an :class:`AsmError` naming the line.
Syntax is Motorola's: ``label:``, local ``.label`` (scoped to the last global
label), ``; comment``, ``$hex``/decimal numbers, ``SYMBOL`` and ``SYMBOL+n``
expressions, size suffixes ``.b .w .l`` and ``.s`` for short branches.

An absolute address without a suffix is assembled as ``.l``; ``ADDR.w`` is
the 16-bit form (sign-extended by the CPU, so ``$C7A4.w`` is ``$FFC7A4``).
Instruction sizes never depend on symbol values, so the first pass places
every label and the second encodes. Directives: ``dc.b``, ``dc.w``, ``even``
and ``section NAME``: each section has its own location counter, starting at
the origin the caller gives for that name (see :func:`assemble_sections`).

Every output is meant to be checked by disassembling it again (Capstone); the
tests do that for each supported form.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass


class AsmError(ValueError):
    pass


SIZES = {"b": 0, "w": 1, "l": 2}
CONDITIONS = {
    "ra": 0x0, "sr": 0x1, "hi": 0x2, "ls": 0x3, "cc": 0x4, "hs": 0x4, "cs": 0x5, "lo": 0x5,
    "ne": 0x6, "eq": 0x7, "vc": 0x8, "vs": 0x9, "pl": 0xA, "mi": 0xB, "ge": 0xC, "lt": 0xD,
    "gt": 0xE, "le": 0xF,
}  # fmt: skip
_EA_MODE = {"dn": 0, "an": 1, "ind": 2, "postinc": 3, "predec": 4, "disp": 5, "index": 6}
_EA_SPECIAL = {"absw": 0, "absl": 1, "pcdisp": 2, "imm": 4}
_EXT_BYTES = {"dn": 0, "an": 0, "ind": 0, "postinc": 0, "predec": 0, "disp": 2, "index": 2,
              "absw": 2, "absl": 4, "pcdisp": 2}  # fmt: skip


@dataclass
class Operand:
    mode: str  # dn an ind postinc predec disp index absw absl pcdisp imm sr reglist
    reg: int = 0
    expr: str = ""  # displacement, address or immediate expression
    index: tuple[str, int, str] | None = None  # ("d"|"a", register, "w"|"l")
    mask: int = 0  # register list: bit 0 = d0 ... bit 15 = a7


@dataclass
class Line:
    number: int
    text: str
    label: str | None
    op: str | None  # mnemonic with suffix, lower case
    args: list[str]
    address: int = 0
    size: int = 0


def _split_args(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _parse_lines(source: str) -> list[Line]:
    lines = []
    for n, raw in enumerate(source.splitlines(), 1):
        text = raw.split(";", 1)[0].rstrip()
        if not text.strip():
            continue
        label = None
        m = re.match(r"^\s*(\.?[A-Za-z_]\w*):", text)
        if m:
            label = m.group(1)
            text = text[m.end() :]
        text = text.strip()
        if not text:
            lines.append(Line(n, raw, label, None, []))
            continue
        parts = text.split(None, 1)
        args = _split_args(parts[1]) if len(parts) > 1 else []
        lines.append(Line(n, raw, label, parts[0].lower(), args))
    return lines


_REG = re.compile(r"^(d[0-7]|a[0-7]|sp)$", re.IGNORECASE)


def _reg(s: str) -> tuple[str, int]:
    s = s.lower()
    return ("a", 7) if s == "sp" else (s[0], int(s[1]))


def _reglist(s: str) -> int:
    mask = 0
    for part in s.lower().split("/"):
        lo, _, hi = part.partition("-")
        k0, r0 = _reg(lo)
        k1, r1 = _reg(hi) if hi else (k0, r0)
        if k0 != k1:
            raise AsmError(f"register range {part!r} mixes data and address registers")
        for r in range(r0, r1 + 1):
            mask |= 1 << ((0 if k0 == "d" else 8) + r)
    return mask


def _operand(s: str) -> Operand:
    t = s.strip()
    low = t.lower()
    if low == "sr":
        return Operand("sr")
    if _REG.match(t):
        k, r = _reg(t)
        return Operand("dn" if k == "d" else "an", r)
    if "/" in t or re.match(r"^[da][0-7]-[da][0-7]$", low):
        return Operand("reglist", mask=_reglist(t))
    if t.startswith("#"):
        return Operand("imm", expr=t[1:])
    if m := re.match(r"^\((a[0-7]|sp)\)\+$", low):
        return Operand("postinc", _reg(m.group(1))[1])
    if m := re.match(r"^-\((a[0-7]|sp)\)$", low):
        return Operand("predec", _reg(m.group(1))[1])
    if m := re.match(r"^\((a[0-7]|sp)\)$", low):
        return Operand("ind", _reg(m.group(1))[1])
    if m := re.match(r"^(.*)\(pc\)$", low):
        return Operand("pcdisp", expr=t[: len(m.group(1))])
    if m := re.match(r"^(.*)\((a[0-7]|sp),([da][0-7])(?:\.([wl]))?\)$", low):
        k, r = _reg(m.group(3))
        expr = t[: len(m.group(1))] or "0"
        return Operand("index", _reg(m.group(2))[1], expr, (k, r, m.group(4) or "w"))
    if m := re.match(r"^(.*)\((a[0-7]|sp)\)$", low):
        return Operand("disp", _reg(m.group(2))[1], t[: len(m.group(1))] or "0")
    if low.endswith(".w"):
        return Operand("absw", expr=t[:-2])
    if low.endswith(".l"):
        return Operand("absl", expr=t[:-2])
    return Operand("absl", expr=t)


def _ext_size(o: Operand, size: int) -> int:
    if o.mode == "imm":
        return 4 if size == 2 else 2
    if o.mode not in _EXT_BYTES:
        raise AsmError(f"{o.mode} cannot be an effective address here")
    return _EXT_BYTES[o.mode]


def _ea_bits(o: Operand) -> int:
    if o.mode in _EA_MODE:
        return _EA_MODE[o.mode] << 3 | o.reg
    if o.mode in _EA_SPECIAL:
        return 7 << 3 | _EA_SPECIAL[o.mode]
    raise AsmError(f"{o.mode} cannot be an effective address here")


def _s16(v: int) -> int:
    """A 16-bit displacement of an address: ``$C7A4`` is the sign-extended ``$FFFFC7A4``."""
    if 0x8000 <= v <= 0xFFFF:
        v -= 0x10000
    if not -0x8000 <= v <= 0x7FFF:
        raise AsmError(f"displacement {v} out of range")
    return v


def _rel16(v: int, what: str) -> int:
    """A 16-bit relative displacement (branches, ``d16(pc)``): the sign is the sign."""
    if not -0x8000 <= v <= 0x7FFF:
        raise AsmError(f"{what} is {v} bytes away, beyond the 16-bit displacement")
    return v


class _Assembler:
    def __init__(self, source: str, sections: dict[str, int], symbols: dict[str, int]):
        self.sections = dict(sections)
        self.symbols = dict(symbols)
        self.lines = _parse_lines(source)
        self.labels: dict[str, int] = {}
        self.sizing = True

    # -------------------------------------------------------- values

    def value(self, expr: str, scope: str) -> int:
        if self.sizing:
            return 0
        total = 0
        for sign, term in re.findall(r"([+-]?)\s*([^+\-\s]+)", expr.replace(" ", "")):
            if re.match(r"^\$[0-9a-fA-F]+$", term):
                v = int(term[1:], 16)
            elif re.match(r"^%[01]+$", term):
                v = int(term[1:], 2)
            elif term.isdigit():
                v = int(term)
            else:
                name = scope + term if term.startswith(".") else term
                if name in self.labels:
                    v = self.labels[name]
                elif term in self.symbols:
                    v = self.symbols[term]
                else:
                    raise AsmError(f"unknown symbol {term!r}")
            total += -v if sign == "-" else v
        return total

    def ext(self, o: Operand, size: int, at: int, scope: str) -> bytes:
        """Extension words of ``o``; ``at`` is the address of the first of them."""
        if self.sizing:
            return b"\0" * _ext_size(o, size)
        if o.mode == "imm":
            v = self.value(o.expr, scope)
            if size == 2:
                return struct.pack(">I", v & 0xFFFFFFFF)
            lo, hi = (-0x80, 0xFF) if size == 0 else (-0x8000, 0xFFFF)
            if not lo <= v <= hi:
                raise AsmError(f"immediate {v} does not fit .{'bwl'[size]}")
            return struct.pack(">H", v & (0xFF if size == 0 else 0xFFFF))
        if o.mode == "disp":
            return struct.pack(">h", _s16(self.value(o.expr, scope)))
        if o.mode == "index":
            k, r, w = o.index
            d = self.value(o.expr, scope)
            if not -0x80 <= d <= 0x7F:
                raise AsmError(f"index displacement {d} out of range")
            return struct.pack(">H", (k == "a") << 15 | r << 12 | (w == "l") << 11 | (d & 0xFF))
        if o.mode == "absw":
            v = self.value(o.expr, scope) & 0xFFFFFFFF
            if not (v <= 0xFFFF or v >= 0xFFFF8000):
                raise AsmError(f"${v:X} has no 16-bit absolute form")
            return struct.pack(">H", v & 0xFFFF)
        if o.mode == "absl":
            return struct.pack(">I", self.value(o.expr, scope) & 0xFFFFFFFF)
        if o.mode == "pcdisp":
            return struct.pack(
                ">h", _rel16(self.value(o.expr, scope) - at, "the pc-relative operand")
            )
        return b""

    # -------------------------------------------------------- instructions

    def encode(self, line: Line, scope: str) -> bytes:  # noqa: C901 - one branch per mnemonic
        op, args, here = line.op, line.args, line.address
        base, _, suffix = op.partition(".")
        size = SIZES.get(suffix, 1)

        def ea(word: int, o: Operand, sz: int, offset: int = 2) -> bytes:
            return struct.pack(">H", word | _ea_bits(o)) + self.ext(o, sz, here + offset, scope)

        if base == "dc":
            if suffix not in ("b", "w"):
                raise AsmError("dc needs .b or .w")
            fmt, mask = (">B", 0xFF) if suffix == "b" else (">H", 0xFFFF)
            return b"".join(struct.pack(fmt, self.value(a, scope) & mask) for a in args)
        if base == "even":
            return b"\0" if here % 2 else b""
        if base == "rts" and not args:
            return b"\x4e\x75"
        cond = base[1:] if base.startswith("b") else None
        if base in ("bra", "bsr") or cond in CONDITIONS:
            cc = {"bra": 0, "bsr": 1}.get(base, CONDITIONS.get(cond, 0))
            target = self.value(args[0], scope)
            if suffix == "s":
                disp = 0 if self.sizing else target - (here + 2)
                if not self.sizing and (not -0x80 <= disp <= 0x7F or disp == 0):
                    raise AsmError(f"short branch to {args[0]} is {disp} bytes away")
                return struct.pack(">BB", 0x60 | cc, disp & 0xFF)
            disp = 0 if self.sizing else _rel16(target - (here + 2), f"branch to {args[0]}")
            return struct.pack(">Hh", 0x6000 | cc << 8, disp)
        if base in ("dbra", "dbf"):
            d = _operand(args[0])
            disp = (
                0
                if self.sizing
                else _rel16(self.value(args[1], scope) - (here + 2), f"{base} to {args[1]}")
            )
            return struct.pack(">Hh", 0x51C8 | d.reg, disp)

        o = [_operand(a) for a in args]
        if base == "moveq":
            v = self.value(o[0].expr, scope)
            if not -128 <= v <= 127:
                raise AsmError(f"moveq value {v} out of range")
            return struct.pack(">BB", 0x70 | o[1].reg << 1, v & 0xFF)
        if base == "move" and o[1].mode == "sr":
            return ea(0x46C0, o[0], 1)
        if base == "movem":
            if o[0].mode == "reglist":  # registers to memory
                mask, mem = o[0].mask, o[1]
                if mem.mode == "predec":
                    mask = int(f"{mask:016b}"[::-1], 2)
                word = 0x4880
            else:
                mem, mask, word = o[0], o[1].mask, 0x4C80
            word |= (size == 2) << 6 | _ea_bits(mem)
            return struct.pack(">HH", word, mask) + self.ext(mem, size, here + 4, scope)
        if base in ("move", "movea"):
            src, dst = o
            if dst.mode == "an" and size == 0:
                raise AsmError("movea.b does not exist")
            d = _ea_bits(dst)
            word = {0: 1, 1: 3, 2: 2}[size] << 12 | (d & 7) << 9 | (d >> 3) << 6 | _ea_bits(src)
            src_ext = self.ext(src, size, here + 2, scope)
            return (
                struct.pack(">H", word)
                + src_ext
                + self.ext(dst, size, here + 2 + len(src_ext), scope)
            )
        if base == "lea":
            return ea(0x41C0 | o[1].reg << 9, o[0], 2)
        if base in ("jmp", "jsr"):
            return ea(0x4EC0 if base == "jmp" else 0x4E80, o[0], 2)
        if base in ("clr", "tst"):
            return ea((0x4200 if base == "clr" else 0x4A00) | size << 6, o[0], size)
        if base == "swap":
            return struct.pack(">H", 0x4840 | o[0].reg)
        if base == "exg":
            if o[0].mode == o[1].mode == "an":
                return struct.pack(">H", 0xC148 | o[0].reg << 9 | o[1].reg)
            if o[0].mode == o[1].mode == "dn":
                return struct.pack(">H", 0xC140 | o[0].reg << 9 | o[1].reg)
            raise AsmError("exg supports two data or two address registers")
        if base in ("addq", "subq"):
            v = 1 if self.sizing else self.value(o[0].expr, scope)
            if not 1 <= v <= 8:
                raise AsmError(f"{base} value {v} out of range")
            return ea(0x5000 | (v & 7) << 9 | (base == "subq") << 8 | size << 6, o[1], size)
        if base in ("ori", "andi", "subi", "addi", "cmpi"):
            code = {"ori": 0x0000, "andi": 0x0200, "subi": 0x0400, "addi": 0x0600, "cmpi": 0x0C00}
            imm = self.ext(o[0], size, here + 2, scope)
            word = code[base] | size << 6 | _ea_bits(o[1])
            return struct.pack(">H", word) + imm + self.ext(o[1], size, here + 2 + len(imm), scope)
        if base in ("add", "sub", "cmp"):
            hi = {"add": 0xD000, "sub": 0x9000, "cmp": 0xB000}[base]
            if o[1].mode == "dn":  # <ea>,Dn
                return ea(hi | o[1].reg << 9 | size << 6, o[0], size)
            if o[0].mode == "dn" and base != "cmp":  # Dn,<ea>
                return ea(hi | o[0].reg << 9 | 0x100 | size << 6, o[1], size)
            raise AsmError("unsupported operands")
        if base in ("adda", "suba", "cmpa"):
            hi = {"adda": 0xD000, "suba": 0x9000, "cmpa": 0xB000}[base]
            return ea(hi | o[1].reg << 9 | (0x1C0 if size == 2 else 0xC0), o[0], size)
        if base in ("btst", "bchg", "bclr", "bset") and o[0].mode == "imm":
            code = {"btst": 0x0800, "bchg": 0x0840, "bclr": 0x0880, "bset": 0x08C0}[base]
            bit = struct.pack(">H", self.value(o[0].expr, scope) & 0xFF)
            return (
                struct.pack(">H", code | _ea_bits(o[1])) + bit + self.ext(o[1], 0, here + 4, scope)
            )
        if base in ("lsl", "lsr", "asl", "asr") and o[0].mode == "imm" and o[1].mode == "dn":
            v = 1 if self.sizing else self.value(o[0].expr, scope)
            if not 1 <= v <= 8:
                raise AsmError(f"shift count {v} out of range")
            left, logical = base.endswith("l"), base.startswith("l")
            word = 0xE000 | (v & 7) << 9 | left << 8 | size << 6 | logical << 3 | o[1].reg
            return struct.pack(">H", word)
        if base in ("divu", "mulu"):
            return ea((0x80C0 if base == "divu" else 0xC0C0) | o[1].reg << 9, o[0], 1)
        raise AsmError("unsupported instruction")

    # -------------------------------------------------------- passes

    def _pass(self) -> dict[str, bytes]:
        current = ""
        if current not in self.sections:
            current = next(iter(self.sections))
        addrs = dict(self.sections)
        outs = {name: bytearray() for name in self.sections}
        scope = ""
        for line in self.lines:
            if line.op == "section":
                if len(line.args) != 1 or line.args[0] not in self.sections:
                    raise AsmError(f"line {line.number}: unknown section {' '.join(line.args)!r}")
                current = line.args[0]
                continue
            addr, out = addrs[current], outs[current]
            if line.label:
                if not line.label.startswith("."):
                    scope = line.label
                name = scope + line.label if line.label.startswith(".") else line.label
                if self.sizing:
                    if name in self.labels:
                        raise AsmError(f"line {line.number}: label {line.label!r} defined twice")
                    self.labels[name] = addr
            line.address = addr
            if line.op:
                if line.op not in ("dc.b", "even") and addr % 2:
                    raise AsmError(f"line {line.number}: instruction at odd address ${addr:X}")
                try:
                    code = self.encode(line, scope)
                except AsmError as exc:
                    raise AsmError(f"line {line.number}: {exc}: {line.text.strip()}") from None
                except (IndexError, KeyError, TypeError, ValueError):
                    raise AsmError(
                        f"line {line.number}: cannot parse: {line.text.strip()}"
                    ) from None
                if self.sizing:
                    line.size = len(code)
                elif len(code) != line.size:
                    raise AsmError(f"line {line.number}: size changed between passes")
                out += code
                addrs[current] = addr + len(code)
        return {name: bytes(out) for name, out in outs.items()}

    def run(self) -> dict[str, bytes]:
        self.sizing = True
        self._pass()
        self.sizing = False
        return self._pass()


def assemble(
    source: str, origin: int, symbols: dict[str, int] | None = None
) -> tuple[bytes, dict[str, int]]:
    """Assemble ``source`` (no sections) to run at ``origin``: its bytes and label addresses."""
    a = _Assembler(source, {"": origin}, symbols or {})
    return a.run()[""], dict(a.labels)


def assemble_sections(
    source: str, sections: dict[str, int], symbols: dict[str, int] | None = None
) -> tuple[dict[str, bytes], dict[str, int]]:
    """Assemble ``source`` whose ``section NAME`` directives place code at ``sections[NAME]``.

    Lines before the first directive go to the first section given. Returns the
    bytes of every section and every label's address.
    """
    if not sections:
        raise AsmError("no sections given")
    a = _Assembler(source, sections, symbols or {})
    return a.run(), dict(a.labels)
