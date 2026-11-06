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


CONSTANT_WIDTH = {"u8": 1, "u16": 2}


@dataclass(frozen=True)
class Site:
    """One instruction that carries a constant: its address, its base-ROM bytes
    (hex in the map) and the offset of the operand inside them."""

    at: int
    expect: bytes
    offset: int


@dataclass
class Constant:
    """A number inside the game's code (an instruction operand), edited by name."""

    name: str
    format: str
    sites: list[Site]
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def width(self) -> int:
        return CONSTANT_WIDTH[self.format]

    def get(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key, default)

    @property
    def limit(self) -> int:
        """The largest value allowed: ``max`` when given, else what the format holds."""
        return self.attrs.get("max", (1 << (8 * self.width)) - 1)


@dataclass
class RomMap:
    rom: dict[str, Any]
    palettes: dict[str, dict[str, Any]]
    segments: list[Segment]
    source: str = "rom_map.yml"
    constants: dict[str, Constant] = field(default_factory=dict)
    constants_path: str | None = None

    @property
    def size(self) -> int:
        """Size of the base ROM (the dump ``map --check`` compares against)."""
        return int(self.rom["size"])

    @property
    def image_size(self) -> int:
        """Size of the built image: ``rom.build_size`` when the map expands it."""
        return int(self.rom.get("build_size", self.rom["size"]))

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
    image = size
    if "build_size" in rom:
        image = _int(rom["build_size"], "rom.build_size")
        if not size <= image <= 0x400000 or image % 0x20000:
            raise RomMapError(
                "rom.build_size: expected a multiple of 128 KiB between rom.size and 4 MiB"
            )
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
        if s.end > image:
            raise RomMapError(f"{s} extends past the image (0x{image:X})")
        prev = s

    _attach_patches(doc.get("patches") or {}, ordered)
    filled = fill_gaps(ordered, image)
    palettes = dict(doc.get("palettes") or {})
    path, constants = _parse_constants(doc.get("constants"), size)
    return RomMap(rom, palettes, filled, source, constants, path)


def _parse_constants(block: Any, size: int) -> tuple[str | None, dict[str, Constant]]:
    """The top-level ``constants:`` key: numbers inside code, edited by name.

    ``path`` is the asset file (relative to ``assets/``) holding the values;
    under ``values`` every constant has ``format`` (u8 | u16), ``sites`` --
    ``[address, "base-ROM bytes of the instruction", operand offset]`` for each
    instruction that carries it -- and, like a segment, ``evidence`` (required),
    ``note`` and ``max_hud`` (a warning above it). ``max`` is a hard limit: a
    larger value is refused by ``ga3 balance set`` and by the build.
    """
    if not block:
        return None, {}
    if not isinstance(block, dict) or not isinstance(block.get("path"), str):
        raise RomMapError("constants: expected a mapping with path: and values:")
    values = block.get("values")
    if not isinstance(values, dict) or not values:
        raise RomMapError("constants: values: must map constant names to definitions")
    out: dict[str, Constant] = {}
    for name, d in values.items():
        where = f"constants.{name}"
        if not isinstance(d, dict):
            raise RomMapError(f"{where}: expected a mapping")
        fmt = d.get("format", "u8")
        if fmt not in CONSTANT_WIDTH:
            raise RomMapError(f"{where}: format must be one of {sorted(CONSTANT_WIDTH)}")
        if not d.get("evidence"):
            raise RomMapError(f"{where}: evidence is required (how the address was proven)")
        raw_sites = d.get("sites")
        if not isinstance(raw_sites, list) or not raw_sites:
            raise RomMapError(f'{where}: sites: expected [[address, "hex bytes", offset], ...]')
        sites = []
        for i, s in enumerate(raw_sites):
            if not (isinstance(s, list) and len(s) == 3 and isinstance(s[1], str)):
                raise RomMapError(f'{where}.sites[{i}]: expected [address, "hex bytes", offset]')
            at = _int(s[0], f"{where}.sites[{i}] address")
            offset = _int(s[2], f"{where}.sites[{i}] offset")
            try:
                expect = bytes.fromhex(s[1])
            except ValueError:
                raise RomMapError(f"{where}.sites[{i}]: {s[1]!r} is not hex bytes") from None
            if offset + CONSTANT_WIDTH[fmt] > len(expect):
                raise RomMapError(f"{where}.sites[{i}]: the operand runs past the bytes given")
            if at + len(expect) > size:
                raise RomMapError(f"{where}.sites[{i}]: 0x{at:06X} is past rom.size")
            sites.append(Site(at, expect, offset))
        attrs = {k: v for k, v in d.items() if k not in ("format", "sites")}
        if "max" in attrs:
            top = (1 << (8 * CONSTANT_WIDTH[fmt])) - 1
            if not isinstance(attrs["max"], int) or isinstance(attrs["max"], bool):
                raise RomMapError(f"{where}: max must be an integer")
            if not 0 <= attrs["max"] <= top:
                raise RomMapError(f"{where}: max must be within 0..{top} ({fmt})")
        out[name] = Constant(name, fmt, sites, attrs)
    return block["path"], out


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
    unused = sorted(set(patches) - set(by_patch))
    if unused:
        raise RomMapError(f"patch {unused[0]!r} has no segment (patch: NAME + section: NAME)")
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
    total = rm.image_size
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


def constants_table(rm: RomMap) -> str:
    """The ``constants:`` block as a Markdown table (feeds docs/rom_map.md)."""
    lines = [
        "| Constant | Format | Instructions | Notes |",
        "|---|---|---|---|",
    ]
    for c in rm.constants.values():
        sites = ", ".join(f"`{s.at:06X}`" for s in c.sites)
        notes = [_md_text(c.get("note", ""))] if c.get("note") else []
        notes.append(f"*evidence: {_md_text(c.get('evidence'))}*")
        lines.append(f"| {c.name} | {c.format} | {sites} | {'; '.join(notes)} |")
    return "\n".join(lines) + "\n"


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
