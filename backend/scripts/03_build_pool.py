"""03 — F3 (SoC interp) + F4/F5 (power/energy) + F6 (aggregate pool) + F19 (dwell).

Builds fact_pool_15min for BOTH scenarios ('actual', 'depot'). The pool grid is
taken from fact_market_15min so the two tables join 1:1 on ts (VW_DEMO).

  - actual: sessions as logged.
  - depot (F19/D12): each V2G-able session's plugged window is extended to a
    minimum of DEPOT_MIN_DWELL_H hours. SoC interpolation stays anchored to the
    original [ts_start, ts_end]; F3's clip([0,1]) holds the ending SoC flat
    across the extension (vehicle sits plugged at soc_end).

    python scripts/03_build_pool.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from scripts._common import truncate_then_insert  # noqa: E402

from app.core.params import DEPOT_MIN_DWELL_H, RESERVE_SOC, SCENARIOS  # noqa: E402
from app.db import engine  # noqa: E402

STEP = pd.Timedelta("15min")


def _load_grid() -> pd.DatetimeIndex:
    ts = pd.read_sql("SELECT ts FROM fact_market_15min ORDER BY ts", engine)["ts"]
    return pd.DatetimeIndex(pd.to_datetime(ts))


def _load_v2g_sessions() -> pd.DataFrame:
    cols = ("vehicle_id", "ts_start", "ts_end", "peak_kw", "soc_start_pct",
            "soc_end_pct")
    df = pd.read_sql(
        "SELECT s.ts_start, s.ts_end, s.peak_kw, s.soc_start_pct, s.soc_end_pct, "
        "v.battery_capacity_kwh "
        "FROM fact_session s JOIN dim_vehicle v ON v.vehicle_id = s.vehicle_id "
        "WHERE s.is_v2g_able = true",
        engine,
    )
    df["ts_start"] = pd.to_datetime(df["ts_start"])
    df["ts_end"] = pd.to_datetime(df["ts_end"])
    return df


def build_pool(sessions: pd.DataFrame, grid: pd.DatetimeIndex, scenario: str) -> pd.DataFrame:
    n = len(grid)
    # Map timestamps to array positions via the REAL grid (searchsorted), not
    # arithmetic indices — the grid has a DST gap (2024-03-31 03:00) so
    # floor((ts-grid0)/step) would mis-place every session after that date.
    grid_ns = grid.values.astype("int64")
    step_ns = int(STEP.value)  # 900e9 ns
    mw = np.zeros(n)
    mwh = np.zeros(n)
    nveh = np.zeros(n, dtype=np.int64)

    for s in sessions.itertuples(index=False):
        start_ns = s.ts_start.value
        end_ns = s.ts_end.value
        span_ns = end_ns - start_ns
        if span_ns <= 0:
            continue

        # F19: extend only the *availability* window end for the depot scenario.
        # SoC interpolation stays anchored to the original span; F3's clip holds
        # soc_end flat across the extension.
        avail_end_ns = end_ns
        if scenario == "depot":
            min_end_ns = start_ns + DEPOT_MIN_DWELL_H * 3600 * 10**9
            avail_end_ns = max(avail_end_ns, int(min_end_ns))

        # Intervals [grid_ts, grid_ts+step) overlapping [start, avail_end):
        # grid_ts > start-step (left) and grid_ts < avail_end (right).
        left = int(np.searchsorted(grid_ns, start_ns - step_ns, side="right"))
        right = int(np.searchsorted(grid_ns, avail_end_ns, side="left"))
        if right <= left:
            continue

        idx = np.arange(left, right)
        frac = np.clip((grid_ns[idx] - start_ns) / span_ns, 0.0, 1.0)  # F3, eval at interval start
        soc = s.soc_start_pct + frac * (s.soc_end_pct - s.soc_start_pct)

        mask = soc > RESERVE_SOC  # F4 gate
        if not mask.any():
            continue
        sel = idx[mask]
        mw[sel] += s.peak_kw / 1000.0  # F4 -> MW
        # F5: energy headroom (MWh)
        mwh[sel] += (soc[mask] - RESERVE_SOC) / 100.0 * s.battery_capacity_kwh / 1000.0
        nveh[sel] += 1

    return pd.DataFrame(
        {
            "ts": grid,
            "scenario": scenario,
            "available_mw": mw,
            "available_mwh": mwh,
            "n_vehicles": nveh,
        }
    )


def main() -> None:
    grid = _load_grid()
    sessions = _load_v2g_sessions()
    frames = [build_pool(sessions, grid, sc) for sc in SCENARIOS]
    pool = pd.concat(frames, ignore_index=True)
    n = truncate_then_insert("fact_pool_15min", pool)
    for sc in SCENARIOS:
        g = pool[pool["scenario"] == sc]
        print(f"03: {sc}: rows={len(g)}, peak_mw={g['available_mw'].max():.3f}, "
              f"max_nveh={int(g['n_vehicles'].max())}")
    print(f"03: fact_pool_15min total rows={n}")


if __name__ == "__main__":
    main()
