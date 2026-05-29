"""Shared query-param helpers for routers/services (validation + window clamp)."""

from __future__ import annotations

import pandas as pd

from app.core import params
from app.errors import ValidationError

_WINDOW_START = pd.Timestamp(params.WINDOW_START)
_WINDOW_END = pd.Timestamp(params.WINDOW_END)


ROLES = ("bkv", "fleet")


def validate_role(role: str) -> str:
    if role not in ROLES:
        raise ValidationError(
            f"role must be one of: {', '.join(ROLES)}",
            [{"field": "role", "message": f"got {role!r}", "code": "INVALID_ENUM"}],
        )
    return role


def validate_scenario(scenario: str) -> str:
    if scenario not in params.SCENARIOS:
        raise ValidationError(
            f"scenario must be one of: {', '.join(params.SCENARIOS)}",
            [{"field": "scenario", "message": f"got {scenario!r}", "code": "INVALID_ENUM"}],
        )
    return scenario


def validate_deg_cost(deg_cost: float) -> float:
    if not (params.DEG_COST_MIN <= deg_cost <= params.DEG_COST_MAX):
        raise ValidationError(
            f"deg_cost must be between {params.DEG_COST_MIN} and {params.DEG_COST_MAX}",
            [{"field": "deg_cost", "message": f"got {deg_cost}", "code": "OUT_OF_RANGE"}],
        )
    return float(deg_cost)


def resolve_range(frm: str | None, to: str | None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Parse optional from/to, default to the full window, clamp, ensure from<to."""
    try:
        start = pd.Timestamp(frm) if frm else _WINDOW_START
        end = pd.Timestamp(to) if to else _WINDOW_END
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"invalid datetime: {exc}") from exc
    if start >= end:
        raise ValidationError(
            "`from` must be before `to`",
            [{"field": "from", "message": "from >= to", "code": "BAD_RANGE"}],
        )
    start = max(start, _WINDOW_START)
    end = min(end, _WINDOW_END)
    return start, end
