"""ROM-gated: the stage palettes 031E16-032934, walked the way the game reads them.

Each test starts from the address the code loads (``lea``), not from the map,
and follows the offsets the way 0112EE, 0112D6, 0112A8 and 0111EA do; the map's
segments must then hold exactly what the walk reaches.
"""

import pytest

pytestmark = pytest.mark.rom


def _lea(rom, at):
    """The absolute address of ``lea $xxxxxx.l,aN`` at ``at``."""
    assert rom.u16(at) & 0xF1FF == 0x41F9, f"no lea.l at {at:06X}"
    return rom.u32(at + 2)


def _offsets(rom, base):
    """Word offsets from ``base``; the table ends where its lowest target starts."""
    offs, at, low = [], base, None
    while low is None or at < low:
        offs.append(rom.u16(at))
        low = min(low or base + offs[-1], base + offs[-1])
        at += 2
    return offs


def _seg(project, name):
    return project.map.by_name(name)


def test_the_code_reads_the_tables_where_the_map_puts_them(project, baserom):
    assert _lea(baserom, 0x0112F2) == _seg(project, "pal_sets").start
    assert _lea(baserom, 0x0112DA) == _seg(project, "pal_stage").start
    assert (
        _lea(baserom, 0x011282)
        == _lea(baserom, 0x011298)
        == _seg(project, "pal_script_index").start
    )
    assert _lea(baserom, 0x0111FE) == _seg(project, "pal_cycles").start


def test_base_sets_point_into_the_palette_segments(project, baserom):
    sets = _seg(project, "pal_sets")
    lines, pool = _seg(project, "pal_lines"), _seg(project, "pal_pool")
    offs = _offsets(baserom, sets.start)
    assert len(offs) == 2
    got = []
    for off in offs:
        block = sets.start + off
        got.append([block + baserom.u16(block + 2 * j) for j in range(4)])
    assert sets.start + offs[-1] + 8 == sets.end
    # set 0: lines 0 and 1 are the words of pal_lines' palettes 1 and 0, lines 2 and 3 in the pool
    assert got[0] == [lines.start + 34 + 2, lines.start + 2, pool.start, pool.start + 11 * 32]
    assert got[1] == [pool.end - 32] * 4  # loaded at 00EEB2: black but colours 0, 6 and 12
    words = [baserom.u16(pool.end - 32 + 2 * k) for k in range(16)]
    assert {k: w for k, w in enumerate(words) if w} == {0: 0x0442, 6: 0x0EEE, 12: 0x0442}


def test_every_stage_line_3_is_a_pool_palette(project, baserom):
    stage, pool = _seg(project, "pal_stage"), _seg(project, "pal_pool")
    offs = _offsets(baserom, stage.start)
    assert len(offs) == 19  # $C778 = 0 .. $12, as stage_music
    subs = sorted({stage.start + o for o in offs})
    ends = subs[1:] + [stage.end]
    used = set()
    for sub, end in zip(subs, ends, strict=True):
        for at in range(sub, end, 2):
            pal = sub + baserom.u16(at)
            assert pool.start <= pal < pool.end and (pal - pool.start) % 32 == 0
            used.add((pal - pool.start) // 32)
    assert used == set(range(1, 15))  # all but set 0's line 2 and the black one
    assert stage.end == _seg(project, "pal_script_index").start


def _script(rom, at):
    """(line, colour offset, end) of the palette script at ``at`` (0112A8)."""
    head = rom.data[at]
    return head & 0x0F, rom.data[at + 1], at + 2 + 2 * ((head >> 4) + 1)


def test_scripts_tile_their_segments(project, baserom):
    index = _seg(project, "pal_script_index")
    scripts, lines = _seg(project, "pal_scripts"), _seg(project, "pal_lines")
    offs = _offsets(baserom, index.start)
    assert len(offs) == 69 and index.start + min(offs) == index.end == scripts.start
    spans = {}
    for off in offs:
        at = index.start + off
        spans[at] = _script(baserom, at)[2]
    covered, at = [], scripts.start
    for start in sorted(spans):
        assert start == at, f"gap or overlap at {at:06X}"
        covered.append(start)
        at = spans[start]
    assert at == lines.end
    whole = [s for s in covered if s >= lines.start]
    assert whole == list(range(lines.start, lines.end, 34))
    for s in whole:  # F_ 00: sixteen words from colour 0
        assert baserom.data[s] >> 4 == 0xF and baserom.data[s + 1] == 0
    assert all(s < scripts.end and spans[s] <= scripts.end for s in covered if s < lines.start)


def test_cycles_tile_their_segment(project, baserom):
    seg = _seg(project, "pal_cycles")
    offs = _offsets(baserom, seg.start)
    assert len(offs) == 8 and offs[0] == offs[1]  # cycle 0 means none
    parts = {}
    for off in set(offs):
        at = seg.start + off
        count = baserom.data[at + 1] + 1
        frames, seq = baserom.u32(at + 4), baserom.u32(at + 8)
        parts[at] = at + 12
        fr = _offsets(baserom, frames)
        parts[frames] = frames + 2 * len(fr)
        for f in fr:
            parts[frames + f] = frames + f + 2 * count
        end = seq
        while baserom.data[end] != 0 and baserom.data[end] < 0x80:
            assert 1 <= baserom.data[end] <= len(fr)
            end += 1
        parts[seq] = end + 1
    at = seg.start + 2 * len(offs)
    for start in sorted(parts):
        if start == at + 1 and at % 2 and baserom.data[at] == 0:
            at += 1  # padding after an odd-length sequence
        assert start == at, f"gap or overlap at {at:06X}"
        at = parts[start]
    assert at + (at % 2) == seg.end
