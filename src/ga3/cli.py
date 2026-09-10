"""``ga3`` command line: one entry point, one subcommand per job.

Every command reads the base ROM from ``baserom/ga3.bin`` (override with
``--rom``) and never writes a ROM anywhere except ``build/``.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from pathlib import Path

from . import __version__, font, nemesis, palette, ramsearch, rom_map, table, text, tiles
from . import balance as balmod
from . import pipeline as pl
from .assets import handler_for
from .assets.base import write_text
from .assets.nemesis_asset import FontArtHandler
from .rom import Rom, apply_ips, diff_report, make_ips


def _hex(s: str) -> int:
    """Hex with or without a 0x prefix (every ROM address on the CLI is hex)."""
    return int(s, 16)


def _proj(args) -> pl.Project:
    return pl.open_project(getattr(args, "root", None))


def _rom(args, proj: pl.Project, strict: bool = True) -> Rom:
    return pl.load_baserom(proj, getattr(args, "rom", None), strict=strict)


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------- pipeline


def cmd_extract(args) -> int:
    proj = _proj(args)
    rom = _rom(args, proj, strict=not args.rom)
    only = set(args.only) if args.only else None
    print(f"extracting from {rom.path} (sha1 {rom.sha1()[:12]}...) into {proj.paths.assets}")
    files = pl.extract_all(proj, rom, only)
    print(f"{len(files)} file(s) written")
    if args.png:
        _previews(proj, rom)
    return 0


def _previews(proj: pl.Project, rom: Rom) -> None:
    for seg in proj.map.by_type("nemesis"):
        raw = nemesis.decompress(rom.data, seg.start)
        out = proj.paths.preview(Path(seg.path).with_suffix(".png").name)
        os.makedirs(out.parent, exist_ok=True)
        tiles.dump_tiles(raw, 0, len(raw) // 32, str(out), cols=16, scale=2)
        print(f"  preview {out.relative_to(proj.root)}")


def cmd_build(args) -> int:
    proj = _proj(args)
    base = _rom(args, proj)
    out = Path(args.out).resolve() if args.out else None
    pl.build(proj, base, out=out, ips=not args.no_ips)
    return 0


def cmd_verify(args) -> int:
    proj = _proj(args)
    ok = pl.verify(proj, update=args.update)
    print("verify: OK" if ok else "verify: FAILED")
    return 0 if ok else 1


def cmd_map(args) -> int:
    proj = _proj(args)
    if args.markdown:
        print(rom_map.markdown_table(proj.map), end="")
        return 0
    if args.check:
        rom = _rom(args, proj)
        problems = pl.check_map(proj, rom)
        for p in problems:
            print("  " + p)
        print(f"map check: {'OK' if not problems else str(len(problems)) + ' problem(s)'}")
        return 0 if not problems else 1
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


def _rom_map_doc(proj: pl.Project) -> str:
    cov = proj.map.coverage()
    total = proj.map.size
    info = proj.map.rom
    lines = [
        "# ROM map",
        "",
        "Generated from `rom_map.yml` by `ga3 assets refresh`. Do not edit by hand.",
        "",
        f"Image: **{info.get('title')}**, {total} bytes, sha1 `{info.get('sha1')}`,",
        f"header checksum `{info.get('header_checksum'):04X}`, "
        f"entry point `{info.get('entry_point'):06X}`.",
        "",
        "## Coverage",
        "",
        "| Type | Bytes | Share |",
        "|---|---|---|",
    ]
    for t, n in sorted(cov.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {t} | {n} | {100.0 * n / total:.1f}% |")
    lines += ["", "## Segments", "", rom_map.markdown_table(proj.map)]
    if proj.map.palettes:
        lines += ["## Palettes (emulator CRAM captures, not build inputs)", ""]
        for name, meta in proj.map.palettes.items():
            lines.append(f"- `{name}` — `{meta.get('path')}` — {meta.get('source', '')}")
        lines.append("")
    return "\n".join(lines)


def cmd_asm(args) -> int:
    from . import disasm

    proj = _proj(args)
    rom = _rom(args, proj)
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
    if args.rom:
        print(Rom.load(args.rom).summary())
        return 0
    proj = _proj(args)
    print(_rom(args, proj, strict=False).summary())
    return 0


def cmd_diff(args) -> int:
    with open(args.a, "rb") as f:
        a = f.read()
    with open(args.b, "rb") as f:
        b = f.read()
    print(diff_report(a, b, limit=args.limit))
    return 0


def cmd_patch(args) -> int:
    if args.patchcmd == "make":
        with open(args.orig, "rb") as f:
            a = f.read()
        with open(args.patched, "rb") as f:
            b = f.read()
        data = make_ips(a, b)
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(data)
        print(f"{args.out}  ({len(data)} bytes)")
    else:
        with open(args.orig, "rb") as f:
            a = f.read()
        with open(args.ips, "rb") as f:
            p = f.read()
        out = apply_ips(a, p)
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(out)
        print(f"{args.out}  ({len(out)} bytes)")
    return 0


def _palette_ref(proj: pl.Project | None, ref: str | None, rom: Rom | None):
    if not ref:
        return None
    if ref.lower().startswith("0x") or all(c in "0123456789abcdefABCDEF" for c in ref):
        if rom is None:
            raise SystemExit("a ROM is needed to read a palette by offset")
        return palette.pal_decode(rom.data, int(ref, 16))
    name, _, idx = ref.partition("/")
    if proj is None:
        raise SystemExit("palette names need a project (rom_map.yml)")
    pals = palette.load_pal(str(proj.paths.asset(f"palettes/{name}.pal")))
    return pals[int(idx or 0)]


def cmd_tiles(args) -> int:
    proj = None
    with contextlib.suppress(pl.PipelineError):
        proj = _proj(args)
    if args.tilescmd == "import":
        raw = tiles.import_indexed(args.png) if args.indexed else tiles.import_tiles(args.png)
        with open(args.out, "wb") as f:
            f.write(raw)
        print(f"{args.out}  ({len(raw) // 32} tiles)")
        return 0
    src = Rom.load(args.file) if args.file else _rom(args, proj, strict=False)
    off = _hex(args.off)
    if args.tilescmd == "ascii":
        print(tiles.render_ascii(src.data, off, args.count, args.cols))
        return 0
    pal = _palette_ref(proj, args.palette, src)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
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
    proj = _proj(args)
    rom = _rom(args, proj, strict=False)
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
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(blob)
        meta = nemesis.info(blob, 0)
        print(
            f"{meta['tiles']} tiles, XOR={meta['xor']} -> {len(blob)} bytes "
            f"({100.0 * len(blob) / len(raw):.1f}% of {len(raw)} raw)"
        )
        return 0
    src = Rom.load(args.file) if args.file else _rom(args, _proj(args), strict=False)
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
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(raw)
        print(args.out)
    return 0


def cmd_text(args) -> int:
    proj = _proj(args)
    if args.textcmd == "export":
        rom = _rom(args, proj, strict=False)
        pl.extract_all(proj, rom, {s.name for s in proj.map.by_type("text")})
        return 0
    # verify
    rom = _rom(args, proj, strict=False)
    rc = 0
    for seg in proj.map.by_type("text"):
        path = proj.paths.asset(seg.path)
        if not path.exists():
            print(f"  {seg.name}: missing {seg.path}")
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
        rom = _rom(args, proj, strict=False)
        files = h.extract(rom, seg, proj.paths)
        print("\n".join(str(f.relative_to(proj.root)) for f in files))
        return 0
    raw = h.raw_from_art(seg, proj.paths)
    if args.fontcmd == "export-png":
        pal = [(0, 0, 0)] * 16
        pal[bg] = (255, 255, 255)
        pal[ink] = (0, 0, 0)
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        tiles.dump_tiles(raw, 0, len(raw) // 32, args.out, palette=pal, cols=16, scale=args.scale)
        print(args.out)
        return 0
    # info
    rom = _rom(args, proj, strict=False)
    in_rom = nemesis.block_size(rom.data, seg.start)
    repack = len(nemesis.compress(raw, slack=False))
    free = font.free_slots(raw, first, bg)
    print(f"font: block {seg.start:06X}, {len(raw) // 32} tiles, slot {seg.size} bytes")
    print(f"  in base ROM       : {in_rom} bytes")
    print(f"  repacked from art : {repack} bytes (margin {seg.size - repack})")
    print(f"  free slots ({len(free)}): " + " ".join("0x%02X" % b for b in free))
    return 0


def cmd_balance(args) -> int:
    proj = _proj(args)
    seg = proj.map.by_name("hp_table")
    path = proj.paths.asset(seg.path)
    values = balmod.read_hp(path)
    if args.balcmd == "show":
        print(f"HP table ({seg.path}, ROM {seg.start:06X}):")
        for k, v in values.items():
            print(f"  {k:10s} {v:3d} (0x{v:02X})")
        return 0
    new = [int(v, 0) for v in args.values]
    if len(new) != len(values):
        return _fail(f"expected {len(values)} values")
    for w in balmod.validate_hp(new):
        print("  warning: " + w, file=sys.stderr)
    balmod.write_hp(path, dict(zip(values.keys(), new, strict=True)))
    print(f"HP: {list(values.values())} -> {new}  (written to {seg.path}; run `ga3 build`)")
    return 0


def cmd_disasm(args) -> int:
    from . import disasm

    src = Rom.load(args.file) if args.file else _rom(args, _proj(args), strict=False)
    start = _hex(args.addr) - args.back
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


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ga3", description="Golden Axe III ROM-hacking toolkit")
    ap.add_argument("--version", action="version", version=f"ga3 {__version__}")
    ap.add_argument("--root", help="project root (default: nearest directory with rom_map.yml)")
    ap.add_argument("--rom", help="ROM image to read instead of baserom/ga3.bin")
    sub = ap.add_subparsers(dest="cmd", required=True)

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
    p.add_argument("--no-ips", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("verify", help="check sha1 of base ROM and build against roms.sha1")
    p.add_argument("--update", action="store_true", help="record the current hashes")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("map", help="rom_map.yml coverage, consistency checks, Markdown table")
    p.add_argument("--check", action="store_true", help="validate the map against the base ROM")
    p.add_argument("--markdown", action="store_true")
    p.add_argument("--list", action="store_true", help="list every segment")
    p.set_defaults(func=cmd_map)

    p = sub.add_parser(
        "assets", help="refresh derived files (encoding.tbl, font.nem, docs/rom_map.md)"
    )
    p.add_argument("assetscmd", nargs="?", default="refresh", choices=["refresh"])
    p.set_defaults(func=cmd_assets)

    p = sub.add_parser("asm", help="write Capstone listings for every code segment")
    p.set_defaults(func=cmd_asm)

    p = sub.add_parser("info", help="header, checksum and sha1 of a ROM")
    p.add_argument("rom", nargs="?", help="ROM path (default: base ROM)")
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
    s.add_parser("export")
    s.add_parser("verify")
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
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("disasm", help="m68000 disassembly window (needs the [disasm] extra)")
    p.add_argument("addr", help="hex")
    p.add_argument("-n", "--count", type=int, default=40)
    p.add_argument("--back", type=int, default=0, help="start this many bytes earlier")
    p.add_argument("--file")
    p.set_defaults(func=cmd_disasm)

    ramsearch.add_cli(sub)

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
    except pl.PipelineError as exc:
        return _fail(str(exc))
    except (ValueError, FileNotFoundError) as exc:
        return _fail(str(exc))
