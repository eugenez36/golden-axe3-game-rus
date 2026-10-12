"""The pre-commit hook that aligns Markdown tables (.github/scripts/align-md-tables.py)."""

from __future__ import annotations

import importlib.util

from .conftest import ROOT

SCRIPT = ROOT / ".github" / "scripts" / "align-md-tables.py"
_spec = importlib.util.spec_from_file_location("align_md_tables", SCRIPT)
md = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(md)


def test_columns_pad_to_the_widest_cell_counting_characters():
    src = "| Range | Contents |\n|---|---|\n| `000000` | векторы |\n"
    assert md.align(src) == (
        "| Range    | Contents |\n|----------|----------|\n| `000000` | векторы  |\n"
    )


def test_escaped_pipes_alignment_colons_and_short_rows():
    src = "| Cmd | Meaning |\n|:--|--:|\n| `state save\\|load` | x |\n| `reset` |\n"
    assert md.align(src).splitlines() == [
        "| Cmd                | Meaning |",
        "|:-------------------|--------:|",
        "| `state save\\|load` | x       |",
        "| `reset`            |         |",
    ]


def test_code_fences_and_non_tables_are_left_alone():
    src = "```text\n| a | b |\n|---|---|\n```\n| just a line |\ntext | with | pipes\n"
    assert md.align(src) == src


def test_aligning_is_idempotent():
    once = md.align("| a | bb |\n|---|---|\n| ccc | d |\n")
    assert md.align(once) == once


def test_check_mode_reports_without_writing(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text("| a | bb |\n|---|---|\n", encoding="utf-8")
    assert md.main(["--check", str(doc)]) == 1
    assert doc.read_text(encoding="utf-8") == "| a | bb |\n|---|---|\n"
    assert md.main([str(doc)]) == 1
    assert md.main(["--check", str(doc)]) == 0
    assert "unaligned tables" in capsys.readouterr().out
