import pytest

from ga3 import table, text


def test_every_byte_roundtrips_losslessly():
    for b in table.BYTE_TO_CHAR:
        s = table.decode_lossless(bytes([b]))
        assert table.encode(s) == bytes([b]), f"byte {b:02X} -> {s!r}"


def test_digits_share_glyphs():
    assert table.encode("0") == b"\x30"
    assert table.encode("3") == b"\x33"
    assert table.encode("О") == b"\x30"
    assert table.encode("З") == b"\x33"


def test_escape_bytes():
    assert table.encode("{FF}{00}") == b"\xff\x00"
    assert table.decode(b"\xff") == "{FF}"


def test_unknown_char_raises():
    with pytest.raises(ValueError):
        table.encode("ß")


def test_case_fallback():
    # «ю» and «Ю» are two glyphs (0x29 low, 0x50 tall); letters with one case only
    # fall back to it
    assert table.encode("ю") == b"\x29"
    assert table.encode("Ю") == b"\x50"
    assert table.encode("й") == table.encode("Й") == b"\x71"


def test_tbl_format_has_every_byte():
    tbl = table.format_tbl()
    for b in table.BYTE_TO_CHAR:
        assert f"{b:02X}={table.BYTE_TO_CHAR[b]}" in tbl
    assert "*FF" in tbl and "/FE" in tbl


def test_find_strings_and_file_roundtrip(tmp_path):
    body = table.encode("ИГРОК") + b"\xff" + table.encode("ВДВОЕМ") + b"\xfe" + b"\x01\x02"
    data = b"\x00" * 16 + body + b"\x00" * 16
    rows = text.find_strings(data, 0, len(data), min_len=4)
    assert [(o, ln) for o, ln, _ in rows] == [(16, 5), (22, 6)]
    assert rows[0][2] == "ИГРОК"
    f = tmp_path / "s.txt"
    f.write_text(text.format_strings_file(rows, "t", 0, len(data)), encoding="utf-8")
    assert text.parse_strings_file(str(f)) == rows


def test_check_rejects_overflow_and_out_of_range():
    rows = [(16, 5, "ИГРОКИ"), (200, 4, "ИГРА")]
    problems = text.check(rows, 0, 100)
    assert len(problems) == 2
    assert "longer" in problems[0]
    assert "outside" in problems[1]


def test_insert_pads_with_spaces():
    data = bytearray(b"\x00" * 8 + table.encode("ИГРОК") + b"\x00" * 8)
    changed = text.insert_strings(data, [(8, 5, "ИГР")], 0, len(data))
    assert changed == 1
    assert bytes(data[8:13]) == table.encode("ИГР") + b"\x20\x20"
    with pytest.raises(ValueError):
        text.insert_strings(data, [(8, 5, "ГЕРОЙ!")], 0, len(data))


def test_bad_escape_is_reported_with_position():
    for bad in ("{zz}", "{1}", "ИГ{0", "{"):
        with pytest.raises(ValueError, match="bad escape"):
            table.encode(bad)


def test_tbl_lists_every_byte_exactly_once():
    active = [
        ln.split("=", 1)[0]
        for ln in table.format_tbl().splitlines()
        if ln and not ln.startswith(("#", "*", "/"))
    ]
    assert len(active) == len(set(active)) == len(table.BYTE_TO_CHAR)
    assert "# 30=0" in table.format_tbl()  # the alias survives, as a comment


def test_case_fallback_accepts_byte_zero(monkeypatch):
    # a hypothetical glyph at byte 0 must not be mistaken for "not found"
    monkeypatch.setitem(table.CHAR_TO_BYTE, "Ω", 0)
    assert table.encode("ω") == b"\x00"


def test_count_changed_counts_unencodable_and_shortened_rows():
    data = b"\x00" * 8 + table.encode("ИГРОК")
    assert text.count_changed([(8, 5, "ИГРОК")], data) == 0
    assert text.count_changed([(8, 5, "ИГР")], data) == 1
    assert text.count_changed([(8, 5, "ИГРОß")], data) == 1
