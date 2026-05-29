"""Single source of truth for all domain constants (Calc-Spec §0).

NEVER hard-code these values anywhere else. NEVER read them from the
environment — they are scientific/model constants, versioned in code.
Deployment configuration (DB URL, paths, CORS) lives in ``config.py``.
"""

from __future__ import annotations

# --- Core model parameters (Calc-Spec §0) ----------------------------------

RESERVE_SOC: float = 30.0
"""Driving-reserve SoC (%). Floor below which a vehicle will not discharge."""

V2G_LOCATIONS: tuple[str, ...] = ("workplace", "urban")
"""Location types eligible for V2G. ``highway`` = in-transit DC fast → excluded."""

ETA_RT: float = 0.85
"""V2G round-trip efficiency (discharge model)."""

ETA_CH: float = 0.90
"""V1G charging efficiency (smart-charging model)."""

DEG_COST: float = 50.0
"""Degradation cost (EUR / MWh discharged), default ~5 c/kWh.

Overridable per request via the ``deg_cost`` query param. LFP chemistry is
nearer 25-30; the slider lets the demo explore sensitivity.
"""

LOT_MW: float = 1.0
"""Market lot minimum (MW). FCR/aFRR/mFRR minimum bid size (regelleistung.net)."""

FIRM_PCTL: float = 0.10
"""Firm percentile. P10 = the level available ~90% of the time (the reliability
grade we commit to). Selling a high percentile would under-deliver."""

DCH_SLOTS: int = 8
CHG_SLOTS: int = 8
"""Arbitrage windows: 8 quarter-hours = 2 h discharge / 2 h charge per day."""

# --- Time window (Calc-Spec §0) --------------------------------------------

WINDOW_START: str = "2024-01-01 00:00:00"
WINDOW_END: str = "2024-07-01 00:00:00"  # 2024-06-30 24:00 == 2024-07-01 00:00

# --- F19 dwell-scenario lever ----------------------------------------------

SCENARIOS: tuple[str, ...] = ("actual", "depot")
"""The two dwell presets. ``actual`` = sessions as logged (conservative floor);
``depot`` = realistic depot (extended overnight plug window)."""

DEPOT_MIN_DWELL_H: float = 12.0
"""Depot scenario (D12): each V2G-able session is extended to at least this
many hours, holding the ending SoC flat across the extension. Explicit and
labelled so the slider stays honest."""

# --- F8 geography region map (Calc-Spec §2, F8) -----------------------------

REGION_PREFIXES: dict[str, tuple[str, ...]] = {
    "Frankfurt core": ("60", "61"),
    "Offenbach/E": ("63",),
    "Wiesbaden/W": ("65",),
}
REGION_OTHER: str = "Other"

# --- F18 display benchmarks -------------------------------------------------

BENCHMARK_FRENCH_EUR_PER_EV: float = 74.0
"""French V2G pilot ~EUR 74 / EV / yr (with degradation)."""

BENCHMARK_AGORA_2030_EUR_PER_EV: float = 500.0
"""Agora projection ~EUR 500 / EV / yr by 2030."""

FLEET_SIZE: int = 250
"""Total vehicles in the dataset (per-vehicle annualisation divisor)."""

DEG_COST_MIN: float = 0.0
DEG_COST_MAX: float = 200.0
"""Accepted range for the ``deg_cost`` query override (validation bound)."""
