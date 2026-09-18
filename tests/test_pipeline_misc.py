"""Small pipeline / palette / tiles helpers that need neither the ROM nor a project."""

from __future__ import annotations

import pytest

from ga3 import palette, rom_map, tiles
from ga3 import pipeline as pl


def test_read_sha_file_accepts_binary_marker_and_tabs(tmp_path):
    f = tmp_path / "roms.sha1"
    f.write_text("# comment\n\naaaa  baserom/ga3.bin\nbbbb *build/ga3.bin\ncccc\tbuild/other.bin\n")
    assert pl.read_sha_file(f) == {
        "baserom/ga3.bin": "aaaa",
        "build/ga3.bin": "bbbb",
        "build/other.bin": "cccc",
    }
    f.write_text("just-a-digest\n")
    with pytest.raises(pl.PipelineError, match="expected"):
        pl.read_sha_file(f)
    assert pl.read_sha_file(tmp_path / "absent") == {}


def test_find_root_walks_up_and_validates_ga3_root(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "assets" / "deep").mkdir(parents=True)
    (root / pl.MAP_FILE).write_text("rom: {size: 0x10}\nsegments: []\n")
    monkeypatch.delenv("GA3_ROOT", raising=False)
    assert pl.find_root(root / "assets" / "deep") == root.resolve()
    monkeypatch.chdir(root / "assets")
    assert pl.find_root() == root.resolve()
    with pytest.raises(pl.PipelineError, match="not found"):
        pl.find_root(tmp_path)
    monkeypatch.setenv("GA3_ROOT", str(tmp_path))
    with pytest.raises(pl.PipelineError, match="GA3_ROOT"):
        pl.find_root()
    assert pl.find_root(root) == root.resolve()  # an explicit start ignores GA3_ROOT
    monkeypatch.setenv("GA3_ROOT", str(root))
    monkeypatch.chdir(tmp_path)
    assert pl.open_project().root == root.resolve()


def test_by_name_unknown_is_a_rommaperror():
    rm = rom_map.parse({"rom": {"size": 0x10}, "segments": []}, "t.yml")
    with pytest.raises(rom_map.RomMapError, match="no segment named 'x' in t.yml"):
        rm.by_name("x")


def test_resolve_ref_prefers_pal_file_over_hex_lookalike(tmp_path):
    words = b"".join(((i << 1) | (i << 5) | (i << 9)).to_bytes(2, "big") for i in range(8)) * 2
    (tmp_path / "cafe.pal").write_text(palette.format_pal(words), encoding="utf-8")
    from_file = palette.resolve_ref("cafe", tmp_path, data=bytes(0x10000))
    assert from_file == palette.parse_pal(palette.format_pal(words))[0]
    assert palette.resolve_ref("cafe/0", tmp_path) == from_file
    with pytest.raises(ValueError, match="out of range"):
        palette.resolve_ref("cafe/3", tmp_path)
    image = bytes(0x100) + words + bytes(0x100)
    assert palette.resolve_ref("0x100", None, image) == from_file
    assert palette.resolve_ref("$100", None, image) == from_file
    assert palette.resolve_ref("100", tmp_path, image) == from_file  # no 100.pal -> offset
    assert palette.resolve_ref(None, tmp_path) is None
    assert palette.resolve_ref("gray", tmp_path) is None
    with pytest.raises(ValueError, match="an image is needed"):
        palette.resolve_ref("0x100", tmp_path)
    with pytest.raises(ValueError, match="past the end"):
        palette.resolve_ref("0x100", None, bytes(0x110))
    with pytest.raises(ValueError, match="no title.pal"):
        palette.resolve_ref("title", tmp_path, image)
    assert palette.resolve_ref("title", tmp_path, image, missing_ok=True) is None
    assert palette.resolve_ref("0x100", tmp_path, missing_ok=True) is None


def test_import_indexed_short_png_raises_valueerror(tmp_path):
    pytest.importorskip("PIL")
    raw = bytes(range(256)) * 4  # 32 tiles
    img = tiles.render_indexed(raw, 0, 32, cols=8)
    p = tmp_path / "t.png"
    img.save(p)
    assert tiles.import_indexed(str(p), count=32) == raw
    with pytest.raises(ValueError, match="holds 32 tiles, 40 requested"):
        tiles.import_indexed(str(p), count=40)


def test_dump_tiles_creates_the_directory(tmp_path):
    pytest.importorskip("PIL")
    out = tmp_path / "a" / "b" / "t.png"
    tiles.dump_tiles(bytes(64), 0, 2, str(out), cols=2, scale=1)
    assert out.exists()
