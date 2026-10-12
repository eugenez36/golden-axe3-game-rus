import pytest

from ga3 import font, nemesis, rom_map, table
from ga3.cli import main

from .conftest import ROOT


def test_real_map_loads_and_covers_the_image():
    rm = rom_map.load(ROOT / "rom_map.yml")
    assert sum(rm.coverage().values()) == rm.size == 0x100000
    names = {s.name for s in rm.segments}
    for expected in ("vectors", "header", "hp_table", "font", "text_dialogue", "art_main", "pcm"):
        assert expected in names
    nem = rm.by_type("nemesis")
    assert len(nem) == 14
    assert rm.by_name("font").get("format") == "font_art"
    assert rm.by_name("font").size == 840


def test_map_rejects_overlap_and_bare_ints():
    doc = {
        "rom": {"size": 0x100},
        "segments": [
            {"name": "a", "start": 0x0, "end": 0x20, "type": "code"},
            {"name": "b", "start": 0x10, "end": 0x30, "type": "code"},
        ],
    }
    with pytest.raises(rom_map.RomMapError, match="overlap"):
        rom_map.parse(doc)
    doc["segments"][1]["start"] = "0x20"
    with pytest.raises(rom_map.RomMapError, match="0x-prefixed"):
        rom_map.parse(doc)


def test_map_fills_gaps():
    doc = {
        "rom": {"size": 0x100},
        "segments": [{"name": "a", "start": 0x10, "end": 0x20, "type": "code"}],
    }
    rm = rom_map.parse(doc)
    assert [s.name for s in rm.segments] == ["unk_000000", "a", "unk_000020"]
    assert rm.coverage() == {"unknown": 0xF0, "code": 0x10}


@pytest.mark.parametrize(
    "text, cell",
    [
        ("draws 'V <package version>'", r"draws 'V \<package version>'"),  # not an HTML tag
        ("C8A0 + n*0100 with attr", r"C8A0 + n\*0100 with attr"),  # no emphasis
        ("a | b", r"a \| b"),  # the cell does not split
        ("`f * len` and *x*", r"`f * len` and \*x\*"),  # code spans stay as they are
        ("`a|b`", r"`a\|b`"),  # GFM splits cells on | even inside code spans
    ],
)
def test_markdown_cells_escape_what_markdown_would_eat(text, cell):
    assert rom_map._md_text(text) == cell


def test_font_art_identity():
    glyph = b"\xcc" * 32  # blank glyph: all background
    art = font.tile_to_art(glyph, 0)
    assert art == ["........"] * 8
    assert font.art_to_tile(art) == glyph
    ink_row = "#" * 8
    assert font.art_to_tile([ink_row] * 8) == b"\x66" * 32
    with pytest.raises(ValueError):
        font.art_to_tile(["........"] * 7)


def test_font_art_file_roundtrip(fixtures):
    raw = (fixtures / "font_vram.4bpp").read_bytes()
    art = font.font_to_art(raw)
    glyphs = font.parse_art(art)
    assert font.art_to_font(glyphs, 96) == raw
    assert font.free_slots(raw) == [0x3E, 0x7B, 0x7F]  # 0x3C is now ё, 0x40 V


def test_committed_font_nem_matches_vram_dump(fixtures):
    """The committed block must decode to the glyphs the game actually uploads."""
    nem = (ROOT / "assets/gfx/nemesis/font.nem").read_bytes()
    vram = (fixtures / "font_vram.4bpp").read_bytes()
    decoded = nemesis.decompress_blob(nem)
    # the VRAM dump predates the six new glyphs; every other tile is identical
    art_rom = font.parse_art(font.font_to_art(decoded))
    art_vram = font.parse_art(font.font_to_art(vram))
    differing = sorted(b for b in art_rom if art_rom[b] != art_vram[b])
    assert all(b in (0x2A, 0x2B, 0x3C, 0x40, 0x4F, 0x51) for b in differing), differing


def test_cli_help_and_map(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert main(["--root", str(ROOT), "map"]) == 0
    out = capsys.readouterr().out
    assert "tiles4bpp" in out and "unknown" in out


# small letters whose mark rises above the x-height: the row their drawing starts on
_TALL_LOWER = {"й": 1, "ё": 0}  # the breve sits on row 1, the dots on row 0


def test_letter_case_matches_glyph_height():
    """A label's case must match its drawing: capitals start on row 0, small letters lower.

    Guards against swapped labels such as the old ю (0x50) / Ю (0x29) mix-up,
    which made correct in-game text read wrong in assets/text.
    """
    glyphs = font.parse_art_file(str(ROOT / "assets/gfx/font/font.txt"))
    wrong = []
    for byte, ch in sorted(table.BYTE_TO_CHAR.items()):
        if not ch.isalpha():
            continue
        art = font.tile_to_art(glyphs[byte], 0)
        top = next(i for i, row in enumerate(art) if row.strip("."))
        if ch in _TALL_LOWER:
            if top != _TALL_LOWER[ch]:
                wrong.append(f"{byte:02X} {ch!r} starts on row {top}")
            continue
        drawn_upper = top <= 1
        if drawn_upper != ch.isupper():
            wrong.append(f"{byte:02X} {ch!r} starts on row {top}")
    assert wrong == []
