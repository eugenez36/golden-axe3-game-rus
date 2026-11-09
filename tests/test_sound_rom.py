"""ROM-gated: the sound bank 0F0000-0FFA10 (issue #53) holds together as the map says."""

import pytest

pytestmark = pytest.mark.rom


def _long(data, off: int) -> int:
    return int.from_bytes(bytes(data[off : off + 4]), "big")


def _seg(project, name: str):
    return project.map.by_name(name)


def test_driver_header_points_into_its_segments(project, baserom):
    d = baserom.data
    head = _seg(project, "snd_tables").start
    assert _long(d, head + 0x08) == _seg(project, "snd_music_index").start
    assert _long(d, head + 0x00) == _seg(project, "snd_priority").start
    assert _long(d, head + 0x1C) == _seg(project, "snd_driver").start
    assert _long(d, head + 0x0C) == _seg(project, "snd_sfx").start
    z80 = _seg(project, "z80_driver")
    assert (_long(d, head + 0x20), _long(d, head + 0x24)) == (z80.start, z80.end)
    loader = _long(d, head + 0x28)
    assert _seg(project, "snd_driver").start <= loader < _seg(project, "snd_driver").end


def test_every_song_lies_in_snd_music(project, baserom):
    index, music = _seg(project, "snd_music_index"), _seg(project, "snd_music")
    songs = [_long(baserom.data, a) for a in range(index.start, index.end, 4)]
    assert len(songs) == 27  # IDs 81-9B
    assert all(music.start <= s < music.end for s in songs)
    assert min(songs) == music.start  # song 82 starts right after the driver code


def test_dac_table_covers_the_samples(project, baserom):
    d = baserom.data
    table, pcm = _seg(project, "dac_table"), _seg(project, "pcm")
    assert (table.end - table.start) % 5 == 0
    first, last = pcm.end, pcm.start
    for e in range(table.start, table.end, 5):
        length = d[e] | d[e + 1] << 8
        start = e + (d[e + 3] | d[e + 4] << 8)
        assert pcm.start <= start and start + length <= pcm.end
        first, last = min(first, start), max(last, start + length)
    assert first == pcm.start
    assert last == pcm.end - 1  # one byte of word padding
