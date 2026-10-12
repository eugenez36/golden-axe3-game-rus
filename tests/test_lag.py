"""``ga3 lag``: frame-wait gaps from a breakpoint log. No ROM or emulator needed."""

from __future__ import annotations

import stat
import sys

from ga3 import lag
from ga3.pipeline import open_project

from .conftest import ROOT


def _log(frames):
    return [f"BP frame={f} pc=00F006 a0=00000000" for f in frames]


def test_parse_log_counts_lost_frames():
    report = lag.parse_log(["noise", *_log([10, 11, 12, 15, 16, 20])])
    assert (report.first, report.last, report.calls) == (10, 20, 6)
    assert report.gaps == [(12, 3), (16, 4)]
    assert report.frames == 11 and report.lost == 5
    assert report.summary() == "frames 10-20: 5 of 11 lost (45.5%); gaps: 3 frames x1, 4 frames x1"


def test_parse_log_without_lag_or_calls():
    assert lag.parse_log(_log(range(100, 160))).summary().endswith("0 of 60 lost (0.0%); gaps: none")
    empty = lag.parse_log([])
    assert empty.frames == 0 and empty.summary() == "the frame-wait routine never ran"


def test_measure_wraps_the_scene_and_passes_overclock(tmp_path):
    scene = tmp_path / "scene.txt"
    scene.write_text("wait 3\n", encoding="utf-8")
    seen = tmp_path / "argv.txt"
    fake = tmp_path / "fake_emu.py"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"open({str(seen)!r}, 'w').write(' '.join(sys.argv[1:]))\n"
        "script = open(sys.argv[sys.argv.index('--script') + 1]).read().splitlines()\n"
        "log = script[0].split(' ', 1)[1]\n"
        "assert script[1] == 'bp 00F006' and script[2].startswith('include ')\n"
        "open(log, 'w').write('\\n'.join(f'BP frame={f} pc=00F006' for f in (1, 2, 4)))\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    report = lag.measure(fake, tmp_path / "rom.bin", scene, 0x00F006, overclock=150)
    assert report.gaps == [(2, 2)]
    assert "--overclock 150" in seen.read_text()
    lag.measure(fake, tmp_path / "rom.bin", scene, 0x00F006)
    assert "--overclock" not in seen.read_text()


def test_the_map_declares_the_frame_wait_routine():
    proj = open_project(ROOT)
    found = [s for s in proj.map.segments if s.get("frame_wait") is not None]
    assert len(found) == 1
    seg = found[0]
    assert seg.type == "code" and seg.start <= seg.get("frame_wait") < seg.end
