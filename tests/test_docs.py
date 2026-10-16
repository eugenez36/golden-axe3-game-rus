"""The documents keep up with the map: counts, lists and hashes they quote.

An audit of every document found some forty statements that had gone stale,
nearly all of them numbers or lists that a change to the map or the assets
should have updated. These tests read the same facts from the project and fail
with the place to fix, the way a stale ``roms.sha1`` fails the build tests.
"""

from __future__ import annotations

import re

from ga3 import text
from ga3.pipeline import open_project

from .conftest import ROOT

README = ROOT / "README.md"
README_RU = ROOT / "README.ru.md"
PATCHES = ROOT / "docs" / "patches.md"
BUILD = ROOT / "docs" / "build.md"
TEXT_FORMAT = ROOT / "docs" / "text_format.md"

# how the READMEs spell a count of text files
WORDS_EN = {9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen"}
WORDS_RU = {
    9: "девяти",
    10: "десяти",
    11: "одиннадцати",
    12: "двенадцати",
    13: "тринадцати",
    14: "четырнадцати",
}


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def _strings_files():
    from ga3.cli import _text_units

    proj = open_project(ROOT)
    return proj, {path for _seg, path, _spans in _text_units(proj)}


def test_readmes_count_the_strings_and_their_files():
    _proj, paths = _strings_files()
    strings = sum(len(text.parse_strings_file(str(p))) for p in paths)
    files = len(paths)
    assert files in WORDS_EN, f"add {files} to WORDS_EN / WORDS_RU in {__file__}"
    en = f"{strings} strings in {WORDS_EN[files]} text"
    ru = f"{strings} строк"
    assert en in " ".join(_read(README).split()), f"README.md should say «{en} files»"
    flat_ru = " ".join(_read(README_RU).split())
    assert ru in flat_ru and f"в {WORDS_RU[files]} текстовых" in flat_ru, (
        f"README.ru.md should say «{strings} строк… в {WORDS_RU[files]} текстовых файлах»"
    )


def test_text_format_lists_every_strings_file():
    _proj, paths = _strings_files()
    listed = set(re.findall(r"^\|[^|]*\| `([\w.]+\.txt)` +\|", _read(TEXT_FORMAT), re.M))
    have = {p.name for p in paths}
    assert listed == have, (
        f"docs/text_format.md strings-file table: missing {sorted(have - listed)}, "
        f"stale {sorted(listed - have)}"
    )


def test_patches_doc_lists_every_patch():
    proj = open_project(ROOT)
    names = {s.get("patch") or s.get("routine") for s in proj.map.by_type("patch")}
    overview = _read(PATCHES).split("\n## ", 1)[0]  # the table before the first section
    listed = set(re.findall(r"^\| `(\w+)` +\|", overview, re.M))
    assert names <= listed, f"docs/patches.md table lacks {sorted(names - listed)}"
    assert listed <= names, f"docs/patches.md table lists unknown {sorted(listed - names)}"


def test_build_doc_records_the_current_build_hash():
    sha = next(
        line.split()[0]
        for line in _read(ROOT / "roms.sha1").splitlines()
        if line.endswith("build/ga3.bin")
    )
    table = re.findall(r"^\| [^|]+\| `([0-9a-f]{8})…`", _read(BUILD), re.M)
    assert table and table[-1] == sha[:8], (
        f"docs/build.md «Byte identity» table should end with the build in roms.sha1 "
        f"(`{sha[:8]}…`), not `{table[-1] if table else None}…`"
    )


def test_readmes_quote_the_free_space_after_the_patches():
    proj = open_project(ROOT)
    free = [s for s in proj.map.by_type("free") if s.end == proj.map.rom.get("build_size")]
    assert len(free) == 1, "expected one free segment up to rom.build_size"
    span = f"{free[0].start:06X}–{free[0].end - 1:06X}"
    for path in (README, README_RU):
        assert f"`{span}`" in _read(path), f"{path.name} should give the free space as `{span}`"
