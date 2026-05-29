"""Pydantic response shapes — the FE contract (API_GUIDELINE.md §2-3).

Used as router response_model so /docs is fully typed. snake_case throughout.
"""

from __future__ import annotations

from pydantic import BaseModel


# --- scenario ---------------------------------------------------------------
class Preset(BaseModel):
    label: str
    desc: str
    dwell_assumption: str


class PresetsResponse(BaseModel):
    actual: Preset
    depot: Preset


# --- pool -------------------------------------------------------------------
class ProfileBucket(BaseModel):
    hour: int
    p10_mw: float
    p50_mw: float
    mean_mw: float
    p90_mw: float


class ProfileResponse(BaseModel):
    scenario: str
    lot_mw: float
    firm_pctl: float
    firm_peak_mw: float
    profile: list[ProfileBucket]


# Note: the pool-timeseries and market-prices responses carry a `from` key
# (a Python keyword), so those two routes return plain dicts rather than a typed
# response_model. The point shapes below document their items.
class PoolPoint(BaseModel):
    ts: str
    available_mw: float
    available_mwh: float
    n_vehicles: int


# --- market -----------------------------------------------------------------
class MarketPoint(BaseModel):
    ts: str
    price_eur_mwh: float | None
    residual_load_mwh: float | None
    pv_mwh: float | None
    is_negative_price: bool


class HourPrice(BaseModel):
    hour: int
    price_eur_mwh: float


class MarketStatsResponse(BaseModel):
    price_mean_eur_mwh: float
    neg_hours: int
    neg_hours_pct: float
    daily_spread_eur_mwh: float
    weekday_trough: HourPrice
    weekday_peak: HourPrice
    imbalance_mean_eur_mwh: float
    imbalance_std_eur_mwh: float
    imbalance_min_eur_mwh: float
    imbalance_max_eur_mwh: float


# --- value ------------------------------------------------------------------
class ValueStreams(BaseModel):
    smart_charging_eur: float
    neg_absorption_eur: float
    arbitrage_eur: float
    fcr_eur: float | None
    degradation_eur: float


class Benchmarks(BaseModel):
    french_eur_per_ev: float
    agora_2030_eur_per_ev: float


class ValueStackResponse(BaseModel):
    scenario: str
    deg_cost_eur_mwh: float
    streams: ValueStreams
    net_total_eur: float
    per_vehicle_eur: float
    surplus_mwh: float
    benchmarks: Benchmarks


# --- geography --------------------------------------------------------------
class RegionRow(BaseModel):
    region: str
    sessions: int
    vehicles: int
    kw: float
    share: float


class PostalRow(BaseModel):
    postal_code: int
    sessions: int
    vehicles: int
    kw: float


class GeographyResponse(BaseModel):
    regions: list[RegionRow]
    top_postal_codes: list[PostalRow]


# --- role layer -------------------------------------------------------------
class MeResponse(BaseModel):
    role: str
    label: str
    available_roles: list[str]
    headline_metric: str
    default_scenario: str


class Headline(BaseModel):
    metric: str
    value: float
    unit: str


class FirmCapacity(BaseModel):
    lot_mw: float
    firm_pctl: float
    firm_peak_mw: float
    profile: list[ProfileBucket]


class Procurement(BaseModel):
    procurable_firm_mw: float
    lots_fillable: int
    pct_time_pool_ge_1mw: float
    surplus_absorbed_mwh: float


class Reliability(BaseModel):
    imbalance_mean_eur_mwh: float
    imbalance_std_eur_mwh: float
    imbalance_max_eur_mwh: float
    note: str


class BkvDashboardResponse(BaseModel):
    role: str
    scenario: str
    headline: Headline
    firm_capacity: FirmCapacity
    procurement: Procurement
    reliability: Reliability


class ValueStackInner(BaseModel):
    streams: ValueStreams
    net_total_eur: float
    per_vehicle_eur: float
    surplus_mwh: float
    benchmarks: Benchmarks


class FleetInfo(BaseModel):
    fleet_size: int
    v2g_able_vehicles: int
    guaranteed_departure_soc_pct: float
    soc_guarantee_note: str


class FleetDashboardResponse(BaseModel):
    role: str
    scenario: str
    deg_cost_eur_mwh: float
    headline: Headline
    value_stack: ValueStackInner
    fleet: FleetInfo
