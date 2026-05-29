"""Unit tests for pure helpers (no DB required)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.errors import ValidationError
from app.services import _query
from app.services.geo_service import _region


def test_validate_scenario_ok():
    assert _query.validate_scenario("actual") == "actual"
    assert _query.validate_scenario("depot") == "depot"


def test_validate_scenario_rejects_unknown():
    with pytest.raises(ValidationError):
        _query.validate_scenario("bogus")


def test_validate_role():
    assert _query.validate_role("bkv") == "bkv"
    with pytest.raises(ValidationError):
        _query.validate_role("driver")


def test_validate_deg_cost_bounds():
    assert _query.validate_deg_cost(50) == 50.0
    with pytest.raises(ValidationError):
        _query.validate_deg_cost(-1)
    with pytest.raises(ValidationError):
        _query.validate_deg_cost(999)


def test_resolve_range_defaults_and_clamp():
    start, end = _query.resolve_range(None, None)
    assert start == pd.Timestamp("2024-01-01 00:00:00")
    assert end == pd.Timestamp("2024-07-01 00:00:00")
    # out-of-window request clamps to the window
    s, e = _query.resolve_range("2020-01-01T00:00:00", "2030-01-01T00:00:00")
    assert s == pd.Timestamp("2024-01-01 00:00:00")
    assert e == pd.Timestamp("2024-07-01 00:00:00")


def test_resolve_range_rejects_inverted():
    with pytest.raises(ValidationError):
        _query.resolve_range("2024-03-01T00:00:00", "2024-02-01T00:00:00")


@pytest.mark.parametrize(
    "pc,expected",
    [
        (60313, "Frankfurt core"),
        (61118, "Frankfurt core"),
        (63179, "Offenbach/E"),
        (65197, "Wiesbaden/W"),
        (12345, "Other"),
    ],
)
def test_region_mapping(pc, expected):
    assert _region(pc) == expected
