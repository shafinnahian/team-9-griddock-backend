"""Scenario service — F19 dwell presets (the honesty slider)."""

from __future__ import annotations

from app.core import params


def get_presets() -> dict:
    return {
        "actual": {
            "label": "Data as-is",
            "desc": "Sessions exactly as logged — a conservative availability floor.",
            "dwell_assumption": "Plugged window = logged session only.",
        },
        "depot": {
            "label": "Realistic depot",
            "desc": "Assumes depot vehicles stay plugged overnight — climbs toward benchmarks.",
            "dwell_assumption": (
                f"Each V2G-able session extended to a minimum {int(params.DEPOT_MIN_DWELL_H)}h "
                "window at ending SoC."
            ),
        },
    }
