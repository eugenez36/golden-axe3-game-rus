"""Shared fixtures.

Tests marked ``rom`` need ``baserom/ga3.bin`` with the SHA-1 recorded in
``rom_map.yml``; they are skipped, not failed, when it is absent so that CI
runs green without the copyrighted image.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ga3 import pipeline as pl
from ga3.rom import Rom

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def pytest_collection_modifyitems(config, items):
    if _baserom_ok():
        return
    skip = pytest.mark.skip(reason="baserom/ga3.bin missing or wrong sha1")
    for item in items:
        if "rom" in item.keywords:
            item.add_marker(skip)


def _baserom_ok() -> bool:
    p = ROOT / pl.BASEROM_REL
    if not p.exists():
        return False
    proj = pl.open_project(ROOT)
    return hashlib.sha1(p.read_bytes()).hexdigest() == proj.map.rom.get("sha1")


@pytest.fixture(scope="session")
def project() -> pl.Project:
    return pl.open_project(ROOT)


@pytest.fixture(scope="session")
def baserom(project) -> Rom:
    return pl.load_baserom(project)


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES
