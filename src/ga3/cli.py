"""``ga3`` command line: one entry point, one subcommand per job.

Commands read the base ROM from ``baserom/ga3.bin``; ``--rom`` points them at
another image (trusted as is, with a note when its sha1 differs from the
map's) and the inspection commands also take ``--file``. The base ROM is
never overwritten: builds and patches go to ``build/`` or to the ``-o`` path.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import (
    __version__,
    balance,
    font,
    nemesis,
    palette,
    pipeline,
    ramsearch,
    rom_map,
    table,
    text,
    tiles,
)
from .assets import handler_for
from .assets.base import write_bytes, write_text
from .assets.nemesis_asset import FontArtHandler
from .rom import Rom, apply_ips, diff_report, make_ips


def _hex(s: str) -> int:
    """Hex with or without a 0x prefix (every ROM address on the CLI is hex)."""
    return int(s, 16)


def _proj(args) -> pipeline.Project:
    return pipeline.open_project(getattr(args, "root", None))


def _try_proj(args) -> pipeline.Project | None:
    """The project, or None when the command runs outside any project tree."""
    try:
        return _proj(args)
    except pipeline.PipelineError:
        return None


def _open_image(args, proj: pipeline.Project | None, strict: bool | None = None) -> Rom:
    """The image a command works on: ``--file``, then ``--rom``, then the base ROM.

    ``strict=None`` verifies the sha1 against rom_map.yml only for the default
    base ROM; an explicit ``--rom`` is used as is, with a note when it differs.
    ``strict=True`` always verifies, ``strict=False`` never does.
    """
    file = getattr(args, "file", None)
    if file:
        return Rom.load(file)
    rom_arg = getattr(args, "rom", None)
    if proj is None:
        if rom_arg:
            return Rom.load(rom_arg)
        raise pipeline.PipelineError(
            "no rom_map.yml found: run inside the project or pass --root, --rom or --file"
        )
    check = strict if strict is not None else not rom_arg
    rom = pipeline.load_baserom(proj, rom_arg, strict=check)
    if rom_arg and not check:
        want = proj.map.rom.get("sha1")
        if want and rom.sha1() != want:
            print(
                f"note: {rom.path}: sha1 differs from rom_map.yml ({want[:12]}...)", file=sys.stderr
            )
    return rom


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


def _report_problems(what: str, problems: list[str]) -> int:
    for p in problems:
        print("  " + p)
    print(f"{what}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 0 if not problems else 1


# ---------------------------------------------------------------- pipeline


def cmd_extract(args) -> int:
    proj = _proj(args)
    rom = _open_image(args, proj)
    only = set(args.only) if args.only else None
    print(f"extracting from {rom.path} (sha1 {rom.sha1()[:12]}...) into {proj.paths.assets}")
    files = pipeline.extract_all(proj, rom, only)
    print(f"{len(files)} file(s) written")
    if args.png:
        _previews(proj, rom)
    return 0


def _previews(proj: pipeline.Project, rom: Rom) -> None:
    for seg in proj.map.by_type("nemesis"):
        raw = nemesis.decompress(rom.data, seg.start)
        out = proj.paths.preview(Path(seg.path).with_suffix(".png").name)
        tiles.dump_tiles(raw, 0, len(raw) // 32, str(out), cols=16, scale=2)
        print(f"  preview {out.relative_to(proj.root)}")


def cmd_build(args) -> int:
    proj = _proj(args)
    base = _open_image(args, proj)
    out = Path(args.out).resolve() if args.out else None
    pipeline.build(proj, base, out=out, ips=not args.no_ips)
    return 0


def cmd_verify(args) -> int:
    proj = _proj(args)
    ok = pipeline.verify(proj, update=args.update)
    print("verify: OK" if ok else "verify: FAILED")
    return 0 if ok else 1


def cmd_map(args) -> int:
    proj = _proj(args)
    if args.markdown:
        print(rom_map.markdown_table(proj.map), end="")
        return 0
    if args.check:
        return _report_problems("map check", pipeline.check_map(proj, _open_image(args, proj)))
    if args.check_assets:
        return _report_problems("asset check", pipeline.check_assets(proj))
    print(rom_map.coverage_report(proj.map))
    if args.list:
        for s in proj.map.segments:
            print(f"  {s.start:06X}-{s.end:06X} {s.size:7d}  {s.type:9s} {s.name}  {s.path or ''}")
    return 0


def cmd_assets(args) -> int:
    """Regenerate derived-but-committed files: encoding.tbl, font.nem, docs/rom_map.md."""
    proj = _proj(args)
    changed = []
    tbl = proj.paths.asset("text/encoding.tbl")
    new = table.format_tbl()
    if not tbl.exists() or tbl.read_text(encoding="utf-8") != new:
        write_text(tbl, new)
        changed.append(tbl)
    for seg in proj.map.by_type("nemesis"):
        h = handler_for(seg)
        if isinstance(h, FontArtHandler):
            path, did = h.refresh_blob(seg, proj.paths)
            if did:
                changed.append(path)
    md = proj.root / "docs" / "rom_map.md"
    body = _rom_map_doc(proj)
    if not md.exists() or md.read_text(encoding="utf-8") != body:
        write_text(md, body)
        changed.append(md)
    for c in changed:
        print(f"  refreshed {c.relative_to(proj.root)}")
    print("assets: up to date" if not changed else f"assets: {len(changed)} file(s) refreshed")
    return 0


def _rom_map_doc(proj: pipeline.Project) -> str:
    cov = proj.map.coverage()
    total = proj.map.image_size
    info = proj.map.rom
    grown = (
        f" The build expands it to {total} bytes ({total // 0x100000} MiB)."
        if total != proj.map.size
        else ""
    )
    lines = [
        "# ROM map",
        "",
        "Generated from `rom_map.yml` by `ga3 assets refresh`. Do not edit by hand.",
        "",
        f"Base image: **{info.get('title')}**, {proj.map.size} bytes, sha1 `{info.get('sha1')}`,",
        f"header checksum `{info.get('header_checksum'):04X}`, "
        f"entry point `{info.get('entry_point'):06X}`.{grown}",
        "",
        "## Coverage",
        "",
        "| Type | Bytes | Share |",
        "|---|---|---|",
    ]
    for t, n in sorted(cov.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {t} | {n} | {100.0 * n / total:.1f}% |")
    lines += ["", "## Segments", "", rom_map.markdown_table(proj.map)]
    if proj.map.constants:
        lines += [
            f"## Constants (instruction operands, values in `assets/{proj.map.constants_path}`)",
            "",
            rom_map.constants_table(proj.map),
        ]
    if proj.map.palettes:
        lines += ["## Palettes (emulator CRAM captures, not build inputs)", ""]
        for name, meta in proj.map.palettes.items():
            lines.append(f"- `{name}` — `{meta.get('path')}` — {meta.get('source', '')}")
        lines.append("")
    return "\n".join(lines)


def cmd_asm(args) -> int:
    from . import disasm

    proj = _proj(args)
    rom = _open_image(args, proj)
    out_dir = proj.paths.asset("code/asm")
    n = 0
    for seg in proj.map.by_type("code"):
        body = disasm.listing(bytes(rom.data), seg.start, seg.end, seg.name)
        write_text(out_dir / f"{seg.name}.s", body)
        n += 1
    print(f"wrote {n} listing(s) to {out_dir.relative_to(proj.root)}")
    return 0


# ---------------------------------------------------------------- inspection


def cmd_info(args) -> int:
    print(_open_image(args, _try_proj(args), strict=False).summary())
    return 0


def cmd_diff(args) -> int:
    with open(args.a, "rb") as f:
        a = f.read()
    with open(args.b, "rb") as f:
        b = f.read()
    print(diff_report(a, b, limit=args.limit))
    return 0


def cmd_patch(args) -> int:
    a = Path(args.orig).read_bytes()
    if args.patchcmd == "make":
        data = make_ips(a, Path(args.patched).read_bytes())
        payload = len(data) - 8
        what = "no changes" if payload == 0 else f"{payload} B of records"
        print(f"{write_bytes(Path(args.out), data)}  ({len(data)} bytes, {what})")
    else:
        out = apply_ips(a, Path(args.ips).read_bytes())
        print(f"{write_bytes(Path(args.out), out)}  ({len(out)} bytes)")
    return 0


def cmd_tiles(args) -> int:
    proj = _try_proj(args)
    if args.tilescmd == "import":
        raw = tiles.import_indexed(args.png) if args.indexed else tiles.import_tiles(args.png)
        write_bytes(Path(args.out), raw)
        print(f"{args.out}  ({len(raw) // 32} tiles)")
        return 0
    src = _open_image(args, proj, strict=False)
    off = _hex(args.off)
    if args.tilescmd == "ascii":
        print(tiles.render_ascii(src.data, off, args.count, args.cols))
        return 0
    pal_dir = proj.paths.asset("palettes") if proj else None
    pal = palette.resolve_ref(args.palette, pal_dir, src.data)
    tiles.dump_tiles(
        src.data,
        off,
        args.count,
        args.out,
        palette=pal,
        cols=args.cols,
        scale=args.scale,
        grid=args.grid,
    )
    print(args.out)
    return 0


def cmd_pals(args) -> int:
    rom = _open_image(args, _try_proj(args), strict=False)
    found = palette.find_palettes(rom.data)
    print(f"palette-shaped blocks: {len(found)} (heuristic; expect false positives)")
    for o in found[: args.limit]:
        cols = palette.pal_decode(rom.data, o)
        print(f"  {o:06X}  " + " ".join("%02X%02X%02X" % c for c in cols[:8]))
    return 0


def cmd_nemesis(args) -> int:
    if args.nemcmd == "pack":
        with open(args.raw, "rb") as f:
            raw = f.read()
        mode = {"auto": None, "on": True, "off": False}[args.xor]
        blob = nemesis.compress(raw, mode, slack=not args.no_slack)
        write_bytes(Path(args.out), blob)
        meta = nemesis.info(blob, 0)
        print(
            f"{meta['tiles']} tiles, XOR={meta['xor']} -> {len(blob)} bytes "
            f"({100.0 * len(blob) / len(raw):.1f}% of {len(raw)} raw)"
        )
        return 0
    src = _open_image(args, _try_proj(args), strict=False)
    off = _hex(args.offset)
    if args.nemcmd == "size":
        meta = nemesis.info(src.data, off)
        size = nemesis.block_size(src.data, off)
        print(f"block {off:06X}: {meta['tiles']} tiles, XOR={meta['xor']}, {size} bytes")
        return 0
    raw = nemesis.decompress(src.data, off)
    meta = nemesis.info(src.data, off)
    print(
        f"block {off:06X}: {meta['tiles']} tiles, XOR={meta['xor']}, {len(raw)} bytes decoded",
        file=sys.stderr,
    )
    if args.out:
        write_bytes(Path(args.out), raw)
        print(args.out)
    return 0


def _text_units(proj: pipeline.Project) -> list[tuple]:
    """Every strings file the build reads: ``(segment, path, prose spans or None)``.

    ``text`` segments may restrict real prose with ``prose: [[start, end], ...]``
    (the rest of a scanned region is data that happens to be printable); strings
    embedded in code, and those a patch relocates or carries, are prose throughout.
    """
    units = []
    for seg in proj.map.segments:
        if seg.type == "text":
            prose = seg.get("prose")
            spans = [tuple(p) for p in prose] if prose is not None else None
            units.append((seg, proj.paths.asset(seg.path), spans))
        elif (seg.type in ("code", "data") and seg.get("strings") is not None) or (
            seg.type == "patch" and seg.get("strings_path") is not None
        ):
            units.append((seg, proj.paths.asset(seg.get("strings_path")), None))
        elif seg.type == "patch" and seg.get("patch_def") is not None:
            spec = seg.get("patch_def").get("strings")
            if spec and spec["section"] == seg.get("section"):
                units.append((seg, proj.paths.asset(spec["path"]), None))
    return units


def _prose_rows(seg, path: Path, spans) -> list:
    rows = text.parse_strings_file(str(path))
    if seg.type == "text":
        rows = [r for r in rows if spans is not None and text.in_spans(r[0], r[1], spans)]
    return rows


def cmd_text(args) -> int:
    proj = _proj(args)
    units = _text_units(proj)
    if args.textcmd == "export":
        rom = _open_image(args, proj, strict=False)
        pipeline.extract_all(proj, rom, {seg.name for seg, _p, _s in units})
        return 0
    if args.textcmd == "lint":
        return _text_lint(units)
    if args.textcmd == "preview":
        return _text_preview(args, proj, units)
    # verify
    rom = _open_image(args, proj, strict=False)
    rc = 0
    for seg, path, _spans in units:
        if not path.exists():
            print(f"  {seg.name}: missing {path.relative_to(proj.paths.assets)}")
            rc = 1
            continue
        rows = text.parse_strings_file(str(path))
        problems = text.check(rows, seg.start, seg.end)
        changed = text.count_changed(rows, rom.data)
        print(
            f"  {seg.name:14s} {len(rows):4d} strings, {changed:3d} changed vs base ROM, "
            f"{len(problems)} problem(s)"
        )
        for p in problems:
            print("      " + p)
            rc = 1
    return rc


def _text_lint(units) -> int:
    total = 0
    for seg, path, spans in units:
        if seg.type == "text" and spans is None:
            continue  # no prose declared: the region is not checked
        allow = {int(k): list(v) for k, v in (seg.get("lint_allow") or {}).items()}
        rows = _prose_rows(seg, path, spans)
        findings = text.lint(rows, allow)
        print(f"  {seg.name:14s} {len(rows):4d} prose strings, {len(findings)} finding(s)")
        for f in findings:
            print("      " + f)
        total += len(findings)
    if not total:
        return 0
    for rule, (_pattern, why) in text.LINT_RULES.items():
        print(f"  rule {rule}: {why}")
    return 1


def _text_preview(args, proj: pipeline.Project, units) -> int:
    """Render prose records with the current font art: one PNG per strings file."""
    seg = next((s for s in proj.map.by_type("nemesis") if s.get("format") == "font_art"), None)
    if seg is None:
        return _fail("rom_map.yml has no nemesis segment with format: font_art")
    h: FontArtHandler = handler_for(seg)  # type: ignore[assignment]
    raw = h.raw_from_art(seg, proj.paths)
    first = seg.get("first_byte", font.DEFAULT_FIRST_BYTE)
    pal = [(0, 0, 0)] * 16
    pal[seg.get("bg", font.DEFAULT_BG)] = (255, 255, 255)
    pal[seg.get("ink", font.DEFAULT_INK)] = (0, 0, 0)
    base = _open_image(args, proj, strict=False) if args.changed else None
    out_dir = Path(args.out)
    written = []
    for tseg, path, spans in units:
        if tseg.type == "text" and spans is None:
            continue
        rows = _prose_rows(tseg, path, spans)
        if base is not None:
            rows = [r for r in rows if text.count_changed([r], base.data)]
        if not rows:
            continue
        width = max(ln for _o, ln, _t in rows)
        blank = raw[0:32]  # the space glyph
        sheet = b""
        for _off, _ln, txt in rows:
            enc = table.encode(txt).ljust(width, b"\x20")
            for b in enc:
                i = b - first
                sheet += raw[i * 32 : i * 32 + 32] if 0 <= i < len(raw) // 32 else blank
        dest = out_dir / f"{tseg.name}.png"
        tiles.dump_tiles(
            sheet, 0, len(sheet) // 32, str(dest), palette=pal, cols=width, scale=args.scale
        )
        written.append(dest)
        print(f"{dest}  ({len(rows)} strings)")
    if not written:
        print("nothing to render")
    return 0


def cmd_font(args) -> int:
    proj = _proj(args)
    seg = next((s for s in proj.map.by_type("nemesis") if s.get("format") == "font_art"), None)
    if seg is None:
        return _fail("rom_map.yml has no nemesis segment with format: font_art")
    h: FontArtHandler = handler_for(seg)  # type: ignore[assignment]
    first = seg.get("first_byte", font.DEFAULT_FIRST_BYTE)
    bg = seg.get("bg", font.DEFAULT_BG)
    ink = seg.get("ink", font.DEFAULT_INK)
    if args.fontcmd == "export-art":
        rom = _open_image(args, proj, strict=False)
        files = h.extract(rom, seg, proj.paths)
        print("\n".join(str(f.relative_to(proj.root)) for f in files))
        return 0
    raw = h.raw_from_art(seg, proj.paths)
    if args.fontcmd == "export-png":
        pal = [(0, 0, 0)] * 16
        pal[bg] = (255, 255, 255)
        pal[ink] = (0, 0, 0)
        tiles.dump_tiles(raw, 0, len(raw) // 32, args.out, palette=pal, cols=16, scale=args.scale)
        print(args.out)
        return 0
    # info
    rom = _open_image(args, proj, strict=False)
    in_rom = nemesis.block_size(rom.data, seg.start)
    repack = len(nemesis.compress(raw, slack=False))
    free = font.free_slots(raw, first, bg)
    print(f"font: block {seg.start:06X}, {len(raw) // 32} tiles, slot {seg.size} bytes")
    print(f"  in base ROM       : {in_rom} bytes")
    print(f"  repacked from art : {repack} bytes (margin {seg.size - repack})")
    print(f"  free slots ({len(free)}): " + " ".join("0x%02X" % b for b in free))
    return 0


def cmd_balance(args) -> int:
    from . import constants

    proj = _proj(args)
    seg = proj.map.by_name("hp_table")
    path = proj.paths.asset(seg.path)
    values = balance.read_hp(path)
    cpath = proj.paths.asset(proj.map.constants_path) if proj.map.constants else None
    if args.balcmd == "show":
        print(f"HP table ({seg.path}, ROM {seg.start:06X}):")
        for k, v in values.items():
            print(f"  {k:10s} {v:3d} (0x{v:02X})")
        if cpath is not None:
            current = constants.read_values(cpath)
            print(f"Constants ({proj.map.constants_path}):")
            for c in proj.map.constants.values():
                where = ", ".join(f"{s.at:06X}" for s in c.sites)
                most = f", max {c.limit}" if "max" in c.attrs else ""
                print(f"  {c.name:10s} {current.get(c.name, '?'):>3} ({c.format} at {where}{most})")
        return 0
    if args.balcmd == "set":
        if cpath is None:
            return _fail("rom_map.yml declares no constants")
        try:
            old, warnings = balance.set_constant(proj.map, cpath, args.name, int(args.value, 0))
        except ValueError as exc:
            return _fail(str(exc))
        for w in warnings:
            print("  warning: " + w, file=sys.stderr)
        print(
            f"{args.name}: {old} -> {int(args.value, 0)}  "
            f"(written to {proj.map.constants_path}; run `ga3 build`)"
        )
        return 0
    new = [int(v, 0) for v in args.values]
    if len(new) != len(values):
        return _fail(f"expected {len(values)} values")
    for w in balance.validate_hp(new, seg.get("max_hud")):
        print("  warning: " + w, file=sys.stderr)
    balance.write_hp(path, dict(zip(values.keys(), new, strict=True)))
    print(f"HP: {list(values.values())} -> {new}  (written to {seg.path}; run `ga3 build`)")
    return 0


def cmd_disasm(args) -> int:
    from . import disasm

    src = _open_image(args, _try_proj(args), strict=False)
    start = max(0, _hex(args.addr) - args.back)
    print(disasm.fmt(disasm.disasm(bytes(src.data), start, args.count)))
    return 0


def cmd_emu(args) -> int:
    import subprocess

    proj = _proj(args)
    exe = proj.root / "build" / "emu" / "headless_gpgx"
    if not exe.exists():
        return _fail(f"{exe.relative_to(proj.root)} not built; run `make emu`")
    rom = Path(args.rom) if args.rom else proj.build_rom
    if not rom.exists():
        return _fail(f"{rom} not found; run `ga3 build` first")
    cmd = [str(exe), "--rom", str(rom), "--script", args.script, *args.extra]
    return subprocess.call(cmd, cwd=proj.root)


def cmd_lag(args) -> int:
    from . import lag

    proj = _proj(args)
    exe = proj.root / "build" / "emu" / "headless_gpgx"
    if not exe.exists():
        return _fail(f"{exe.relative_to(proj.root)} not built; run `make emu`")
    rom = Path(args.rom) if args.rom else proj.build_rom
    if not rom.exists():
        return _fail(f"{rom} not found; run `ga3 build` first")
    seg = next((s for s in proj.map.segments if s.get("frame_wait") is not None), None)
    if seg is None:
        return _fail("rom_map.yml declares no frame_wait")
    for pct in args.overclock:
        report = lag.measure(
            exe, rom, Path(args.scene), seg.get("frame_wait"), overclock=pct, cwd=proj.root
        )
        print(f"{pct:3d}%  {report.summary()}")
        if args.verbose:
            for after, gap in report.gaps:
                print(f"       after frame {after}: {gap} frames")
    return 0


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="ga3",
        description="Golden Axe III (Mega Drive) ROM-hacking toolkit: take the base ROM apart "
        "into assets/, rebuild it byte for byte, prove it in the headless emulator.",
        epilog="Pipeline: extract -> edit assets/ -> build -> verify. "
        "Offsets live in rom_map.yml; docs in docs/. `ga3 COMMAND --help` for details.",
    )
    ap.add_argument("--version", action="version", version=f"ga3 {__version__}")
    ap.add_argument("--root", help="project root (default: nearest directory with rom_map.yml)")
    ap.add_argument("--rom", help="ROM image to read instead of baserom/ga3.bin")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND", title="commands")

    p = sub.add_parser("extract", help="take the base ROM apart into assets/")
    p.add_argument("--only", nargs="+", metavar="SEGMENT", help="segment names to extract")
    p.add_argument(
        "--png", action="store_true", help="also render Nemesis previews into build/preview/"
    )
    p.add_argument(
        "--rom", default=argparse.SUPPRESS, help="extract from this image instead of the base ROM"
    )
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("build", help="rebuild build/ga3.bin and build/ga3.ips from assets/")
    p.add_argument("-o", "--out", help="output ROM path (default build/ga3.bin)")
    p.add_argument("--no-ips", action="store_true", help="do not write the IPS patch")
    p.add_argument(
        "--rom",
        default=argparse.SUPPRESS,
        help="build on top of this image instead of the base ROM",
    )
    p.set_defaults(func=cmd_build)

    p = sub.add_parser(
        "verify",
        help="check base ROM and build against roms.sha1; check the IPS reproduces the build",
    )
    p.add_argument("--update", action="store_true", help="record the current hashes")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("map", help="rom_map.yml coverage, consistency checks, Markdown table")
    p.add_argument("--check", action="store_true", help="validate the map against the base ROM")
    p.add_argument(
        "--check-assets",
        action="store_true",
        help="only check that every committed asset file exists (needs no ROM)",
    )
    p.add_argument("--markdown", action="store_true", help="print the segment table as Markdown")
    p.add_argument("--list", action="store_true", help="list every segment")
    p.set_defaults(func=cmd_map)

    p = sub.add_parser(
        "assets", help="refresh derived files (encoding.tbl, font.nem, docs/rom_map.md)"
    )
    p.add_argument(
        "assetscmd", nargs="?", default="refresh", choices=["refresh"], help="the action"
    )
    p.set_defaults(func=cmd_assets)

    p = sub.add_parser(
        "asm", help="write Capstone listings for every code segment ([disasm] extra)"
    )
    p.set_defaults(func=cmd_asm)

    p = sub.add_parser("info", help="header, checksum and sha1 of a ROM")
    p.add_argument("file", nargs="?", help="ROM to describe (default: --rom, then the base ROM)")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("diff", help="compare two images")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--limit", type=int, default=24)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("patch", help="make or apply IPS patches")
    s = p.add_subparsers(dest="patchcmd", required=True)
    q = s.add_parser("make")
    q.add_argument("orig")
    q.add_argument("patched")
    q.add_argument("-o", "--out", required=True)
    q = s.add_parser("apply")
    q.add_argument("orig")
    q.add_argument("ips")
    q.add_argument("-o", "--out", required=True)
    p.set_defaults(func=cmd_patch)

    p = sub.add_parser("tiles", help="render, dump or import 4bpp tiles")
    s = p.add_subparsers(dest="tilescmd", required=True)
    for name in ("render", "ascii"):
        q = s.add_parser(name)
        q.add_argument("off", help="offset, hex")
        q.add_argument("count", type=int)
        q.add_argument("--file", help="read from this file instead of the base ROM")
        q.add_argument("--cols", type=int, default=16)
        if name == "render":
            q.add_argument("-o", "--out", default="build/preview/tiles.png")
            q.add_argument(
                "--palette", help="NAME[/INDEX] from assets/palettes or a hex ROM offset"
            )
            q.add_argument("--scale", type=int, default=3)
            q.add_argument("--grid", action="store_true")
    q = s.add_parser("import")
    q.add_argument("png")
    q.add_argument("-o", "--out", required=True)
    q.add_argument("--indexed", action="store_true", help="read palette indices (mode P PNG)")
    p.set_defaults(func=cmd_tiles)

    p = sub.add_parser("pals", help="heuristic palette search in the base ROM")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(func=cmd_pals)

    p = sub.add_parser("nemesis", help="Nemesis codec")
    s = p.add_subparsers(dest="nemcmd", required=True)
    q = s.add_parser("unpack")
    q.add_argument("offset", help="hex")
    q.add_argument("-o", "--out")
    q.add_argument("--file")
    q = s.add_parser("pack")
    q.add_argument("raw")
    q.add_argument("-o", "--out", required=True)
    q.add_argument("--xor", choices=("auto", "on", "off"), default="auto")
    q.add_argument("--no-slack", action="store_true", help="omit the two trailing spare bytes")
    q = s.add_parser("size")
    q.add_argument("offset")
    q.add_argument("--file")
    p.set_defaults(func=cmd_nemesis)

    p = sub.add_parser("text", help="export or verify text assets")
    s = p.add_subparsers(dest="textcmd", required=True)
    s.add_parser("export", help="extract every strings file from the ROM (overwrites edits)")
    s.add_parser("verify", help="check every strings file against its segment")
    s.add_parser("lint", help="mechanical checks of the prose (no ROM needed)")
    q = s.add_parser("preview", help="render the prose with the current font art")
    q.add_argument("-o", "--out", default="build/preview/text")
    q.add_argument("--scale", type=int, default=3)
    q.add_argument("--changed", action="store_true", help="only strings that differ from the ROM")
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("font", help="font block: info, export-art, export-png")
    s = p.add_subparsers(dest="fontcmd", required=True)
    s.add_parser("info")
    s.add_parser("export-art")
    q = s.add_parser("export-png")
    q.add_argument("-o", "--out", default="build/preview/font.png")
    q.add_argument("--scale", type=int, default=4)
    p.set_defaults(func=cmd_font)

    p = sub.add_parser("balance", help="gameplay tables by name")
    s = p.add_subparsers(dest="balcmd", required=True)
    s.add_parser("show")
    q = s.add_parser("set-hp")
    q.add_argument("values", nargs="+")
    q = s.add_parser("set", help="one gameplay constant (rom_map.yml constants:), e.g. lives 5")
    q.add_argument("name")
    q.add_argument("value")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("disasm", help="m68000 disassembly window (needs the [disasm] extra)")
    p.add_argument("addr", help="hex")
    p.add_argument("-n", "--count", type=int, default=40)
    p.add_argument("--back", type=int, default=0, help="start this many bytes earlier")
    p.add_argument("--file")
    p.set_defaults(func=cmd_disasm)

    ramsearch.add_cli(sub)

    p = sub.add_parser(
        "lag", help="count frames the game's main loop missed while a scene runs (emulator)"
    )
    p.add_argument("scene", help="emulator script, e.g. emu/scenes/stage1_fight.txt")
    p.add_argument(
        "--overclock",
        type=int,
        nargs="+",
        default=[100],
        metavar="PCT",
        help="68000 clock in percent; several values compare them (100..400)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="list every gap")
    p.set_defaults(func=cmd_lag)

    p = sub.add_parser("emu", help="run a headless emulator script against the build")
    p.add_argument("script")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="extra headless_gpgx arguments")
    p.set_defaults(func=cmd_emu)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, ValueError, LookupError, OSError) as exc:
        # PipelineError/BuildError are RuntimeErrors, RomMapError a ValueError,
        # a bad segment name a LookupError, a missing file an OSError.
        if os.environ.get("GA3_DEBUG"):
            raise
        return _fail(str(exc) or type(exc).__name__)
