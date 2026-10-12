"""The version is X.YY.ZZZ, zero-padded everywhere (0.37.400, 0.38.001)."""

from __future__ import annotations

import re
import tomllib

import ga3
from ga3 import patches

from .conftest import ROOT

FORMAT = re.compile(r"\d\.\d{2}\.\d{3}")


def test_version_is_x_yy_zzz():
    assert FORMAT.fullmatch(ga3.__version__), ga3.__version__


def test_pyproject_carries_the_same_string():
    with open(ROOT / "pyproject.toml", "rb") as f:
        assert tomllib.load(f)["project"]["version"] == ga3.__version__


def test_main_menu_shows_it_with_the_zeros():
    assert patches.version_text() == f"V {ga3.__version__}"
    assert patches.version_text("0.38.001") == "V 0.38.001"
