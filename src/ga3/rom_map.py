"""``rom_map.yml``: the single home of every ROM offset.

The map is a sorted list of non-overlapping segments covering the image.
Each segment has a ``type`` that selects an asset handler (see ``ga3.assets``)
and, for extractable types, a ``path`` relative to ``assets/``. Gaps between
declared segments are synthesised as ``unknown`` so coverage is measurable and
nothing is silently skipped.

Integers must be written with a ``0x`` prefix. PyYAML would otherwise read
``0179F2`` as the decimal 179 followed by garbage, or as a string, depending
on the digits -- the loader rejects anything that is not an int.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

PASSTHROUGH_TYPES = frozenset({"code", "data", "free", "unknown"})
ASSET_TYPES = frozenset({"header", "table", "text", "tiles4bpp", "nemesis", "pcm", "raw"})
GENERATED_TYPES = frozenset({"patch"})
ALL_TYPES = PASSTHROUGH_TYPES | ASSET_TYPES | GENERATED_TYPES


class RomMapError(ValueError):
    pass


@dataclass
class Segment:
    name: str
    start: int
    end: int
    type: str
    path: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    synthetic: bool = False

    @property
    def size(self) -> int:
        return self.end - self.start

    def get(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key, default)

    def __str__(self) -> str:
        return f"{self.name} [{self.start:06X}-{self.end:06X}] {self.type}"


@dataclass
class RomMap:
    rom: dict[str, Any]
    palettes: dict[str, dict[str, Any]]
    segments: list[Segment]
    source: str = "rom_map.yml"

    @property
    def size(self) -> int:
        return int(self.rom["size"])

    def by_name(self, name: str) -> Segment:
        for s in self.segments:
            if s.name == name:
                return s
        raise RomMapError(f"no segment named {name!r} in {self.source}")

    def by_type(self, *types: str) -> list[Segment]:
        return [s for s in self.segments if s.type in types]

    def declared(self) -> list[Segment]:
        return [s for s in self.segments if not s.synthetic]

    def coverage(self) -> dict[str, int]:
        cov: dict[str, int] = {}
        for s in self.segments:
            cov[s.type] = cov.get(s.type, 0) + s.size
        return cov


def _int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RomMapError(f"{where}: expected a 0x-prefixed integer, got {value!r}")
    return value


def _parse_segment(raw: dict[str, Any], idx: int) -> Segment:
    where = f"segments[{idx}]"
    if not isinstance(raw, dict):
        raise RomMapError(f"{where}: expected a mapping")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise RomMapError(f"{where}: missing name")
    where = f"segment {name!r}"
    start = _int(raw.get("start"), where + ".start")
    if "end" in raw:
        end = _int(raw["end"], where + ".end")
    elif "size" in raw:
        end = start + _int(raw["size"], where + ".size")
    else:
        raise RomMapError(f"{where}: needs end or size")
    if end <= start:
        raise RomMapError(f"{where}: end {end:06X} must be greater than start {start:06X}")
    stype = raw.get("type")
    if stype not in ALL_TYPES:
        raise RomMapError(f"{where}: unknown type {stype!r}; valid: {sorted(ALL_TYPES)}")
    path = raw.get("path")
    if path is not None and not isinstance(path, str):
        raise RomMapError(f"{where}: path must be a string")
    if stype in ASSET_TYPES and path is None:
        raise RomMapError(f"{where}: type {stype} requires a path")
    attrs = {
        k: v for k, v in raw.items() if k not in {"name", "start", "end", "size", "type", "path"}
    }
    return Segment(name, start, end, stype, path, attrs)


def parse(doc: dict[str, Any], source: str = "rom_map.yml") -> RomMap:
    if not isinstance(doc, dict) or "rom" not in doc or "segments" not in doc:
        raise RomMapError(f"{source}: expected top-level 'rom' and 'segments' keys")
    rom = dict(doc["rom"])
    size = _int(rom.get("size"), "rom.size")
    segments = [_parse_segment(s, i) for i, s in enumerate(doc["segments"])]

    names = [s.name for s in segments]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise RomMapError(f"duplicate segment names: {dupes}")

    ordered = sorted(segments, key=lambda s: s.start)
    if [s.name for s in ordered] != names:
        raise RomMapError("segments must be listed in ascending start order")
    prev = None
    for s in ordered:
        if prev is not None and s.start < prev.end:
            raise RomMapError(f"segments overlap: {prev} and {s}")
        if s.end > size:
            raise RomMapError(f"{s} extends past rom.size 0x{size:X}")
        prev = s

    _attach_patches(doc.get("patches") or {}, ordered)
    filled = fill_gaps(ordered, size)
    palettes = dict(doc.get("palettes") or {})
    return RomMap(rom, palettes, filled, source)


def _attach_patches(patches: dict[str, Any], segments: list[Segment]) -> None:
    """Give every ``patch: NAME`` segment its patch definition and all section origins.

    A patch assembled from one source into several free-space slots is one entry
    under the top-level ``patches:`` key; each slot is a ``patch`` segment with
    ``patch: NAME`` and ``section: SECTION``. The handler then sees, on its own
    segment, ``patch_def`` (that entry) and ``sections`` (section -> start).
    """
    if not isinstance(patches, dict):
        raise RomMapError("patches: expected a mapping of patch name -> definition")
    by_patch: dict[str, dict[str, Segment]] = {}
    for seg in segments:
        name = seg.get("patch")
        if name is None:
            continue
        if name not in patches:
            raise RomMapError(f"{seg}: patch {name!r} is not defined under patches:")
        section = seg.get("section")
        if not isinstance(section, str):
            raise RomMapError(f"{seg}: a segment of patch {name!r} needs section: NAME")
        if section in by_patch.setdefault(name, {}):
            raise RomMapError(f"patch {name!r}: section {section!r} is given twice")
        by_patch[name][section] = seg
    for name, slots in by_patch.items():
        sections = {sec: seg.start for sec, seg in slots.items()}
        for seg in slots.values():
            seg.attrs["patch_def"] = patches[name]
            seg.attrs["sections"] = sections


def fill_gaps(segments: list[Segment], size: int) -> list[Segment]:
    """Insert synthetic ``unknown`` segments for every uncovered byte range."""
    out: list[Segment] = []
    pos = 0
    for s in segments:
        if s.start > pos:
            out.append(Segment(f"unk_{pos:06X}", pos, s.start, "unknown", synthetic=True))
        out.append(s)
        pos = s.end
    if pos < size:
        out.append(Segment(f"unk_{pos:06X}", pos, size, "unknown", synthetic=True))
    return out


def load(path: str | os.PathLike) -> RomMap:
    with open(path, encoding="utf-8") as fh:
        try:
            doc = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise RomMapError(f"{path}: not valid YAML: {exc}") from None
    return parse(doc, str(path))


def coverage_report(rm: RomMap) -> str:
    cov = rm.coverage()
    total = rm.size
    lines = [f"{rm.source}: {len(rm.declared())} declared segments, {len(rm.segments)} with gaps"]
    for t, n in sorted(cov.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {t:10s} {n:8d} B  {100.0 * n / total:5.1f}%")
    unk = [s for s in rm.segments if s.type == "unknown"]
    if unk:
        lines.append("unknown ranges:")
        for s in unk:
            lines.append(f"  {s.start:06X}-{s.end:06X}  {s.size:7d} B  {s.name}")
    return "\n".join(lines)


def _md_text(text: str) -> str:
    """Free text for a Markdown table cell: escape what Markdown would eat.

    ``*`` would start emphasis and ``<word>`` would be dropped as an HTML tag,
    except inside code spans (between backticks); ``|`` would split the cell
    even there, so it is escaped everywhere.
    """
    parts = str(text).split("`")
    for i in range(0, len(parts), 2):  # even parts are outside code spans
        for ch in "\\*<":
            parts[i] = parts[i].replace(ch, "\\" + ch)
    return "`".join(parts).replace("|", "\\|")


def markdown_table(rm: RomMap) -> str:
    """The ROM map as a Markdown table (feeds docs/rom_map.md and the README)."""
    lines = [
        "| Range | Type | Segment | Asset | Notes |",
        "|---|---|---|---|---|",
    ]
    for s in rm.segments:
        notes = []
        if "tiles" in s.attrs:
            notes.append(f"{s.attrs['tiles']} tiles" + (", XOR" if s.attrs.get("xor") else ""))
        if "format" in s.attrs:
            notes.append(f"format {s.attrs['format']}")
        if "fill" in s.attrs:
            notes.append(f"filled with 0x{s.attrs['fill']:02X}")
        if "note" in s.attrs:
            notes.append(_md_text(s.attrs["note"]))
        if "evidence" in s.attrs:
            notes.append(f"*evidence: {_md_text(s.attrs['evidence'])}*")
        lines.append(
            f"| `{s.start:06X}–{s.end:06X}` | {s.type} | {s.name} | "
            f"{'`' + s.path + '`' if s.path else ''} | {'; '.join(notes)} |"
        )
    return "\n".join(lines) + "\n"
