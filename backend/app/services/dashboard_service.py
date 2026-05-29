"""Role dashboards — compose the shared services into per-user-type bundles.

Two user types, one shared pool (see API_GUIDELINE.md §0/§4):
  - bkv   (buyer/grid):   firm MW vs 1 MW lot, reliability premium, procurement.
  - fleet (seller/fleet): value stack net of degradation, €/vehicle, SoC guarantee.

No new tables/data — pure view-shaping over pool/market/value services.
"""

from __future__ import annotations

from app.cache import cache
from app.core import params
from app.services import market_service, pool_service, value_service
from app.services._query import validate_scenario

_ROLE_META = {
    "bkv": {
        "label": "Grid / BKV buyer",
        "headline_metric": "firm_mw",
        "default_scenario": "actual",
    },
    "fleet": {
        "label": "EV fleet operator",
        "headline_metric": "eur_per_vehicle",
        "default_scenario": "actual",
    },
}


def get_me(role: str) -> dict:
    meta = _ROLE_META[role]
    return {
        "role": role,
        "label": meta["label"],
        "available_roles": list(_ROLE_META.keys()),
        "headline_metric": meta["headline_metric"],
        "default_scenario": meta["default_scenario"],
    }


def _pct_time_pool_ge_lot(scenario: str) -> float:
    pool = cache.pool[cache.pool["scenario"] == scenario]
    wk = pool[pool["ts"].dt.dayofweek < 5]
    if wk.empty:
        return 0.0
    return round(100.0 * float((wk["available_mw"] >= params.LOT_MW).mean()), 2)


def get_bkv_dashboard(scenario: str) -> dict:
    validate_scenario(scenario)
    fc = pool_service.get_profile(scenario)
    stats = market_service.get_stats()
    # surplus is F15-driven (deg_cost-independent); use the default deg_cost.
    surplus = value_service.compute_value_stack(scenario, params.DEG_COST)["surplus_mwh"]

    firm_peak = fc["firm_peak_mw"]
    return {
        "role": "bkv",
        "scenario": scenario,
        "headline": {"metric": "firm_mw", "value": firm_peak, "unit": "MW"},
        "firm_capacity": {
            "lot_mw": fc["lot_mw"],
            "firm_pctl": fc["firm_pctl"],
            "firm_peak_mw": firm_peak,
            "profile": fc["profile"],
        },
        "procurement": {
            "procurable_firm_mw": firm_peak,
            "lots_fillable": int(firm_peak // params.LOT_MW),
            "pct_time_pool_ge_1mw": _pct_time_pool_ge_lot(scenario),
            "surplus_absorbed_mwh": surplus,
        },
        "reliability": {
            "imbalance_mean_eur_mwh": stats["imbalance_mean_eur_mwh"],
            "imbalance_std_eur_mwh": stats["imbalance_std_eur_mwh"],
            "imbalance_max_eur_mwh": stats["imbalance_max_eur_mwh"],
            "note": (
                "A firmer pool avoids exposure to imbalance-price spikes; "
                "firmness = the P10 grade."
            ),
        },
    }


def get_fleet_dashboard(scenario: str, deg_cost: float) -> dict:
    validate_scenario(scenario)
    vs = value_service.compute_value_stack(scenario, deg_cost)
    v2g_vehicles = int(
        cache.sessions.loc[cache.sessions["is_v2g_able"], "vehicle_id"].nunique()
    )
    return {
        "role": "fleet",
        "scenario": scenario,
        "deg_cost_eur_mwh": vs["deg_cost_eur_mwh"],
        "headline": {
            "metric": "eur_per_vehicle",
            "value": vs["per_vehicle_eur"],
            "unit": "€/EV/yr",
        },
        "value_stack": {
            "streams": vs["streams"],
            "net_total_eur": vs["net_total_eur"],
            "per_vehicle_eur": vs["per_vehicle_eur"],
            "surplus_mwh": vs["surplus_mwh"],
            "benchmarks": vs["benchmarks"],
        },
        "fleet": {
            "fleet_size": params.FLEET_SIZE,
            "v2g_able_vehicles": v2g_vehicles,
            "guaranteed_departure_soc_pct": params.RESERVE_SOC,
            "soc_guarantee_note": (
                f"Vehicles are never discharged below RESERVE_SOC, so departure "
                f"SoC is guaranteed ≥ {int(params.RESERVE_SOC)}%."
            ),
        },
    }
