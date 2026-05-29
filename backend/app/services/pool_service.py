"""Pool services — F6 (timeseries) and F7 (firm-capacity profile)."""

from __future__ import annotations

import pandas as pd

from app.cache import cache
from app.core import params
from app.services._query import resolve_range, validate_scenario


def get_profile(scenario: str) -> dict:
    """F7: hourly P10/P50/mean/P90 firm-capacity curve vs the 1 MW lot."""
    validate_scenario(scenario)
    prof = cache.profile[cache.profile["scenario"] == scenario].sort_values("hour")
    buckets = [
        {
            "hour": int(r.hour),
            "p10_mw": round(float(r.p10_mw), 4),
            "p50_mw": round(float(r.p50_mw), 4),
            "mean_mw": round(float(r.mean_mw), 4),
            "p90_mw": round(float(r.p90_mw), 4),
        }
        for r in prof.itertuples(index=False)
    ]
    firm_peak = max((b["p10_mw"] for b in buckets), default=0.0)
    return {
        "scenario": scenario,
        "lot_mw": params.LOT_MW,
        "firm_pctl": params.FIRM_PCTL,
        "firm_peak_mw": round(firm_peak, 4),
        "profile": buckets,
    }


def get_timeseries(scenario: str, frm: str | None, to: str | None) -> dict:
    """F6: raw 15-min supply series within [from, to)."""
    validate_scenario(scenario)
    start, end = resolve_range(frm, to)
    df = cache.pool[
        (cache.pool["scenario"] == scenario)
        & (cache.pool["ts"] >= start)
        & (cache.pool["ts"] < end)
    ].sort_values("ts")
    points = [
        {
            "ts": ts.isoformat(),
            "available_mw": round(float(mw), 4),
            "available_mwh": round(float(mwh), 4),
            "n_vehicles": int(nv),
        }
        for ts, mw, mwh, nv in zip(
            df["ts"], df["available_mw"], df["available_mwh"], df["n_vehicles"]
        )
    ]
    return {
        "scenario": scenario,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "points": points,
    }
