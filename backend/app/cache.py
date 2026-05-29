"""In-process warm read-cache.

The dataset is static and small (~17k rows/table), so services compute on
pandas frames warmed once at startup rather than re-querying Postgres per
request. Postgres stays the system of record; this is a read-through cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.db import engine


@dataclass
class DataCache:
    sessions: pd.DataFrame = field(default_factory=pd.DataFrame)
    market: pd.DataFrame = field(default_factory=pd.DataFrame)
    pool: pd.DataFrame = field(default_factory=pd.DataFrame)
    profile: pd.DataFrame = field(default_factory=pd.DataFrame)
    hourly_price: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    n_days: int = 0
    loaded: bool = False

    def load(self) -> None:
        """Read all tables into memory. Safe to call again to refresh."""
        self.sessions = pd.read_sql(
            "SELECT s.*, v.battery_capacity_kwh, v.segment "
            "FROM fact_session s JOIN dim_vehicle v ON v.vehicle_id = s.vehicle_id",
            engine,
            parse_dates=["ts_start", "ts_end"],
        )
        self.market = pd.read_sql(
            "SELECT * FROM fact_market_15min ORDER BY ts", engine, parse_dates=["ts"]
        )
        self.pool = pd.read_sql(
            "SELECT * FROM fact_pool_15min ORDER BY ts", engine, parse_dates=["ts"]
        )
        self.profile = pd.read_sql("SELECT * FROM agg_hourly_profile", engine)

        # Hourly day-ahead price: one value per clock hour (price is ffilled to
        # 15-min, so the hour's :00 row carries the hourly price).
        hp = self.market[["ts", "price_eur_mwh"]].copy()
        hp["hour"] = hp["ts"].dt.floor("h")
        self.hourly_price = (
            hp.groupby("hour")["price_eur_mwh"].first().sort_index()
        )

        self.n_days = self.market["ts"].dt.normalize().nunique()
        self.loaded = True

    @property
    def annualization_factor(self) -> float:
        """365 / observed-days (Calc-Spec F15/F16 annualisation)."""
        return 365.0 / self.n_days if self.n_days else 1.0


cache = DataCache()
