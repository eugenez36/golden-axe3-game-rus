"""``ga3 text lint`` / ``preview`` and strings embedded in code. No ROM needed."""

from __future__ import annotations

import pytest
import yaml

from ga3 import pipeline as pl
from ga3 import table, text
from ga3.assets import BuildError, Paths, handler_for
from ga3.cli import main
from ga3.rom import Rom
from ga3.rom_map import Segment

from .conftest import ROOT, Synth

# ---------------------------------------------------------------- rules


@pytest.mark.parametrize(
    "txt, rule",
    [
        (" Эя все еще жив!", "e-for-quote"),  # 0x22 typed as a quotation mark
        ("в округе.Э", "e-for-quote"),
        ("ВперЁд, воин!", "capital-inside-word"),
        ("мир  не вечен.", "double-space"),
        ("Привет , воин", "space-before-punctuation"),
        ("конец.Начало", "no-space-after-punctuation"),
    ],
)
def test_each_rule_catches_its_case(txt, rule):
    assert rule in [r for r, _excerpt in text.lint_text(txt)]


@pytest.mark.parametrize(
    "txt",
    [
        " 'Теперь, когда с тебя",  # a reply opens with a space and '
        "Топор.",
        "осторожен - здесь полно",  # spaced hyphen stands in for a dash
        "Хм... Ты уже здесь.",
        "Е. Новиков",  # initials
        "С.В.",
        "опаснее.          ",  # trailing padding is not a double space
        "ОЧКИ ",
        "Это правда",  # «Э» starting a word is a letter
        "Победил ИГРОК 1.",
    ],
)
def test_clean_text_has_no_findings(txt):
    assert text.lint_text(txt) == []


def test_lint_reports_offsets_and_honours_allow():
    rows = [(0x100, 12, "ВперЁд!"), (0x110, 8, "мир  да")]
    assert text.lint(rows) == [
        "000100 capital-inside-word: «ВперЁд!»",
        "000110 double-space: «мир  да»",
    ]
    assert text.lint(rows, {0x100: ["capital-inside-word"]}) == ["000110 double-space: «мир  да»"]


def test_records_at_and_in_spans():
    data = bytes(8) + table.encode("ПАУЗА") + bytes(3)
    assert text.records_at(data, [(8, 5)]) == [(8, 5, "ПАУЗА")]
    assert text.in_spans(8, 5, [(8, 13)])
    assert not text.in_spans(8, 6, [(8, 13)])


# ---------------------------------------------------------------- strings embedded in code

WORD = table.encode("ПАУЗА")


def _code_segment(**over) -> Segment:
    attrs = {"strings": [[0x108, 5]], "strings_path": "text/code.txt"} | over
    return Segment("code_x", 0x100, 0x120, "code", "code/code_x.m68k", attrs)


def _image() -> Rom:
    data = bytearray(range(0x80, 0xA0)) * 0x10  # no text bytes outside the string
    data[0x108:0x10D] = WORD
    return Rom(bytes(data[:0x200]))


def _paths(tmp_path) -> Paths:
    return Paths(tmp_path, tmp_path / "assets", tmp_path / "build")


def test_embedded_strings_extract_build_roundtrip(tmp_path):
    seg, rom, paths = _code_segment(), _image(), _paths(tmp_path)
    h = handler_for(seg)
    assert h.check(rom, seg) == []
    files = h.extract(rom, seg, paths)
    strings = paths.asset("text/code.txt")
    assert strings in files
    assert text.parse_strings_file(str(strings)) == [(0x108, 5, "ПАУЗА")]
    assert h.sources(seg, paths) == [strings]

    body = strings.read_text(encoding="utf-8").replace("ПАУЗА", "СТОП")
    strings.write_text(body, encoding="utf-8")
    out = _image()
    assert "1 string(s) changed" in h.build(out, seg, paths)
    assert bytes(out.data[0x108:0x10D]) == table.encode("СТОП ")
    assert bytes(out.data[0x100:0x108]) == bytes(rom.data[0x100:0x108])  # code untouched


def test_embedded_strings_refuse_undeclared_records(tmp_path):
    seg, rom, paths = _code_segment(), _image(), _paths(tmp_path)
    h = handler_for(seg)
    h.extract(rom, seg, paths)
    strings = paths.asset("text/code.txt")
    strings.write_text(strings.read_text(encoding="utf-8") + "000110:4 | ДА  \n", encoding="utf-8")
    with pytest.raises(BuildError, match="does not declare: 000110:4"):
        h.build(_image(), seg, paths)


@pytest.mark.parametrize(
    "over, match",
    [
        ({"strings": []}, "non-empty list"),
        ({"strings": [[0x108]]}, "bad strings entry"),
        ({"strings": [[0x11E, 5]]}, "outside the segment"),
        ({"strings": [[0x108, 5], [0x10A, 2]]}, "overlap"),
    ],
)
def test_embedded_strings_reject_bad_declarations(tmp_path, over, match):
    seg = _code_segment(**over)
    with pytest.raises(BuildError, match=match):
        handler_for(seg).extract(_image(), seg, _paths(tmp_path))


def test_embedded_strings_check_and_missing_file(tmp_path):
    seg, rom = _code_segment(strings=[[0x100, 4]]), _image()
    assert "no glyph" in handler_for(seg).check(rom, seg)[0]
    seg = _code_segment(strings_path=None)
    with pytest.raises(BuildError, match="strings_path"):
        handler_for(seg).sources(seg, _paths(tmp_path))
    seg = _code_segment()
    with pytest.raises(BuildError, match="missing text file"):
        handler_for(seg).build(_image(), seg, _paths(tmp_path))


# ---------------------------------------------------------------- CLI


def _with_prose(s: Synth, spans) -> None:
    path = s.root / pl.MAP_FILE
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for seg in doc["segments"]:
        if seg["name"] == "text_demo":
            seg["prose"] = spans
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def run(s: Synth, *argv: str) -> int:
    return main(["--root", str(s.root), *argv])


def test_cli_lint_and_preview(synthetic_extracted, capsys):
    s = synthetic_extracted
    assert run(s, "text", "lint") == 0  # no prose declared: nothing to check
    assert "text_demo" not in capsys.readouterr().out

    _with_prose(s, [[0x220, 0x260]])
    assert run(s, "text", "lint") == 0
    assert "3 prose strings, 0 finding(s)" in capsys.readouterr().out

    demo = s.asset("text/demo.txt")
    demo.write_text(demo.read_text(encoding="utf-8").replace("ОПЦИИ", "ОпЦИ"), encoding="utf-8")
    assert run(s, "text", "lint") == 1
    out = capsys.readouterr().out
    assert "capital-inside-word" in out and "rule capital-inside-word:" in out

    pytest.importorskip("PIL.Image")
    out_dir = s.root / "build" / "preview"
    assert run(s, "text", "preview", "-o", str(out_dir), "--scale", "1") == 0
    png = out_dir / "text_demo.png"
    from PIL import Image

    with Image.open(png) as im:
        assert im.size == (6 * 8, 3 * 8)  # widest record x 3 records, 8x8 glyphs
    assert run(s, "text", "preview", "-o", str(out_dir / "c"), "--changed") == 0
    assert "(1 strings)" in capsys.readouterr().out.splitlines()[-1]


def test_committed_game_text_is_lint_clean():
    """The real strings files pass ``ga3 text lint`` (deliberate findings: ``lint_allow``)."""
    assert main(["--root", str(ROOT), "text", "lint"]) == 0
