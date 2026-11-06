"""Cartridge image: header, checksum, diff and IPS patches.

Facts verified on this ROM (Golden Axe 3 (RUS), 1 MiB):
  * the checksum word sits at 0x18E and is the sum of big-endian 16-bit words
    from 0x200 to the end of the image, modulo 0x10000;
  * "ROM start" / "ROM end" are a pair of longs at 0x1A0 / 0x1A4;
  * on the reference image both header fixes are no-ops, so a rebuild of
    unchanged assets is byte-identical.
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys
from array import array

HDR_CHECKSUM = 0x18E
HDR_ROM_START = 0x1A0
HDR_ROM_END = 0x1A4
CHECKSUM_FROM = 0x200


class Rom:
    """A cartridge image in memory. All edits go through the ``data`` bytearray."""

    def __init__(self, data: bytes | bytearray, path: str | None = None):
        self.data = bytearray(data)
        self.path = path

    # -- load / save ---------------------------------------------------------

    @classmethod
    def load(cls, path: str | os.PathLike) -> Rom:
        with open(path, "rb") as fh:
            return cls(fh.read(), str(path))

    def save(self, path: str | os.PathLike, fix_header: bool = True) -> str:
        """Write the image. Fixes the checksum and ROM-end fields unless told not to.

        The path is mandatory on purpose: the toolkit never overwrites the
        image it was loaded from. Builds go to ``build/``, the reference stays
        read-only.
        """
        path = str(path)
        if fix_header:
            self.fix_rom_end()
            self.fix_checksum()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(self.data)
        os.replace(tmp, path)
        return path

    # -- header --------------------------------------------------------------

    def header_field(self, off: int, size: int) -> str:
        return self.data[off : off + size].decode("ascii", "replace").rstrip()

    @property
    def domestic_name(self) -> str:
        return self.header_field(0x120, 48)

    @property
    def serial(self) -> str:
        return self.header_field(0x180, 14)

    def compute_checksum(self) -> int:
        """Sum of big-endian 16-bit words from 0x200 to the end, mod 0x10000."""
        body = self.data[CHECKSUM_FROM:]
        if len(body) & 1:  # odd tail: pad with zero, as the boot loader does
            body = body + b"\x00"
        words = array("H", body)
        if sys.byteorder == "little":
            words.byteswap()
        return sum(words) & 0xFFFF

    def stored_checksum(self) -> int:
        return self.u16(HDR_CHECKSUM)

    def fix_checksum(self) -> int:
        cs = self.compute_checksum()
        self.set_u16(HDR_CHECKSUM, cs)
        return cs

    def checksum_ok(self) -> bool:
        return self.stored_checksum() == self.compute_checksum()

    def rom_bounds(self) -> tuple[int, int]:
        return self.u32(HDR_ROM_START), self.u32(HDR_ROM_END)

    def fix_rom_end(self) -> int:
        """ROM end = address of the last byte of the image."""
        end = len(self.data) - 1
        self.set_u32(HDR_ROM_END, end)
        return end

    def expand(self, size: int = 0x200000, fill: int = 0xFF) -> None:
        """Grow the image (e.g. to 2 MiB). The header is fixed on save()."""
        if size < len(self.data):
            raise ValueError("expand(): new size is smaller than the current image")
        self.data.extend(bytes([fill]) * (size - len(self.data)))

    # -- big-endian word access ----------------------------------------------

    def u16(self, off: int) -> int:
        return struct.unpack_from(">H", self.data, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from(">I", self.data, off)[0]

    def set_u16(self, off: int, val: int) -> None:
        struct.pack_into(">H", self.data, off, val & 0xFFFF)

    def set_u32(self, off: int, val: int) -> None:
        struct.pack_into(">I", self.data, off, val & 0xFFFFFFFF)

    def sha1(self) -> str:
        return hashlib.sha1(self.data).hexdigest()

    def summary(self) -> str:
        s, e = self.rom_bounds()
        return (
            f"{self.path or '<memory>'}\n"
            f"  size        {len(self.data)} (0x{len(self.data):X})\n"
            f"  name        {self.domestic_name!r}\n"
            f"  serial      {self.serial!r}\n"
            f"  rom bounds  0x{s:06X}..0x{e:06X}\n"
            f"  checksum    stored 0x{self.stored_checksum():04X} / "
            f"computed 0x{self.compute_checksum():04X} "
            f"{'OK' if self.checksum_ok() else 'MISMATCH'}\n"
            f"  sha1        {self.sha1()}"
        )


# ---------------------------------------------------------------- diff / IPS


def diff(a: bytes, b: bytes, max_gap: int = 8) -> list[tuple[int, bytes, bytes]]:
    """List of changes ``(offset, old, new)``. Edits closer than ``max_gap`` merge."""
    n = min(len(a), len(b))
    spans: list[tuple[int, int]] = []
    start = last = None
    for i in range(n):
        if a[i] != b[i]:
            if start is None:
                start = i
            elif i - last > max_gap:
                spans.append((start, last))
                start = i
            last = i
    if start is not None:
        spans.append((start, last))
    if len(b) > len(a):  # the image was expanded
        spans.append((len(a), len(b) - 1))
    out = [(s, bytes(a[s : e + 1]), bytes(b[s : e + 1])) for s, e in spans]
    if len(b) < len(a):  # the image was truncated: the removed tail, with an empty ``new``
        out.append((len(b), bytes(a[len(b) :]), b""))
    return out


def diff_report(a: bytes, b: bytes, limit: int = 24) -> str:
    ch = diff(a, b)
    total = sum(len(new) for _, _, new in ch)
    head = [f"changes: {len(ch)}, bytes affected: {total}", f"size: {len(a)} -> {len(b)}"]
    for off, old, new in ch[:limit]:
        if not new:
            head.append(f"  {off:06X}  {len(old)} byte(s) removed from the end")
            continue
        head.append(
            f"  {off:06X}  {old[:16].hex(' ')}  ->  {new[:16].hex(' ')}"
            + (f"  (+{len(new) - 16} B)" if len(new) > 16 else "")
        )
    if len(ch) > limit:
        head.append(f"  ... {len(ch) - limit} more")
    return "\n".join(head)


IPS_EOF_OFFSET = 0x454F46  # the bytes "EOF" read as a 24-bit record offset
IPS_MAX_RECORD = 0xFFFF
IPS_RLE_MIN = 16  # an RLE record is 8 bytes; a plain one is 5 + the bytes


def make_ips(orig: bytes, patched: bytes) -> bytes:
    """Build an IPS patch. 24-bit offsets: images up to 16 MiB.

    A shrunken image is expressed with the common truncation extension (the
    new length after ``EOF``), which ``apply_ips`` honours. Runs of at least
    ``IPS_RLE_MIN`` equal bytes (the free space of an expanded image) become RLE
    records, so a 2 MiB expansion costs bytes, not a megabyte.
    """
    if max(len(orig), len(patched)) > 0xFFFFFF:
        raise ValueError("IPS cannot address images larger than 16 MiB")
    out = bytearray(b"PATCH")
    for off, _old, new in diff(orig, patched, max_gap=5):
        if not new:  # the removed tail is covered by the truncation trailer
            continue
        out += _ips_records(patched, off, off + len(new))
    out += b"EOF"
    if len(patched) < len(orig):
        out += len(patched).to_bytes(3, "big")
    return bytes(out)


def _run_length(data: bytes, pos: int, end: int) -> int:
    """How many bytes from ``pos`` (before ``end``) equal ``data[pos]``, at most a record."""
    limit = min(end, pos + IPS_MAX_RECORD)
    same = bytes([data[pos]]) * IPS_RLE_MIN
    n = 1
    while pos + n + IPS_RLE_MIN <= limit and data[pos + n : pos + n + IPS_RLE_MIN] == same:
        n += IPS_RLE_MIN  # whole chunks of equal bytes
    while pos + n < limit and data[pos + n] == data[pos]:
        n += 1
    return n


def _ips_records(patched: bytes, pos: int, end: int) -> bytes:
    """IPS records for ``patched[pos:end]``: RLE for long runs, plain records otherwise."""
    out = bytearray()
    plain = pos  # start of the pending plain stretch
    while pos < end:
        run = _run_length(patched, pos, end)
        if run >= IPS_RLE_MIN and pos != IPS_EOF_OFFSET:
            out += _ips_plain(patched, plain, pos)
            out += pos.to_bytes(3, "big") + b"\x00\x00" + run.to_bytes(2, "big")
            out += patched[pos : pos + 1]
            pos = plain = pos + run
        else:
            pos += run
    out += _ips_plain(patched, plain, end)
    return bytes(out)


def _ips_plain(patched: bytes, pos: int, end: int) -> bytes:
    out = bytearray()
    while pos < end:
        if pos == IPS_EOF_OFFSET:
            # A record starting here would read as the end marker. Start it one
            # byte earlier instead and re-send a byte that is already correct.
            pos -= 1
        n = min(IPS_MAX_RECORD, end - pos)
        out += pos.to_bytes(3, "big") + n.to_bytes(2, "big") + patched[pos : pos + n]
        pos += n
    return bytes(out)


def apply_ips(orig: bytes, ips: bytes) -> bytes:
    """Apply an IPS patch (plain and RLE records; the truncation extension is honoured).

    Raises ``ValueError`` on a malformed or truncated patch rather than
    producing a silently incomplete image.
    """
    if ips[:5] != b"PATCH":
        raise ValueError("not an IPS file (missing PATCH header)")
    out = bytearray(orig)
    pos = 5

    def take(n: int) -> bytes:
        nonlocal pos
        if pos + n > len(ips):
            raise ValueError(
                f"truncated IPS patch: record at byte {pos} needs {n} more byte(s), "
                f"file has {len(ips)}"
            )
        chunk = ips[pos : pos + n]
        pos += n
        return chunk

    while True:
        if pos + 3 > len(ips):
            raise ValueError("truncated IPS patch: no EOF marker")
        if ips[pos : pos + 3] == b"EOF":
            pos += 3
            break
        off = int.from_bytes(take(3), "big")
        size = int.from_bytes(take(2), "big")
        if size == 0:  # RLE record
            run = int.from_bytes(take(2), "big")
            payload = take(1) * run
        else:
            payload = take(size)
        end = off + len(payload)
        if end > len(out):
            out.extend(b"\x00" * (end - len(out)))
        out[off:end] = payload
    if pos + 3 <= len(ips):  # optional truncation length
        out = out[: int.from_bytes(ips[pos : pos + 3], "big")]
    return bytes(out)
