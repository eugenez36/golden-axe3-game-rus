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
        return sum(struct.unpack(">%dH" % (len(body) // 2), body)) & 0xFFFF

    def stored_checksum(self) -> int:
        return struct.unpack(">H", self.data[HDR_CHECKSUM : HDR_CHECKSUM + 2])[0]

    def fix_checksum(self) -> int:
        cs = self.compute_checksum()
        struct.pack_into(">H", self.data, HDR_CHECKSUM, cs)
        return cs

    def checksum_ok(self) -> bool:
        return self.stored_checksum() == self.compute_checksum()

    def rom_bounds(self) -> tuple[int, int]:
        return struct.unpack(">II", self.data[HDR_ROM_START : HDR_ROM_START + 8])

    def fix_rom_end(self) -> int:
        """ROM end = address of the last byte of the image."""
        end = len(self.data) - 1
        struct.pack_into(">I", self.data, HDR_ROM_END, end)
        return end

    def expand(self, size: int = 0x200000, fill: int = 0xFF) -> None:
        """Grow the image (e.g. to 2 MiB). The header is fixed on save()."""
        if size < len(self.data):
            raise ValueError("expand(): new size is smaller than the current image")
        self.data.extend(bytes([fill]) * (size - len(self.data)))

    # -- scalar access -------------------------------------------------------

    def u8(self, off: int) -> int:
        return self.data[off]

    def u16(self, off: int) -> int:
        return struct.unpack_from(">H", self.data, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from(">I", self.data, off)[0]

    def set_u8(self, off: int, val: int) -> None:
        self.data[off] = val & 0xFF

    def set_u16(self, off: int, val: int) -> None:
        struct.pack_into(">H", self.data, off, val & 0xFFFF)

    def set_u32(self, off: int, val: int) -> None:
        struct.pack_into(">I", self.data, off, val & 0xFFFFFFFF)

    def find_all(self, pattern: bytes, start: int = 0) -> list[int]:
        out, i = [], start
        while True:
            i = self.data.find(pattern, i)
            if i < 0:
                return out
            out.append(i)
            i += 1

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
    return [(s, bytes(a[s : e + 1]), bytes(b[s : e + 1])) for s, e in spans]


def diff_report(a: bytes, b: bytes, limit: int = 24) -> str:
    ch = diff(a, b)
    total = sum(len(new) for _, _, new in ch)
    head = [f"changes: {len(ch)}, bytes affected: {total}", f"size: {len(a)} -> {len(b)}"]
    for off, old, new in ch[:limit]:
        head.append(
            f"  {off:06X}  {old[:16].hex(' ')}  ->  {new[:16].hex(' ')}"
            + (f"  (+{len(new) - 16} B)" if len(new) > 16 else "")
        )
    if len(ch) > limit:
        head.append(f"  ... {len(ch) - limit} more")
    return "\n".join(head)


def make_ips(orig: bytes, patched: bytes) -> bytes:
    """Build an IPS patch. 24-bit offsets: images up to 16 MiB."""
    if len(patched) > 0xFFFFFF:
        raise ValueError("IPS cannot address images larger than 16 MiB")
    out = bytearray(b"PATCH")
    for off, _old, new in diff(orig, patched, max_gap=5):
        # An offset of 0x454F46 would read as the "EOF" marker: start one byte earlier.
        if off == 0x454F46 and off > 0:
            off -= 1
            new = patched[off : off + len(new) + 1]
        i = 0
        while i < len(new):
            chunk = new[i : i + 0xFFFF]
            out += (off + i).to_bytes(3, "big") + len(chunk).to_bytes(2, "big") + chunk
            i += len(chunk)
    out += b"EOF"
    return bytes(out)


def apply_ips(orig: bytes, ips: bytes) -> bytes:
    """Apply an IPS patch (plain and RLE records; the truncation extension is honoured)."""
    if ips[:5] != b"PATCH":
        raise ValueError("not an IPS file (missing PATCH header)")
    out = bytearray(orig)
    pos = 5
    while True:
        if ips[pos : pos + 3] == b"EOF":
            pos += 3
            break
        off = int.from_bytes(ips[pos : pos + 3], "big")
        size = int.from_bytes(ips[pos + 3 : pos + 5], "big")
        pos += 5
        if size == 0:  # RLE record
            run = int.from_bytes(ips[pos : pos + 2], "big")
            value = ips[pos + 2]
            pos += 3
            payload = bytes([value]) * run
        else:
            payload = ips[pos : pos + size]
            pos += size
        end = off + len(payload)
        if end > len(out):
            out.extend(b"\x00" * (end - len(out)))
        out[off:end] = payload
    if pos + 3 <= len(ips):  # optional truncation length
        out = out[: int.from_bytes(ips[pos : pos + 3], "big")]
    return bytes(out)


def write_ips(orig_path: str, patched_path: str, out_path: str) -> str:
    with open(orig_path, "rb") as f:
        a = f.read()
    with open(patched_path, "rb") as f:
        b = f.read()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(make_ips(a, b))
    return out_path
