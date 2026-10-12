"""Lag frames: frames the game's main loop did not finish in time.

The game ends every frame by calling its frame-wait routine (``frame_wait`` on
the code segment in ``rom_map.yml``): it clears the VBlank flag and spins
until the interrupt sets it again. A breakpoint there fires once per frame when
the loop keeps up; a gap of N frames between two calls means N - 1 frames were
lost to work that did not fit (decompression, heavy scenes).
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

_FRAME = re.compile(r"frame=(\d+)")


@dataclass
class LagReport:
    first: int  # frame of the first frame-wait call
    last: int  # frame of the last one
    calls: int
    gaps: list[tuple[int, int]] = field(default_factory=list)  # (after frame, frames) when > 1

    @property
    def frames(self) -> int:
        return self.last - self.first + 1 if self.calls else 0

    @property
    def lost(self) -> int:
        return sum(g - 1 for _f, g in self.gaps)

    def summary(self) -> str:
        if not self.calls:
            return "the frame-wait routine never ran"
        pct = 100.0 * self.lost / self.frames
        hist = Counter(g for _f, g in self.gaps)
        spread = ", ".join(f"{g} frames x{n}" for g, n in sorted(hist.items())) or "none"
        return (
            f"frames {self.first}-{self.last}: {self.lost} of {self.frames} lost ({pct:.1f}%); "
            f"gaps: {spread}"
        )


def parse_log(lines) -> LagReport:
    """A watchlog that holds only frame-wait breakpoint lines."""
    frames = [int(m.group(1)) for line in lines if (m := _FRAME.search(line))]
    if not frames:
        return LagReport(0, 0, 0)
    gaps = [(a, b - a) for a, b in zip(frames, frames[1:], strict=False) if b - a > 1]
    return LagReport(frames[0], frames[-1], len(frames), gaps)


def measure(
    exe: Path,
    rom: Path,
    scene: Path,
    frame_wait: int,
    overclock: int = 100,
    cwd: Path | None = None,
) -> LagReport:
    """Run ``scene`` with a breakpoint on the frame-wait routine and report the gaps."""
    with tempfile.TemporaryDirectory(prefix="ga3-lag-") as tmp:
        log = Path(tmp) / "wait.log"
        wrapper = Path(tmp) / "lag.txt"
        wrapper.write_text(
            f"watchlog {log}\nbp {frame_wait:06X}\ninclude {scene.resolve()}\n", encoding="utf-8"
        )
        cmd = [str(exe), "--rom", str(rom), "--script", str(wrapper), "--quiet"]
        if overclock != 100:
            cmd += ["--overclock", str(overclock)]
        subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.DEVNULL)
        with open(log, encoding="utf-8") as fh:
            return parse_log(fh)
