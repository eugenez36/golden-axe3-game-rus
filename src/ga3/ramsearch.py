"""Find game variables in Work RAM from a series of dumps -- cheat-engine style.

Run the game in the headless emulator, periodically saving a Work RAM dump and
a screenshot; measure the observed quantity on the screenshots (bar length,
number of lives) and look for RAM bytes that correlate with it. That is how
the player's HP was found: FFC8E6 correlates with the health bar at r = 1.0000.

IMPORTANT: Genesis Plus GX stores Work RAM byte-swapped (``READ_BYTE`` in
macros.h is ``(BASE)[(ADDR)^1]`` on little-endian hosts). Offset ``O`` in a
dump therefore corresponds to 68000 address ``0xFF0000 | (O ^ 1)``; this
module compensates.

    # 1. collect dumps
    ga3 emu emu/explore/hp.txt
    # 2. bytes correlating with a series of values, one per dump
    ga3 ramsearch corr 'build/dumps/hp/w*.bin' 51,51,50,48,47
    # 3. bytes always equal to a value
    ga3 ramsearch value 'build/dumps/hp/w*.bin' 2
    # 4. bytes that only ever decrease
    ga3 ramsearch decreasing 'build/dumps/hp/w*.bin'
"""

from __future__ import annotations

import argparse
import glob


def load(pattern: str) -> list[bytes]:
    files = sorted(glob.glob(pattern))
    if not files:
        raise ValueError(f"no dumps match {pattern!r}")
    dumps = []
    for f in files:
        with open(f, "rb") as fh:
            dumps.append(fh.read())
    sizes = {len(d) for d in dumps}
    if len(sizes) != 1:
        raise ValueError(f"dumps differ in size: {sorted(sizes)}")
    print(f"dumps: {len(dumps)}, size {len(dumps[0])} bytes")
    return dumps


def m68k_addr(offset: int) -> int:
    """Dump offset -> 68000 address (compensating for the byte swap)."""
    return 0xFF0000 | ((offset ^ 1) & 0xFFFF)


def correlate(dumps: list[bytes], series: list[float], threshold: float, min_distinct: int):
    n = len(series)
    ms = sum(series) / n
    vs = sum((x - ms) ** 2 for x in series) ** 0.5
    if vs == 0:
        raise ValueError("the value series is constant; correlation is meaningless")
    hits = []
    for off in range(len(dumps[0])):
        vals = [d[off] for d in dumps]
        if len(set(vals)) < min_distinct:
            continue
        mv = sum(vals) / n
        vv = sum((x - mv) ** 2 for x in vals) ** 0.5
        if vv == 0:
            continue
        cov = sum((vals[i] - mv) * (series[i] - ms) for i in range(n))
        r = cov / (vv * vs)
        if abs(r) >= threshold:
            hits.append((abs(r), r, off, vals))
    hits.sort(reverse=True)
    return hits


def cmd_corr(args) -> int:
    dumps = load(args.pattern)
    series = [float(x) for x in args.series.split(",")]
    if len(series) != len(dumps):
        raise ValueError(f"{len(series)} values but {len(dumps)} dumps; they must match")
    hits = correlate(dumps, series, args.threshold, args.min_distinct)
    print(f"\nbytes with |r| >= {args.threshold}: {len(hits)}")
    for _a, r, off, vals in hits[: args.limit]:
        print("  %06X  r=%+.4f  %s" % (m68k_addr(off), r, vals[:12]))
    return 0


def cmd_value(args) -> int:
    dumps = load(args.pattern)
    want = int(args.value, 0)
    hits = [off for off in range(len(dumps[0])) if all(d[off] == want for d in dumps)]
    print(f"\nbytes always equal to {want}: {len(hits)}")
    for off in hits[: args.limit]:
        print("  %06X" % m68k_addr(off))
    return 0


def cmd_decreasing(args) -> int:
    dumps = load(args.pattern)
    hits = []
    for off in range(len(dumps[0])):
        vals = [d[off] for d in dumps]
        if len(set(vals)) < args.min_distinct:
            continue
        if all(vals[i + 1] <= vals[i] for i in range(len(vals) - 1)):
            hits.append((vals[0] - vals[-1], off, vals))
    hits.sort(reverse=True)
    print(f"\nmonotonically decreasing bytes: {len(hits)}")
    for drop, off, vals in hits[: args.limit]:
        print("  %06X  drop %3d  %s" % (m68k_addr(off), drop, vals[:12]))
    return 0


def add_cli(sub) -> None:
    p = sub.add_parser(
        "ramsearch",
        help="find variables in Work RAM dumps",
        description="Cheat-engine style search over Work RAM dumps written by the headless "
        "emulator (see `ga3 emu`). Offsets are reported as 68000 addresses.",
    )
    # options live on the subcommands so that `ga3 ramsearch corr ... --limit 5` works
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--limit", type=int, default=20, help="rows to print (default 20)")
    distinct = argparse.ArgumentParser(add_help=False)
    distinct.add_argument(
        "--min-distinct",
        type=int,
        default=3,
        help="minimum distinct values for a byte to count as interesting (default 3)",
    )
    s = p.add_subparsers(dest="ramcmd", required=True, metavar="MODE")
    q = s.add_parser("corr", parents=[common, distinct], help="correlate with a series of values")
    q.add_argument("pattern", help="glob of Work RAM dumps, e.g. 'build/dumps/hp/w*.bin'")
    q.add_argument("series", help="comma-separated values, one per dump")
    q.add_argument("--threshold", type=float, default=0.9, help="minimum |r| (default 0.9)")
    q.set_defaults(func=cmd_corr)
    q = s.add_parser("value", parents=[common], help="bytes always equal to a value")
    q.add_argument("pattern", help="glob of Work RAM dumps")
    q.add_argument("value", help="the value (decimal or 0x hex)")
    q.set_defaults(func=cmd_value)
    q = s.add_parser("decreasing", parents=[common, distinct], help="bytes that only decrease")
    q.add_argument("pattern", help="glob of Work RAM dumps")
    q.set_defaults(func=cmd_decreasing)
