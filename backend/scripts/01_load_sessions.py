"""01 — F1 (clean sessions) + F2 (vehicle dimension).

Writes fact_session (~8,000) and dim_vehicle (250).

    python scripts/01_load_sessions.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from scripts._common import settings, truncate_then_insert  # noqa: E402

from app.core.params import V2G_LOCATIONS  # noqa: E402

SESSION_COLS = [
    "session_id",
    "vehicle_id",
    "ts_start",
    "ts_end",
    "dwell_h",
    "location_type",
    "postal_code",
    "kwh_delivered",
    "peak_kw",
    "soc_start_pct",
    "soc_end_pct",
    "is_v2g_able",
]


def main() -> None:
    df = pd.read_csv(settings.sessions_csv_path)

    # F1: parse datetimes, derive dwell_h and is_v2g_able.
    df["ts_start"] = pd.to_datetime(df["timestamp_start"])
    df["ts_end"] = pd.to_datetime(df["timestamp_end"])
    df["dwell_h"] = (df["ts_end"] - df["ts_start"]).dt.total_seconds() / 3600.0
    df["kwh_delivered"] = pd.to_numeric(df["kWh_delivered"])
    df["peak_kw"] = pd.to_numeric(df["peak_kw"])
    df["postal_code"] = pd.to_numeric(df["postal_code"]).astype(int)
    df["soc_start_pct"] = pd.to_numeric(df["soc_start_pct"])
    df["soc_end_pct"] = pd.to_numeric(df["soc_end_pct"])
    df["battery_capacity_kwh"] = pd.to_numeric(df["battery_capacity_kwh"])
    df["is_v2g_able"] = df["location_type"].isin(V2G_LOCATIONS)

    sessions = df[SESSION_COLS].copy()

    # F2: vehicle dimension — battery & segment are constant per vehicle (verified).
    veh = (
        df.groupby("vehicle_id")
        .agg(
            segment=("vehicle_segment", "first"),
            battery_capacity_kwh=("battery_capacity_kwh", "first"),
        )
        .reset_index()
    )

    n_v = truncate_then_insert("dim_vehicle", veh)
    n_s = truncate_then_insert("fact_session", sessions)
    n_v2g = int(sessions["is_v2g_able"].sum())
    print(f"01: dim_vehicle={n_v}, fact_session={n_s}, v2g_able={n_v2g} "
          f"({100*n_v2g/n_s:.0f}%)")


if __name__ == "__main__":
    main()
