"""ROM-gated: the sound bank 0F0000-0FFA10 (issue #53) holds together as the map says."""

import pytest

pytestmark = pytest.mark.rom


def test_driver_header_points_into_its_segments(project, baserom):
    seg = project.map.by_name
    head = seg("snd_tables").start
    assert baserom.u32(head + 0x00) == seg("snd_priority").start
    assert baserom.u32(head + 0x08) == seg("snd_music_index").start
    assert baserom.u32(head + 0x0C) == seg("snd_sfx").start
    special = baserom.u32(head + 0x04)  # special SFX index, 5 longs inside snd_sfx
    assert seg("snd_sfx").start < special and special + 5 * 4 <= seg("snd_sfx").end
    envelopes = baserom.u32(head + 0x14)  # PSG envelope index, inside snd_tables
    assert head < envelopes < seg("snd_tables").end
    z80 = seg("z80_driver")
    assert (baserom.u32(head + 0x20), baserom.u32(head + 0x24)) == (z80.start, z80.end)
    driver = seg("snd_driver")
    for entry in (baserom.u32(head + 0x1C), baserom.u32(head + 0x28)):  # update, Z80 loader
        assert driver.start <= entry < driver.end


def test_driver_starts_with_its_jmp_vectors(project, baserom):
    """The priority table stops where two jmp (pc) vectors of the driver begin."""
    start = project.map.by_name("snd_driver").start
    update = baserom.u32(project.map.by_name("snd_tables").start + 0x1C)
    assert baserom.u16(start) == baserom.u16(start + 4) == 0x4EFA
    assert start + 2 + baserom.u16(start + 2) == update


def test_every_song_lies_in_snd_music(project, baserom):
    index, music = project.map.by_name("snd_music_index"), project.map.by_name("snd_music")
    songs = [baserom.u32(a) for a in range(index.start, index.end, 4)]
    assert len(songs) == 27  # IDs 81-9B
    assert all(music.start <= s < music.end for s in songs)
    assert min(songs) == music.start  # song 82 starts right after the driver code


def test_dac_table_covers_the_samples(project, baserom):
    d = baserom.data
    table, pcm = project.map.by_name("dac_table"), project.map.by_name("pcm")
    assert (table.end - table.start) % 5 == 0
    first, last = pcm.end, pcm.start
    for e in range(table.start, table.end, 5):
        length = d[e] | d[e + 1] << 8
        start = e + (d[e + 3] | d[e + 4] << 8)
        assert pcm.start <= start and start + length <= pcm.end
        first, last = min(first, start), max(last, start + length)
    assert first == pcm.start
    assert last == pcm.end - 1  # one byte of word padding


def test_stage_music_names_real_songs(project, baserom):
    """The map's range for stage_music is exactly the music index's IDs, and the ROM keeps to it."""
    index, table = project.map.by_name("snd_music_index"), project.map.by_name("stage_music")
    first, last = table.get("range")
    assert (first, last) == (0x81, 0x81 + (index.end - index.start) // 4 - 1)
    assert all(first <= b <= last for b in baserom.data[table.start : table.end])
