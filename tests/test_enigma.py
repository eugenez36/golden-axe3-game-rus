"""Enigma tilemaps: the game's three title maps, and the encoder against the decoder."""

from __future__ import annotations

import random

import pytest

from ga3 import enigma

# map, the base attribute its caller passes, words, size in bytes (with the even pad)
GAME_MAPS = [
    (0x0EB490, 0xA080, 38 * 6, 140),
    (0x0EB5E8, 0x00F8, 32 * 28, 408),
    (0x0EB808, 0x4001, 40 * 28, 582),
]


@pytest.mark.rom
@pytest.mark.parametrize(("offset", "base", "words", "size"), GAME_MAPS)
def test_game_maps_decode_and_reencode(baserom, offset, base, words, size):
    data = bytes(baserom.data)
    decoded, used = enigma.decompress(data, offset, base)
    assert (len(decoded), used) == (words, size)
    blob = enigma.compress(decoded, base)
    assert enigma.decompress(blob, 0, base)[0] == decoded
    assert len(blob) % 2 == 0


@pytest.mark.parametrize("seed", range(6))
def test_roundtrip_random_maps(seed):
    rng = random.Random(seed)
    pool = [rng.randrange(0x800) | rng.choice([0, enigma.FLAG_V, enigma.FLAG_H]) for _ in range(12)]
    words: list[int] = []
    while len(words) < 400:
        kind = rng.randrange(4)
        start = rng.choice(pool)
        n = rng.randrange(1, 40)
        step = {0: 0, 1: 1, 2: -1}.get(kind, 0)
        words += [(start + step * k) & 0x1FFF for k in range(n)]
        if kind == 3:
            words += [rng.choice(pool) for _ in range(n)]
    words = [w & (enigma.FLAG_V | enigma.FLAG_H | enigma.TILE_MASK) for w in words[:400]]
    base = 0x6000 + rng.randrange(0x100)
    attrs = [base + w for w in words]
    assert enigma.decompress(enigma.compress(attrs, base), 0, base)[0] == attrs


def test_runs_pack_small():
    words = list(range(100, 164)) + [7] * 64
    blob = enigma.compress(words)
    assert enigma.decompress(blob, 0)[0] == words
    assert len(blob) < 20


def test_palette_bits_must_come_from_the_base():
    with pytest.raises(ValueError, match="priority/palette"):
        enigma.compress([0x2001], base=0)
