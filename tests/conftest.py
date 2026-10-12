"""Shared fixtures.

Two kinds of test image:

* ``baserom`` -- the real ``baserom/ga3.bin``. Tests marked ``rom`` need it with
  the SHA-1 recorded in ``rom_map.yml``; they are skipped, not failed, when it
  is absent so that CI runs green without the copyrighted image.
* ``synthetic_project`` -- an 8 KiB image built here from the committed
  fixtures, with its own ``rom_map.yml`` covering every extractable segment type
  (``patch`` is exercised in ``test_patches.py``). It lets
  the asset handlers, the pipeline and the CLI run end to end without the ROM.
"""

from __future__ import annotations

import hashlib
import shutil
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from ga3 import nemesis, palette, table
from ga3 import pipeline as pl
from ga3.rom import Rom

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def pytest_collection_modifyitems(config, items):
    if _baserom_ok():
        return
    skip = pytest.mark.skip(reason="baserom/ga3.bin missing or wrong sha1")
    for item in items:
        if "rom" in item.keywords:
            item.add_marker(skip)


def _baserom_ok() -> bool:
    p = ROOT / pl.BASEROM_REL
    if not p.exists():
        return False
    proj = pl.open_project(ROOT)
    return hashlib.sha1(p.read_bytes()).hexdigest() == proj.map.rom.get("sha1")


@pytest.fixture(scope="session")
def project() -> pl.Project:
    return pl.open_project(ROOT)


@pytest.fixture(scope="session")
def baserom(project) -> Rom:
    """The pristine base ROM. Never mutate it: copy with ``Rom(bytes(baserom.data))``."""
    return pl.load_baserom(project)


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


# ---------------------------------------------------------------- synthetic project

SYNTH_SIZE = 0x2000
SYNTH_TEXT = ["ИГРОК", "ВДВОЕМ", "ОПЦИИ"]


@dataclass
class Synth:
    """A throw-away project tree: ``rom_map.yml``, ``baserom/ga3.bin``, ``assets/``."""

    root: Path
    project: pl.Project
    image: bytes  # the pristine synthetic image
    rows: list[tuple[int, int, str]]  # text records the ``text_demo`` segment holds

    @property
    def rom(self) -> Rom:
        return Rom(self.image, str(self.root / pl.BASEROM_REL))

    def seg(self, name: str):
        return self.project.map.by_name(name)

    def asset(self, rel: str) -> Path:
        return self.project.paths.asset(rel)


def _header_block() -> bytes:
    hdr = bytearray(b" " * 0x100)

    def put(off: int, s: str) -> None:
        hdr[off - 0x100 : off - 0x100 + len(s)] = s.encode("ascii")

    put(0x100, "SEGA MEGA DRIVE ")
    put(0x110, "(C)GA3  2026.SEP")
    put(0x120, "SYNTHETIC TEST IMAGE".ljust(48))
    put(0x150, "SYNTHETIC TEST IMAGE".ljust(48))
    put(0x180, "GM 00000000-00")
    put(0x190, "J".ljust(16))
    struct.pack_into(">IIII", hdr, 0xA0, 0, 0, 0x00FF0000, 0x00FFFFFF)  # rom_end fixed on save
    put(0x1F0, "JUE".ljust(16))
    return bytes(hdr)


@lru_cache(maxsize=1)
def synthetic_template() -> tuple[bytes, list[dict], dict, str, list[tuple[int, int, str]]]:
    """Image, segment list, ``rom:`` block, ``.pal`` text and expected text rows."""
    tiny_raw = (FIXTURES / "tiny.4bpp").read_bytes()
    tiny_nem = (FIXTURES / "tiny.nem").read_bytes()
    font_raw = (FIXTURES / "font_vram.4bpp").read_bytes()
    font_nem = nemesis.compress(font_raw, xor_mode=False, slack=False)
    assert len(font_nem) <= 840, "font fixture no longer fits the 840-byte slot"

    img = bytearray(SYNTH_SIZE)
    vec = [0xFFFFFFFF] * 64
    vec[0], vec[1] = 0x00FFE000, 0x200
    img[0x000:0x100] = struct.pack(">64I", *vec)
    img[0x100:0x200] = _header_block()
    img[0x200:0x210] = bytes(range(16))
    img[0x210:0x214] = bytes([51, 59, 67, 75])
    img[0x214:0x218] = struct.pack(">HH", 0x1234, 0xBEEF)
    img[0x218:0x220] = b"\xee" * 8  # gap -> synthetic unknown
    body = b"".join(table.encode(s) + b"\xff" for s in SYNTH_TEXT)
    img[0x220 : 0x220 + len(body)] = body
    rows, pos = [], 0x220
    for s in SYNTH_TEXT:
        rows.append((pos, len(table.encode(s)), s))
        pos += len(table.encode(s)) + 1
    img[0x260 : 0x260 + len(tiny_nem)] = tiny_nem  # + 2 bytes of zero padding
    img[0x2CF:0x300] = b"\xff" * (0x300 - 0x2CF)
    img[0x300 : 0x300 + len(font_nem)] = font_nem  # zero padded to 0x648
    img[0x648:0x700] = b"\xee" * (0x700 - 0x648)  # gap
    art = tiny_raw + bytes((i * 37 + 11) & 0xFF for i in range(128))
    img[0x700:0x800] = art
    img[0x800:0x900] = bytes((i * 3) & 0xFF for i in range(0x100))
    img[0x900:0x920] = bytes(range(0x20, 0x40))
    img[0x920:0x2000] = bytes((i * 7 + 1) & 0xFF for i in range(0x2000 - 0x920))

    rom = Rom(img)
    rom.fix_rom_end()
    rom.fix_checksum()
    image = bytes(rom.data)

    def seg(name: str, start: int, end: int, type: str, path: str | None = None, **attrs):
        d = {"name": name, "start": start, "end": end, "type": type}
        if path:
            d["path"] = path
        return d | attrs

    assert 0x260 + len(tiny_nem) + 2 == 0x2CF
    segments = [
        seg("vectors", 0x000, 0x100, "header", "header/vectors.yml"),
        seg("header", 0x100, 0x200, "header", "header/header.yml"),
        seg("boot", 0x200, 0x210, "code", "code/boot.m68k"),
        seg("hp_table", 0x210, 0x214, "table", "data/hp_table.yml", format="u8",
            fields=["slot_0", "slot_1", "slot_2", "slot_3"], max_hud=0x36),
        seg("words", 0x214, 0x218, "table", "data/words.yml", format="u16"),
        # 0x218-0x220: gap -> synthetic unknown
        seg("text_demo", 0x220, 0x260, "text", "text/demo.txt", min_len=4),
        seg("nem_tiny", 0x260, 0x2CF, "nemesis", "gfx/nemesis/tiny.nem", tiles=4,
            xor=nemesis.info(tiny_nem, 0)["xor"]),
        seg("free_02CF", 0x2CF, 0x300, "free", fill=0xFF),
        seg("font", 0x300, 0x648, "nemesis", "gfx/font/font.txt", format="font_art",
            blob="gfx/nemesis/font.nem", tiles=96, xor=False, first_byte=0x20, bg=0x0C, ink=0x06),
        # 0x648-0x700: gap
        seg("art", 0x700, 0x800, "tiles4bpp", "gfx/tiles", prefix="art", sheet_tiles=4, cols=4,
            palette="demo"),
        seg("pcm", 0x800, 0x900, "pcm", "sound/pcm/samples.pcm"),
        seg("blob", 0x900, 0x920, "raw", "raw/blob.raw"),
        seg("tail", 0x920, 0x2000, "data", "code/tail.m68k"),
    ]  # fmt: skip
    rom_info = {
        "title": "Synthetic test image",
        "size": SYNTH_SIZE,
        "sha1": hashlib.sha1(image).hexdigest(),
        "header_checksum": rom.stored_checksum(),
        "entry_point": 0x200,
    }
    words = b"".join(
        struct.pack(">H", (lvl << 9) | (lvl << 5) | (lvl << 1))
        for lvl in ((i % 7) + 1 for i in range(16))
    )
    pal_text = palette.format_pal(words, ["demo: synthetic palette"])
    return image, segments, rom_info, pal_text, rows


def make_synthetic_project(root: Path) -> Synth:
    image, segments, rom_info, pal_text, rows = synthetic_template()
    root.mkdir(parents=True, exist_ok=True)
    doc = {
        "rom": rom_info,
        "palettes": {"demo": {"path": "palettes/demo.pal", "source": "synthetic"}},
        "segments": segments,
    }
    (root / pl.MAP_FILE).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    (root / pl.BASEROM_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / pl.BASEROM_REL).write_bytes(image)
    pal = root / "assets" / "palettes" / "demo.pal"
    pal.parent.mkdir(parents=True, exist_ok=True)
    pal.write_text(pal_text, encoding="utf-8")
    return Synth(root, pl.open_project(root), image, list(rows))


@pytest.fixture
def synthetic_project(tmp_path) -> Synth:
    return make_synthetic_project(tmp_path / "synth")


@pytest.fixture
def synthetic_extracted(synthetic_project) -> Synth:
    """The synthetic project after ``extract``: every asset file is on disk."""
    pl.extract_all(synthetic_project.project, synthetic_project.rom, log=lambda *_: None)
    return synthetic_project


def copy_tree(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst)
    return dst
