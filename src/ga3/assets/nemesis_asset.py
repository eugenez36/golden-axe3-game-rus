"""Nemesis-compressed graphics, including the font (``format: font_art``).

Byte identity rule: our packer is *smaller* than SEGA's on 13 of the 14 blocks
in this ROM, so recompressing unchanged tiles would change the image. The
committed ``.nem`` is therefore written back verbatim whenever it still
decodes to the current tiles; only edited blocks are recompressed. The slot is
padded with 0x00 up to ``seg.end`` (the base ROM word-aligns blocks the same way).

Files:
  ``<path>``            committed compressed block, exact size (``.nem``)
  ``<path>.4bpp``       decoded tiles next to it (gitignored) -- edit these or
                        a PNG rendered from them, then ``ga3 build``
  font: ``path`` is the text-art file (source of truth), ``blob`` the ``.nem``.
"""

from __future__ import annotations

from pathlib import Path

from .. import font as fontmod
from .. import nemesis
from ..rom import Rom
from ..rom_map import Segment
from ..tiles import TILE_SIZE
from .base import BuildError, Handler, Paths, write_bytes, write_text


def _blob_for(raw: bytes, nem_path: Path, xor_attr, seg: Segment) -> tuple[bytes, str]:
    """Reuse the committed .nem if it still matches, else recompress."""
    if nem_path.exists():
        nem = nem_path.read_bytes()
        try:
            if nemesis.decompress(nem + b"\x00\x00", 0) == raw:
                return nem, "verbatim"
        except (ValueError, IndexError, KeyError):
            pass
    xor = None if xor_attr is None else bool(xor_attr)
    blob = nemesis.compress(raw, xor_mode=xor, slack=False)
    if len(blob) > seg.size:
        # last resort: the other XOR mode might be shorter
        alt = nemesis.compress(raw, xor_mode=None, slack=False)
        blob = min(blob, alt, key=len)
    return blob, f"recompressed {len(blob)} B (slot {seg.size}, margin {seg.size - len(blob)})"


class NemesisHandler(Handler):
    committed = True

    def _raw_path(self, seg: Segment, paths: Paths) -> Path:
        return paths.asset(seg.path).with_suffix(".4bpp")

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        size = nemesis.block_size(rom.data, seg.start)
        if size > seg.size:
            raise BuildError(f"{seg}: block is {size} bytes but the segment holds {seg.size}")
        raw = nemesis.decompress(rom.data, seg.start)
        nem_path = write_bytes(paths.asset(seg.path), bytes(rom.data[seg.start : seg.start + size]))
        raw_path = write_bytes(self._raw_path(seg, paths), raw)
        return [nem_path, raw_path]

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        nem_path = paths.asset(seg.path)
        raw_path = self._raw_path(seg, paths)
        if raw_path.exists():
            raw = raw_path.read_bytes()
        elif nem_path.exists():
            raw = nemesis.decompress(nem_path.read_bytes() + b"\x00\x00", 0)
        else:
            raise BuildError(f"{seg}: neither {nem_path.name} nor {raw_path.name} exists")
        tiles = seg.get("tiles")
        if tiles is not None and len(raw) != tiles * TILE_SIZE:
            raise BuildError(f"{seg}: expected {tiles} tiles, got {len(raw) // TILE_SIZE}")
        blob, note = _blob_for(raw, nem_path, seg.get("xor"), seg)
        self.place(rom, seg, blob, pad=0x00)
        return None if note == "verbatim" else note

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        problems = []
        try:
            meta = nemesis.info(rom.data, seg.start)
            size = nemesis.block_size(rom.data, seg.start)
        except Exception as exc:  # noqa: BLE001 - report, do not crash the check
            return [f"{seg}: cannot decode: {exc}"]
        if seg.get("tiles") is not None and meta["tiles"] != seg.get("tiles"):
            problems.append(
                f"{seg}: header says {meta['tiles']} tiles, map says {seg.get('tiles')}"
            )
        if seg.get("xor") is not None and meta["xor"] != bool(seg.get("xor")):
            problems.append(f"{seg}: header XOR={meta['xor']}, map says {seg.get('xor')}")
        if size > seg.size:
            problems.append(f"{seg}: exact block size {size} exceeds segment size {seg.size}")
        pad = rom.data[seg.start + size : seg.end]
        if any(pad):
            problems.append(
                f"{seg}: {len(pad)} byte(s) after the block are not zero padding: {pad.hex()}"
            )
        return problems


class FontArtHandler(NemesisHandler):
    """The font: ``path`` is the text art, ``blob`` the derived ``.nem``."""

    def _params(self, seg: Segment):
        return (
            seg.get("first_byte", fontmod.DEFAULT_FIRST_BYTE),
            seg.get("bg", fontmod.DEFAULT_BG),
            seg.get("ink", fontmod.DEFAULT_INK),
        )

    def _blob_path(self, seg: Segment, paths: Paths) -> Path:
        blob = seg.get("blob")
        if not blob:
            raise BuildError(f"{seg}: font_art segments need a 'blob' path for the .nem")
        return paths.asset(blob)

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        first, bg, ink = self._params(seg)
        size = nemesis.block_size(rom.data, seg.start)
        raw = nemesis.decompress(rom.data, seg.start)
        art = fontmod.font_to_art(raw, first, bg, ink)
        return [
            write_text(paths.asset(seg.path), art),
            write_bytes(self._blob_path(seg, paths), bytes(rom.data[seg.start : seg.start + size])),
        ]

    def raw_from_art(self, seg: Segment, paths: Paths) -> bytes:
        first, bg, ink = self._params(seg)
        art_path = paths.asset(seg.path)
        if not art_path.exists():
            raise BuildError(f"{seg}: missing font art {art_path}")
        glyphs = fontmod.parse_art_file(str(art_path), bg, ink)
        tiles = seg.get("tiles") or (len(glyphs))
        return fontmod.art_to_font(glyphs, tiles, first)

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        raw = self.raw_from_art(seg, paths)
        blob, note = _blob_for(raw, self._blob_path(seg, paths), seg.get("xor"), seg)
        self.place(rom, seg, blob, pad=0x00)
        return None if note == "verbatim" else note

    def refresh_blob(self, seg: Segment, paths: Paths) -> tuple[Path, bool]:
        """Regenerate the committed .nem from the art (``ga3 assets refresh``)."""
        raw = self.raw_from_art(seg, paths)
        blob_path = self._blob_path(seg, paths)
        blob, note = _blob_for(raw, blob_path, seg.get("xor"), seg)
        if note == "verbatim":
            return blob_path, False
        if len(blob) > seg.size:
            raise BuildError(f"{seg}: font needs {len(blob)} bytes, slot holds {seg.size}")
        write_bytes(blob_path, blob)
        return blob_path, True
