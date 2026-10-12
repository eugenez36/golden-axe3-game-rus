"""Nemesis -- SEGA's tile compression scheme. Decoder and encoder.

The implementation was lifted straight from the game's own disassembly:
  0x0122FC  NemDec        -- decompress into the VDP data port
  0x01230E  NemDecToRAM   -- decompress into memory
  0x0123B2  build the code table
  0x012434  initialise the bit reader
  0x01243E  read n bits without shifting
  0x012452  shift by n bits

Format
------
  word    header: bit 15 = XOR mode, bits 0..14 = tile count
  ...     code table, terminated by 0xFF
  ...     bit stream, read MSB first

The code table is a sequence of:
  a descriptor (>= 0x80, low nibble = pixel value), followed by
  (info byte < 0x80, code byte) pairs until the next descriptor or 0xFF.
  info byte: bits 0..3 = code length, bits 4..6 = run length minus one.

The stream is a Huffman code over (pixel, run length) symbols. A prefix of six
ones is reserved: ``peek(8) >= 0xFC`` means "the next 7 bits are literal"
(3 bits of run length, 4 bits of pixel). The code space is therefore 252 of 256.

A tile is 8 rows of 8 nibbles (4 bytes). In XOR mode the accumulator XORed
with the previous output row is emitted instead of the row itself.

Encoder notes (why it matches or beats SEGA's packer on all 14 blocks of this ROM)
--------------------------------------------------------------------------------
* Rare symbols are cheaper inline. A table entry costs 2 bytes plus ``f * len``
  bits of stream; inline costs 13 bits per occurrence and nothing in the table,
  so a symbol earns its table slot only when ``f * (13 - len) < 16``.
* Code lengths come from package-merge, not from a heuristic: plain Huffman
  yields codes longer than 8 bits, which the format cannot hold.
* The four reserved table entries (0xFC..0xFF) are modelled as four zero-weight
  phantom symbols inside package-merge rather than by lengthening codes
  afterwards. That alone saved 88 bytes on the font block.
"""

from __future__ import annotations

import struct

MAX_CODE_LEN = 8  # the info byte stores 4 bits, but the decoder indexes 8 bits
MAX_RUN = 8  # run length is stored in 3 bits as runlen-1
CODE_SPACE = 1 << MAX_CODE_LEN  # 256 decoder table entries
RESERVED = 4  # 0xFC..0xFF flag the inline mode
CODE_BUDGET = CODE_SPACE - RESERVED  # 252

TABLE_ENTRY_BITS = 16  # info byte + code byte per table symbol
INLINE_BITS = 13  # 6-bit prefix + 7 literal bits

Symbol = tuple[int, int]  # (pixel nibble, run length)


# ---------------------------------------------------------------- bit stream


class BitReader:
    """Bit-by-bit reading exactly as the game does: a 16-bit window, refilled by bytes."""

    def __init__(self, data: bytes, pos: int):
        self.data = data
        self.pos = pos
        self.window = (self._byte() << 8) | self._byte()
        self.avail = 16
        self.consumed = 0  # total bits consumed; used for exact block sizes

    def _byte(self) -> int:
        b = self.data[self.pos] if self.pos < len(self.data) else 0
        self.pos += 1
        return b

    def peek(self, n: int) -> int:
        return (self.window >> (self.avail - n)) & ((1 << n) - 1)

    def consume(self, n: int) -> None:
        self.avail -= n
        self.consumed += n
        if self.avail < 9:
            self.avail += 8
            self.window = ((self.window << 8) & 0xFFFF) | self._byte()


class BitWriter:
    """Write bits MSB first, in the order BitReader consumes them."""

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.nbits = 0

    def write(self, value: int, n: int) -> None:
        self.acc = (self.acc << n) | (value & ((1 << n) - 1))
        self.nbits += n
        while self.nbits >= 8:
            self.nbits -= 8
            self.out.append((self.acc >> self.nbits) & 0xFF)
        self.acc &= (1 << self.nbits) - 1

    def finish(self, slack: bool = True) -> bytes:
        if self.nbits:
            self.out.append((self.acc << (8 - self.nbits)) & 0xFF)
            self.acc = 0
            self.nbits = 0
        # The reader keeps 16 bits in its window and fetches ahead; without two
        # spare bytes the last code would pull in whatever follows the block.
        # In a ROM that "whatever" is the next block, so the slack is not
        # needed there -- see strip_slack().
        return bytes(self.out) + (b"\x00\x00" if slack else b"")


# ---------------------------------------------------------------- decoding


def _build_code_table(data: bytes, pos: int) -> tuple[dict[int, tuple[int, int, int]], int]:
    """Decoder table: 8-bit index -> (code length, run length, pixel).

    Mirrors 0x0123B2 literally, including the fact that entries with a code
    shorter than 8 bits occupy all 2^(8-len) indices sharing that prefix.
    """
    table: dict[int, tuple[int, int, int]] = {}
    desc = data[pos]
    pos += 1
    while True:
        if desc == 0xFF:
            return table, pos
        nibble = desc & 0x0F
        while True:
            info = data[pos]
            pos += 1
            if info >= 0x80:
                desc = info
                break
            runlen = (info & 0x70) >> 4
            codelen = info & 0x0F
            code_byte = data[pos]
            pos += 1
            entry = (codelen, runlen, nibble)
            if codelen == 8:
                table[code_byte] = entry
            else:
                shift = 8 - codelen
                base = (code_byte << shift) & 0xFF
                for i in range(1 << shift):
                    table[base + i] = entry


def _header(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"no Nemesis header at {offset:06X}: the data ends at {len(data):06X}")
    return struct.unpack_from(">H", data, offset)[0]


def _walk(data: bytes, offset: int, emit: bool) -> tuple[bytes, int]:
    """Shared decoder loop. Returns (raw tiles or b'', exact compressed size)."""
    header = _header(data, offset)
    xor_mode = bool(header & 0x8000)
    rows_total = (header & 0x7FFF) * 8

    try:
        table, pos = _build_code_table(data, offset + 2)
    except IndexError:
        raise ValueError(f"truncated Nemesis block at {offset:06X}: code table cut short") from None
    br = BitReader(data, pos)

    out = bytearray()
    acc = 0  # d4: row accumulator
    nibbles = 8  # d3
    xor_acc = 0  # d2
    rows_done = 0

    while rows_done < rows_total:
        code = br.peek(8)
        if code >= 0xFC:
            br.consume(6)
            payload = br.peek(7)
            br.consume(7)
        else:
            entry = table.get(code)
            if entry is None:
                raise ValueError(f"code {code:02X} missing from the table (block {offset:06X})")
            codelen, runlen, nibble = entry
            br.consume(codelen)
            payload = (runlen << 4) | nibble

        runs = (payload & 0xF0) >> 4
        nibble = payload & 0x0F

        for _ in range(runs + 1):
            if emit:
                acc = ((acc << 4) | nibble) & 0xFFFFFFFF
            nibbles -= 1
            if nibbles == 0:
                if emit:
                    if xor_mode:
                        xor_acc ^= acc
                        out += struct.pack(">I", xor_acc)
                    else:
                        out += struct.pack(">I", acc)
                    acc = 0
                rows_done += 1
                nibbles = 8
                if rows_done >= rows_total:
                    break

    stream_bytes = (br.consumed + 7) // 8
    return bytes(out), (pos - offset) + stream_bytes


def decompress(data: bytes, offset: int) -> bytes:
    """Decompress the Nemesis block at ``offset`` inside ``data``. Returns raw 4bpp tiles."""
    return _walk(data, offset, emit=True)[0]


def decompress_blob(blob: bytes) -> bytes:
    """Decompress a standalone block (a ``.nem`` file) rather than a slice of a ROM.

    The bit reader fetches two bytes beyond the last code it acts on, so a block
    that is not followed by other data needs two spare bytes (see
    ``BitWriter.finish`` and ``strip_slack``).
    """
    return decompress(bytes(blob) + b"\x00\x00", 0)


def info(data: bytes, offset: int) -> dict:
    header = _header(data, offset)
    return {"offset": offset, "tiles": header & 0x7FFF, "xor": bool(header & 0x8000)}


def block_size(data: bytes, offset: int) -> int:
    """Exact size in bytes of the compressed block at ``offset``.

    Computed from the number of bits the decoder actually consumes, so it is
    accurate to the byte. (An earlier version inferred it from the reader's
    position and was one byte short on 12 of the 14 blocks in this ROM.)
    """
    return _walk(data, offset, emit=False)[1]


def strip_slack(blob: bytes) -> bytes:
    """Drop the two spare bytes BitWriter.finish() appends.

    Safe when the block is followed by other data in the ROM: the decoder only
    peeks past the last code, it never acts on those bits.
    """
    return blob[:-2] if blob.endswith(b"\x00\x00") else blob


# ---------------------------------------------------------------- encoding


def _nibble_stream(raw: bytes, xor_mode: bool) -> list[int]:
    """Tiles -> nibble stream. XOR mode encodes the difference between rows."""
    if len(raw) % 4:
        raise ValueError("data must be a multiple of 4 bytes (one tile row)")
    nibbles = []
    prev = 0
    for i in range(0, len(raw), 4):
        row = struct.unpack_from(">I", raw, i)[0]
        value = (row ^ prev) if xor_mode else row
        if xor_mode:
            prev = row
        for shift in range(28, -4, -4):
            nibbles.append((value >> shift) & 0x0F)
    return nibbles


def _runs_greedy(nibbles: list[int]) -> list[Symbol]:
    """Nibble stream -> (pixel, run) symbols, runs no longer than MAX_RUN."""
    runs = []
    i = 0
    n = len(nibbles)
    while i < n:
        v = nibbles[i]
        j = i + 1
        while j < n and nibbles[j] == v and j - i < MAX_RUN:
            j += 1
        runs.append((v, j - i))
        i = j
    return runs


def _runs_optimal(nibbles: list[int], cost: dict[Symbol, int]) -> list[Symbol]:
    """Re-cut runs by dynamic programming once code lengths are known.

    Twelve identical pixels can be cut as 8+4 or 6+6; the cheaper cut is the
    one whose symbols got the shorter codes. Each homogeneous group is solved
    on its own: runs never cross a pixel boundary.
    """
    default = MAX_CODE_LEN + 4
    out: list[Symbol] = []
    i = 0
    n = len(nibbles)
    while i < n:
        v = nibbles[i]
        j = i
        while j < n and nibbles[j] == v:
            j += 1
        length = j - i

        # best[k]: cheapest cut of k pixels; choice[k]: length of the last run
        best: list[int | None] = [0] + [None] * length
        choice = [0] * (length + 1)
        for k in range(1, length + 1):
            for r in range(1, min(MAX_RUN, k) + 1):
                prev = best[k - r]
                if prev is None:
                    continue
                c = prev + cost.get((v, r), default)
                if best[k] is None or c < best[k]:
                    best[k] = c
                    choice[k] = r
        parts = []
        k = length
        while k > 0:
            r = choice[k]
            parts.append((v, r))
            k -= r
        out.extend(reversed(parts))
        i = j
    return out


def _package_merge(freqs: dict, max_len: int = MAX_CODE_LEN) -> dict:
    """Optimal code lengths under a depth limit (Larmore-Hirschberg).

    Plain Huffman may produce codes longer than 8 bits, which Nemesis cannot
    store. Package-merge solves the constrained problem exactly by reduction
    to the coin-collector problem: a coin for symbol i at level t has width
    2^-t and weight f_i; collect total width n-1 at minimum weight. The number
    of coins picked for a symbol is its code length.
    """
    if not freqs:
        return {}
    if len(freqs) == 1:
        return {next(iter(freqs)): 1}

    syms = sorted(freqs.items(), key=lambda kv: (kv[1], repr(kv[0])))
    n = len(syms)

    packages: list[tuple[int, tuple]] = []
    for _t in range(max_len, 0, -1):
        level = sorted([(f, (sym,)) for sym, f in syms] + packages, key=lambda x: x[0])
        packages = [
            (level[k][0] + level[k + 1][0], level[k][1] + level[k + 1][1])
            for k in range(0, len(level) - 1, 2)
        ]

    packages.sort(key=lambda x: x[0])
    lengths = {sym: 0 for sym, _f in syms}
    for _w, members in packages[: n - 1]:
        for sym in members:
            lengths[sym] += 1

    # degenerate cases: a zero-length code is impossible
    for sym in lengths:
        if lengths[sym] == 0:
            lengths[sym] = max_len
    return lengths


def _kraft(lengths: dict) -> int:
    return sum(1 << (MAX_CODE_LEN - ln) for ln in lengths.values())


def _fit_budget(lengths: dict, freqs: dict, budget: int = CODE_BUDGET) -> dict:
    """Free room for the inline prefix by lengthening the cheapest codes.

    Package-merge fills all 256 entries, but the last four (0xFC..0xFF) belong
    to the inline flag. Lengthening a symbol by one bit costs f_i and frees
    2^(7-l) entries; pick the best ratio each time.
    """
    lengths = dict(lengths)
    while _kraft(lengths) > budget:
        best = None
        for sym, ln in lengths.items():
            if ln >= MAX_CODE_LEN:
                continue
            freed = 1 << (MAX_CODE_LEN - 1 - ln)
            price = freqs[sym] / freed
            if best is None or price < best[0]:
                best = (price, sym)
        if best is None:
            raise ValueError("symbols do not fit into the Nemesis code space")
        lengths[best[1]] += 1
    return lengths


def _choose_lengths(freqs: dict) -> dict:
    """Optimal lengths given that 4 table entries are reserved.

    Instead of lengthening codes after package-merge, add four zero-weight
    phantom symbols: they sink to maximum depth and take exactly the four
    entries (0xFC..0xFF) the decoder treats as inline, leaving the real
    symbols with an optimal code over the remaining 252.
    """
    if not freqs:
        return {}
    padded = dict(freqs)
    phantoms = [("__reserved__", i) for i in range(RESERVED)]
    for ph in phantoms:
        padded[ph] = 0
    lengths = _package_merge(padded)
    for ph in phantoms:
        lengths.pop(ph, None)
    if _kraft(lengths) > CODE_BUDGET:
        lengths = _fit_budget(lengths, freqs)
    return lengths


def _split_inline(freqs: dict) -> tuple[dict, set]:
    """Decide which symbols stay in the table and which go inline.

    A table symbol costs 2 bytes of table plus f*len bits of stream; an inline
    symbol costs no table space but 13 bits per occurrence. Keep a symbol in
    the table only if it pays for its 16 bits: f*(13 - len) < 16 sends it
    inline. For len = 8 that is f <= 3.

    This is exactly where SEGA's packer used to win: on XOR blocks it keeps 56
    table symbols against about a hundred for the naive approach, nearly 100
    bytes of difference.
    """
    table_syms = dict(freqs)
    inline: set = set()
    for _ in range(32):
        if not table_syms:
            break
        lengths = _choose_lengths(table_syms)
        victims = [
            sym
            for sym, f in table_syms.items()
            if f * INLINE_BITS < TABLE_ENTRY_BITS + f * lengths[sym]
        ]
        if not victims:
            break
        for sym in victims:
            del table_syms[sym]
            inline.add(sym)
    return table_syms, inline


def _assign_codes(lengths: dict) -> dict:
    """Canonical codes: by increasing length, consecutive values from zero.

    The occupied part of the table is then the prefix [0, sum) and the
    reserved tail 0xFC..0xFF stays free for the inline mode.
    """
    codes = {}
    code = 0
    for sym in sorted(lengths, key=lambda s: (lengths[s], s)):
        ln = lengths[sym]
        step = 1 << (MAX_CODE_LEN - ln)
        if code % step:
            code += step - (code % step)
        codes[sym] = code >> (MAX_CODE_LEN - ln)
        code += step
    if code > CODE_BUDGET:
        raise ValueError(f"codes occupy {code} of {CODE_BUDGET} allowed table entries")
    return codes


def _emit_table(lengths: dict, codes: dict) -> bytes:
    """Code table: one descriptor per pixel value, then (info, code) pairs."""
    out = bytearray()
    by_nibble: dict[int, list[Symbol]] = {}
    for nibble, runlen in lengths:
        by_nibble.setdefault(nibble, []).append((nibble, runlen))
    for nibble in sorted(by_nibble):
        out.append(0x80 | nibble)
        for sym in sorted(by_nibble[nibble], key=lambda s: s[1]):
            runlen = sym[1]
            out.append(((runlen - 1) << 4) | lengths[sym])
            out.append(codes[sym])
    out.append(0xFF)
    return bytes(out)


def _emit_stream(runs, lengths, codes, slack: bool) -> bytes:
    bw = BitWriter()
    for sym in runs:
        if sym in codes:
            bw.write(codes[sym], lengths[sym])
        else:
            bw.write(0x3F, 6)  # inline prefix
            bw.write(((sym[1] - 1) << 4) | sym[0], 7)
    return bw.finish(slack)


def _build(raw: bytes, xor_mode: bool, nibbles, runs, use_inline: bool, slack: bool):
    freqs: dict = {}
    for sym in runs:
        freqs[sym] = freqs.get(sym, 0) + 1

    if use_inline:
        table_syms, inline = _split_inline(freqs)
    else:
        table_syms, inline = dict(freqs), set()

    lengths = _choose_lengths(table_syms) if table_syms else {}
    codes = _assign_codes(lengths) if lengths else {}

    # re-cut runs against the actual symbol prices and encode with those
    cost = dict(lengths)
    for sym in inline:
        cost[sym] = INLINE_BITS
    runs = _runs_optimal(nibbles, cost)

    tiles = len(raw) // 32
    header = ((0x8000 if xor_mode else 0) | tiles) & 0xFFFF
    blob = (
        struct.pack(">H", header)
        + _emit_table(lengths, codes)
        + _emit_stream(runs, lengths, codes, slack)
    )
    return blob, runs


def _compress_one(raw: bytes, xor_mode: bool, slack: bool) -> bytes:
    """Try the strategies and keep the shortest result.

    The strategies differ in whether rare symbols go inline: on some blocks
    that saves about a hundred bytes of table, on others it only hurts. Each
    runs twice so the run cut can be refined against the real prices.
    """
    nibbles = _nibble_stream(raw, xor_mode)
    base = _runs_greedy(nibbles)

    best = None
    for use_inline in (True, False):
        runs = base
        for _ in range(2):
            blob, runs = _build(raw, xor_mode, nibbles, runs, use_inline, slack)
            if best is None or len(blob) < len(best):
                best = blob
    return best


def compress(raw: bytes, xor_mode: bool | None = None, slack: bool = True) -> bytes:
    """Compress raw 4bpp tiles into a Nemesis block.

    ``xor_mode=None`` tries both modes and keeps the shorter. The result is
    always verified by decompression: this function cannot silently corrupt
    graphics. ``slack=False`` omits the two trailing spare bytes (use when the
    block is written into a ROM where other data follows it).
    """
    if len(raw) % 32:
        raise ValueError("data must be a multiple of 32 bytes (one 8x8 4bpp tile)")
    if not raw:
        raise ValueError("nothing to compress")
    if (len(raw) // 32) > 0x7FFF:
        raise ValueError("too many tiles for the 15-bit count in the header")

    modes = (False, True) if xor_mode is None else (xor_mode,)
    best = None
    for mode in modes:
        blob = _compress_one(raw, mode, slack)
        if decompress_blob(blob) != raw:
            raise RuntimeError(
                f"Nemesis self-check failed (XOR={mode}): the packer produced a block that "
                "does not decode to its input. This is a bug in ga3; please report it."
            )
        if best is None or len(blob) < len(best):
            best = blob
    return best
