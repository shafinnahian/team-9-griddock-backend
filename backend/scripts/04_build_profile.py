"""04 — F7 (reliability percentiles / firm capacity).

Weekday-only, grouped by hour-of-day, per scenario: P10 (firm), P50, mean, P90.
Writes agg_hourly_profile (24 hours x 2 scenarios).

    python scripts/04_build_profile.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from scripts._common import truncate_then_insert  # noqa: E402

from app.db import engine  # noqa: E402


def main() -> None:
    pool = pd.read_sql(
        "SELECT ts, scenario, available_mw FROM fact_pool_15min", engine
    )
    pool["ts"] = pd.to_datetime(pool["ts"])
    weekday = pool[pool["ts"].dt.dayofweek < 5].copy()
    weekday["hour"] = weekday["ts"].dt.hour

    rows = []
    for scenario, g in weekday.groupby("scenario"):
        prof = g.groupby("hour")["available_mw"].agg(
            p10_mw=lambda s: s.quantile(0.10),
            p50_mw="median",
            mean_mw="mean",
            p90_mw=lambda s: s.quantile(0.90),
        ).reset_index()
        prof["scenario"] = scenario
        rows.append(prof)

    profile = pd.concat(rows, ignore_index=True)[
        ["hour", "scenario", "p10_mw", "p50_mw", "mean_mw", "p90_mw"]
    ]
    n = truncate_then_insert("agg_hourly_profile", profile)

    for scenario, g in profile.groupby("scenario"):
        peak = g.loc[g["p10_mw"].idxmax()]
        print(f"04: {scenario}: firm peak hour={int(peak['hour'])}, "
              f"p10={peak['p10_mw']:.3f}, mean={peak['mean_mw']:.3f}, "
              f"p90={peak['p90_mw']:.3f}")
    print(f"04: agg_hourly_profile rows={n}")


if __name__ == "__main__":
    main()
