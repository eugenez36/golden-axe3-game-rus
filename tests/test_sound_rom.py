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


def test_song_constants_are_play_commands(project, baserom):
    """Every ``*_song`` constant is a stage event [.. .. 00 ID][00 00 00 03] (command 3 hands
    the ID to SOUND, 00C2F0) or ``moveq #ID,d0`` right before ``jsr``/``bra`` SOUND (00E4B2)."""
    songs = {n: c for n, c in project.map.constants.items() if "song" in n}
    assert len(songs) == 21
    for name, c in songs.items():
        assert c.get("range") == [0x81, 0x9B] and c.get("hex"), name
        for s in c.sites:
            if s.offset == 3:  # a stage event
                assert baserom.data[s.at + 2] == 0 and baserom.u32(s.at + 4) == 3, name
                assert 0x0EC300 <= s.at < 0x0F0000, name
            else:  # moveq #ID,d0 then jsr $e4b2(pc) / bra.w $e4b2
                assert (baserom.data[s.at], s.offset) == (0x70, 1), name
                op, disp = baserom.u16(s.at + 2), baserom.u16(s.at + 4)
                assert op in (0x4EBA, 0x6000), name
                assert (s.at + 4 + disp) & 0xFFFF == 0xE4B2, name


def _sections(rom, base, index):
    """Section pointers ($C77A) of the list at ``base`` for $C778 = ``index``: 18 word offsets
    (special_12, the 19th, would read the first pointer's high word), then a long per section."""
    offsets = [rom.u16(base + 2 * i) for i in range(18)]
    first = offsets[index]
    later = [o for o in offsets if o > first]
    count = (min(later) - first) // 4 if later else 1
    return [rom.u32(base + first + 4 * k) for k in range(count)]


def _sound_events(rom, names):
    """Every stage event whose command (low 6 bits of its second long) is 3, play sound:
    {entry address: {list names that reach it}}. Object lists hold 8-byte entries up to FFFF;
    a script section is a word table of scripts, a script is words (wave offsets from it,
    FFFC-FFFF end it), a wave is a word (delay, count) and ``count`` entries (00C0A4)."""

    def read_base(lea):  # lea $xxxxxx.l,a4
        assert rom.u16(lea) == 0x49F9
        return rom.u32(lea + 2)

    objects, scripts = read_base(0x00C15A), read_base(0x00BDF2)
    found = {}

    def add(entry, name):
        if rom.u32(entry + 4) & 0x3F == 3:
            found.setdefault(entry, set()).add(name)

    for index, name in enumerate(names[:18]):
        for p in _sections(rom, objects, index):
            while rom.u16(p) != 0xFFFF:
                add(p, name)
                p += 8
        for p in _sections(rom, scripts, index):
            for j in range(rom.u16(p) // 2):
                script = p + rom.u16(p + 2 * j)
                for k in range(64):
                    x = rom.u16(script + 2 * k)
                    if x == 0 or x >= 0xFFFC:
                        break
                    wave = script + x
                    for e in range(rom.u16(wave) & 0xFF):
                        add(wave + 2 + 8 * e, name)
    return found


def test_boss_songs_sit_in_their_stages_lists(project, baserom):
    """``boss_song_X`` names every song event of stage X and nothing else: walked exactly as
    the game reads the lists, not found by byte pattern (which once put stage 7's name on a
    scene's entry)."""
    names = project.map.by_name("stage_music").get("fields")
    found = _sound_events(baserom, names)
    in_stages = {
        a
        for a, where in found.items()
        if 0x81 <= baserom.data[a + 3] <= 0x9B and any(n.startswith("stage_") for n in where)
    }
    sites = set()
    for name, c in project.map.constants.items():
        if name.startswith("boss_song_"):
            stage = "stage_" + name.removeprefix("boss_song_")
            for s in c.sites:
                assert stage in found.get(s.at, ()), (name, hex(s.at))
                sites.add(s.at)
    assert sites == in_stages
    # left out on purpose: the castle scene's entry (never heard) and a sound effect
    rest = {a: (baserom.data[a + 3], sorted(found[a])) for a in found.keys() - in_stages}
    assert rest == {0x0EE7FE: (0x94, ["special_11"]), 0x0EEA12: (0x04, ["stage_5a"])}
