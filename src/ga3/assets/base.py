"""The ``Handler`` interface, project ``Paths`` and the atomic writers every asset type shares."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..rom import Rom
from ..rom_map import Segment


class BuildError(RuntimeError):
    """An asset cannot be placed into the image (overflow, bad format, missing file)."""


@dataclass
class Paths:
    root: Path
    assets: Path
    build: Path

    def asset(self, rel: str) -> Path:
        return self.assets / rel

    def preview(self, rel: str) -> Path:
        return self.build / "preview" / rel


def write_bytes(path: Path, data: bytes) -> Path:
    os.makedirs(path.parent, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return path


def write_text(path: Path, text: str) -> Path:
    os.makedirs(path.parent, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


class Handler:
    """Interface every asset type implements."""

    #: files this handler writes are meant to be committed
    committed = True

    def extract(self, rom: Rom, seg: Segment, paths: Paths) -> list[Path]:
        raise NotImplementedError

    def build(self, rom: Rom, seg: Segment, paths: Paths) -> str | None:
        """Place the asset into ``rom.data``. Return a short note for the log, or None."""
        raise NotImplementedError

    def check(self, rom: Rom, seg: Segment) -> list[str]:
        """Consistency problems between the map entry and the base ROM (for ``ga3 map --check``)."""
        return []

    def sources(self, seg: Segment, paths: Paths) -> list[Path]:
        """Files ``build`` needs for this segment -- what has to be committed.

        Handlers with several files per segment override this; passthrough
        handlers (``committed = False``) are never asked.
        """
        return [paths.asset(seg.path)] if seg.path else []

    @staticmethod
    def place(rom: Rom, seg: Segment, blob: bytes, pad: int | None = 0x00) -> None:
        if len(blob) > seg.size:
            raise BuildError(
                f"{seg}: needs {len(blob)} bytes, slot holds {seg.size} "
                f"(overflow {len(blob) - seg.size})"
            )
        if len(blob) < seg.size:
            if pad is None:
                raise BuildError(f"{seg}: expected exactly {seg.size} bytes, got {len(blob)}")
            blob = blob + bytes([pad]) * (seg.size - len(blob))
        rom.data[seg.start : seg.end] = blob
