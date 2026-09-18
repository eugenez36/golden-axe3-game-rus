"""extract -> build -> verify orchestration.

``build`` starts from the base ROM, lets every segment's handler place its
asset, then fixes the header and writes ``build/ga3.bin`` plus an IPS patch
against the base ROM. With unchanged assets the result is byte-identical to
the base ROM -- that is the property ``verify`` and the tests defend.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from . import rom_map as rm
from .assets import BuildError, Paths, handler_for
from .rom import Rom, apply_ips, make_ips

MAP_FILE = "rom_map.yml"
SHA_FILE = "roms.sha1"
BASEROM_REL = "baserom/ga3.bin"
BUILD_ROM_REL = "build/ga3.bin"
BUILD_IPS_REL = "build/ga3.ips"


class PipelineError(RuntimeError):
    pass


@dataclass
class Project:
    root: Path
    map: rm.RomMap
    paths: Paths

    @property
    def baserom(self) -> Path:
        return self.root / BASEROM_REL

    @property
    def build_rom(self) -> Path:
        return self.root / BUILD_ROM_REL

    @property
    def build_ips(self) -> Path:
        return self.root / BUILD_IPS_REL

    @property
    def sha_file(self) -> Path:
        return self.root / SHA_FILE


def find_root(start: str | os.PathLike | None = None) -> Path:
    """Walk up from ``start`` (default: the working directory) to the directory holding rom_map.yml.

    ``$GA3_ROOT`` short-circuits the walk when no explicit start is given.
    """
    env = os.environ.get("GA3_ROOT")
    if start is None and env:
        root = Path(env).resolve()
        if not (root / MAP_FILE).exists():
            raise PipelineError(f"GA3_ROOT={env} has no {MAP_FILE}")
        return root
    p = Path(start or os.getcwd()).resolve()
    for cand in (p, *p.parents):
        if (cand / MAP_FILE).exists():
            return cand
    raise PipelineError(f"{MAP_FILE} not found in {p} or any parent (pass --root or set GA3_ROOT)")


def open_project(root: str | os.PathLike | None = None) -> Project:
    """The project containing ``root`` (or the working directory)."""
    r = find_root(root)
    romap = rm.load(r / MAP_FILE)
    return Project(r, romap, Paths(root=r, assets=r / "assets", build=r / "build"))


def load_baserom(proj: Project, path: str | os.PathLike | None = None, strict: bool = True) -> Rom:
    p = Path(path) if path else proj.baserom
    if not p.exists():
        raise PipelineError(
            f"base ROM not found at {p}. Put your dump there "
            f"(expected sha1 {proj.map.rom.get('sha1')}); see baserom/README.md"
        )
    rom = Rom.load(p)
    want = proj.map.rom.get("sha1")
    if strict and want and rom.sha1() != want:
        raise PipelineError(f"{p}: sha1 {rom.sha1()} does not match rom_map.yml ({want})")
    return rom


# ---------------------------------------------------------------- extract


def extract_all(proj: Project, rom: Rom, only: set[str] | None = None, log=print) -> list[Path]:
    written: list[Path] = []
    for seg in proj.map.segments:
        if only and seg.name not in only:
            continue
        h = handler_for(seg)
        try:
            files = h.extract(rom, seg, proj.paths)
        except BuildError as exc:
            raise PipelineError(str(exc)) from None
        if files:
            rel = ", ".join(os.path.relpath(f, proj.root) for f in files[:2])
            more = f" (+{len(files) - 2})" if len(files) > 2 else ""
            log(f"  {seg.start:06X}-{seg.end:06X}  {seg.type:9s} {seg.name:18s} -> {rel}{more}")
        written.extend(files)
    return written


# ---------------------------------------------------------------- build


def build(proj: Project, base: Rom, out: Path | None = None, ips: bool = True, log=print) -> Rom:
    rom = Rom(bytes(base.data), str(out or proj.build_rom))
    size = proj.map.size
    if len(rom.data) < size:
        rom.expand(size, fill=0xFF)
    for seg in proj.map.segments:
        h = handler_for(seg)
        try:
            note = h.build(rom, seg, proj.paths)
        except BuildError as exc:
            raise PipelineError(str(exc)) from None
        if note:
            log(f"  {seg.start:06X}-{seg.end:06X}  {seg.name:18s} {note}")
    rom.save(out or proj.build_rom, fix_header=True)
    log(f"wrote {rom.path}  sha1 {rom.sha1()}  checksum 0x{rom.stored_checksum():04X}")
    if ips:
        patch = make_ips(bytes(base.data), bytes(rom.data))
        if apply_ips(bytes(base.data), patch) != bytes(rom.data):
            raise PipelineError(
                "IPS self-check failed: applying the patch does not reproduce the build"
            )
        ips_path = out.with_suffix(".ips") if out else proj.build_ips
        os.makedirs(ips_path.parent, exist_ok=True)
        ips_path.write_bytes(patch)
        payload = len(patch) - 8  # minus "PATCH" and "EOF"
        what = "no changes" if payload == 0 else f"{payload} B of records"
        log(f"wrote {ips_path}  ({len(patch)} bytes, {what})")
    return rom


# ---------------------------------------------------------------- verify


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_sha_file(path: Path) -> dict[str, str]:
    """``sha1sum`` output -> {name: digest}; accepts the binary-mode ``*name`` marker and tabs."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise PipelineError(f"{path}:{lineno}: expected '<sha1>  <file>', got {raw!r}")
        digest, name = parts
        out[name.strip().lstrip("*")] = digest
    return out


def write_sha_file(path: Path, entries: dict[str, str]) -> None:
    lines = ["# sha1sum -c roms.sha1   (base ROM first, then every build product)"]
    for name, digest in entries.items():
        lines.append(f"{digest}  {name}")
    path.write_text("\n".join(lines) + "\n")


def verify(proj: Project, update: bool = False, log=print) -> bool:
    """Check the base ROM and the build against ``roms.sha1`` and the IPS against the build.

    ``update`` records new or changed hashes -- but only when nothing else is
    wrong: a missing file or an IPS that does not reproduce the build still fails.
    """
    problems = 0
    entries = read_sha_file(proj.sha_file)
    checks = {BASEROM_REL: proj.baserom, BUILD_ROM_REL: proj.build_rom}
    actual: dict[str, str] = {}
    for name, path in checks.items():
        if not path.exists():
            log(f"  MISSING  {name}")
            problems += 1
            continue
        actual[name] = sha1_of(path)
        want = entries.get(name)
        if want == actual[name]:
            log(f"  OK       {name}")
        elif want is None:
            log(f"  NEW      {name}  {actual[name]}")
            problems += 0 if update else 1
        elif update:
            log(f"  UPDATE   {name}  {want[:12]}... -> {actual[name][:12]}...")
        else:
            log(f"  FAIL     {name}  expected {want}  got {actual[name]}")
            problems += 1
    if proj.build_rom.exists() and proj.build_ips.exists() and proj.baserom.exists():
        try:
            rebuilt = apply_ips(proj.baserom.read_bytes(), proj.build_ips.read_bytes())
        except ValueError as exc:
            log(f"  FAIL     {BUILD_IPS_REL}: {exc}")
            problems += 1
        else:
            if rebuilt == proj.build_rom.read_bytes():
                log(f"  OK       {BUILD_IPS_REL} reproduces the build")
            else:
                log(f"  FAIL     {BUILD_IPS_REL} does not reproduce the build")
                problems += 1
    if update and actual:
        if problems:
            log(f"not updating {SHA_FILE}: {problems} problem(s) above")
        else:
            merged = dict(entries)
            merged.update(actual)
            write_sha_file(proj.sha_file, merged)
            log(f"updated {proj.sha_file.relative_to(proj.root)}")
    return problems == 0


# ---------------------------------------------------------------- map checks


def check_assets(proj: Project) -> list[str]:
    """Committed files that ``build`` would need but the tree lacks. Needs no ROM."""
    problems: list[str] = []
    for seg in proj.map.segments:
        h = handler_for(seg)
        if not h.committed:
            continue
        try:
            missing = [p for p in h.sources(seg, proj.paths) if not p.exists()]
        except BuildError as exc:
            problems.append(str(exc))
            continue
        problems.extend(f"{seg}: missing {os.path.relpath(p, proj.root)}" for p in missing)
    return problems


def check_map(proj: Project, rom: Rom) -> list[str]:
    """Consistency of rom_map.yml with the base ROM, plus ``check_assets``."""
    problems: list[str] = []
    if len(rom.data) != proj.map.size:
        problems.append(f"base ROM is {len(rom.data)} bytes, rom_map.yml says 0x{proj.map.size:X}")
    want_cs = proj.map.rom.get("header_checksum")
    if want_cs is not None and rom.stored_checksum() != want_cs:
        problems.append(f"header checksum 0x{rom.stored_checksum():04X} != 0x{want_cs:04X}")
    entry = proj.map.rom.get("entry_point")
    if entry is not None and rom.u32(4) != entry:
        problems.append(f"reset vector 0x{rom.u32(4):08X} != entry_point 0x{entry:06X}")
    serial = proj.map.rom.get("serial")
    if serial is not None and rom.serial != serial:
        problems.append(f"header serial {rom.serial!r} != rom_map.yml {serial!r}")
    for seg in proj.map.segments:
        problems.extend(handler_for(seg).check(rom, seg))
    problems.extend(check_assets(proj))
    return problems
