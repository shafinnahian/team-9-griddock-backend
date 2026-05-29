"""The 5 ORM tables == the data model (Calc-Spec §1).

  DIM_VEHICLE  ||--o{  FACT_SESSION
  FACT_SESSION }o..o{  FACT_POOL_15MIN   (derived by time-overlap aggregation)
  FACT_POOL_15MIN  --  FACT_MARKET_15MIN (joined live on ts -> VW_DEMO)
  FACT_MARKET_15MIN --  AGG_HOURLY_PROFILE (summarised by hour)

The pool and profile tables carry a ``scenario`` key (F19): both ``actual`` and
``depot`` are built once by the ETL and selected by query.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DimVehicle(Base):
    __tablename__ = "dim_vehicle"

    vehicle_id: Mapped[str] = mapped_column(String, primary_key=True)
    segment: Mapped[str] = mapped_column(String)
    battery_capacity_kwh: Mapped[float] = mapped_column(Float)


class FactSession(Base):
    __tablename__ = "fact_session"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String, index=True)
    ts_start: Mapped[datetime] = mapped_column(DateTime)
    ts_end: Mapped[datetime] = mapped_column(DateTime)
    dwell_h: Mapped[float] = mapped_column(Float)
    location_type: Mapped[str] = mapped_column(String)
    postal_code: Mapped[int] = mapped_column(Integer)
    kwh_delivered: Mapped[float] = mapped_column(Float)
    peak_kw: Mapped[float] = mapped_column(Float)
    soc_start_pct: Mapped[float] = mapped_column(Float)
    soc_end_pct: Mapped[float] = mapped_column(Float)
    is_v2g_able: Mapped[bool] = mapped_column(Boolean, index=True)


class FactPool15Min(Base):
    __tablename__ = "fact_pool_15min"

    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    scenario: Mapped[str] = mapped_column(String, primary_key=True)  # 'actual' | 'depot'
    available_mw: Mapped[float] = mapped_column(Float)
    available_mwh: Mapped[float] = mapped_column(Float)
    n_vehicles: Mapped[int] = mapped_column(Integer)


class FactMarket15Min(Base):
    __tablename__ = "fact_market_15min"

    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    price_eur_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid_load_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    residual_load_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    renewable_gen_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    pv_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    imbalance_price_eur_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    resid_load_forecast_mwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_negative_price: Mapped[bool] = mapped_column(Boolean)


class AggHourlyProfile(Base):
    __tablename__ = "agg_hourly_profile"

    hour: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario: Mapped[str] = mapped_column(String, primary_key=True)
    p10_mw: Mapped[float] = mapped_column(Float)
    p50_mw: Mapped[float] = mapped_column(Float)
    mean_mw: Mapped[float] = mapped_column(Float)
    p90_mw: Mapped[float] = mapped_column(Float)
