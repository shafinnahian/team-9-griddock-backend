"""Live value engine — F15 (V1G smart charging), F16 (V2G arbitrage),
F17 (degradation), F18 (value stack).

Computed on the fly per (scenario, deg_cost) so the demo sliders stay
interactive; results are memoised since the underlying data is static.

Stream decomposition (disjoint, additive before/after degradation):
    net_total = smart_charging + neg_absorption + arbitrage - degradation (+ fcr)
where smart_charging is the non-negative-hour shifting saving and neg_absorption
is the bonus from being paid to charge at negative prices (their sum is the
total V1G saving). All figures are FLEET totals, annualised; per_vehicle divides
by FLEET_SIZE.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.cache import cache
from app.core import params

_QH = 0.25  # hours per 15-min interval

# memo: (scenario, deg_cost_rounded) -> result dict
_memo: dict[tuple[str, float], dict] = {}


def _extend_for_depot(ts_start: pd.Series, ts_end: pd.Series, scenario: str) -> pd.Series:
    if scenario != "depot":
        return ts_end
    min_end = ts_start + pd.Timedelta(hours=params.DEPOT_MIN_DWELL_H)
    return pd.concat([ts_end, min_end], axis=1).max(axis=1)


def _f15_smart_charging(scenario: str) -> dict:
    """Per-session V1G: shift the same energy to the cheapest hours in the plug
    window (<= peak_kw per hour). Returns period (un-annualised) fleet totals."""
    price = cache.hourly_price  # Series indexed by hour Timestamp
    price_idx = price.index.values
    price_val = price.values

    sessions = cache.sessions
    end = _extend_for_depot(sessions["ts_start"], sessions["ts_end"], scenario)

    total_unctrl = 0.0
    total_smart = 0.0
    neg_earnings = 0.0   # positive € earned at negative-price hours
    neg_kwh = 0.0

    starts = sessions["ts_start"].dt.floor("h").values
    ends = end.values
    E_arr = sessions["kwh_delivered"].values
    P_arr = sessions["peak_kw"].values

    for i in range(len(sessions)):
        E = float(E_arr[i])
        P = float(P_arr[i])
        if E <= 0 or P <= 0:
            continue
        lo = np.searchsorted(price_idx, starts[i], side="left")
        hi = np.searchsorted(price_idx, ends[i], side="left")  # hours < end
        if hi <= lo:
            hi = min(lo + 1, len(price_idx))  # at least the start hour
        w = price_val[lo:hi]
        if w.size == 0:
            continue

        total_unctrl += E * w.mean() / 1000.0

        # greedy: cheapest hours first, <= P kWh per hour, until E met
        order = np.argsort(w, kind="stable")
        remaining = E
        for k in order:
            if remaining <= 0:
                break
            q = min(P, remaining)  # kWh this hour
            p = w[k]
            total_smart += p * q / 1000.0
            if p < 0:
                neg_earnings += -p * q / 1000.0
                neg_kwh += q
            remaining -= q

    savings = total_unctrl - total_smart
    return {
        "total_savings_eur": savings,
        "neg_absorption_eur": neg_earnings,
        "neg_absorbed_mwh": neg_kwh / 1000.0,
    }


def _f16_arbitrage(scenario: str, deg_cost: float) -> dict:
    """Per-day one-cycle V2G arbitrage on the pool ⋈ market frame."""
    pool = cache.pool[cache.pool["scenario"] == scenario]
    df = pool.merge(cache.market[["ts", "price_eur_mwh"]], on="ts")
    df = df[(df["available_mw"] > 0) & df["price_eur_mwh"].notna()].copy()
    if df.empty:
        return {"arbitrage_gross_eur": 0.0, "degradation_eur": 0.0, "discharged_mwh": 0.0}
    df["day"] = df["ts"].dt.normalize()

    gross = 0.0
    deg = 0.0
    discharged = 0.0
    eta = params.ETA_RT

    for _, g in df.groupby("day"):
        gs = g.sort_values("price_eur_mwh")
        charge = gs.head(params.CHG_SLOTS)
        discharge = gs.tail(params.DCH_SLOTS)
        if charge.empty or discharge.empty:
            continue
        sell = float(discharge["price_eur_mwh"].mean())
        buy = float(charge["price_eur_mwh"].mean())
        # act only if the spread covers efficiency loss + degradation
        if sell <= buy / eta + deg_cost:
            continue
        e_slot = np.minimum(discharge["available_mw"].values * _QH,
                            discharge["available_mwh"].values)
        eout = float(e_slot.sum())
        eout = min(eout, float(g["available_mwh"].max()))  # ~one cycle/day cap
        if eout <= 0:
            continue
        ein = eout / eta
        gross += eout * sell - ein * buy
        deg += eout * deg_cost
        discharged += eout

    return {
        "arbitrage_gross_eur": gross,
        "degradation_eur": deg,
        "discharged_mwh": discharged,
    }


def compute_value_stack(scenario: str, deg_cost: float) -> dict:
    key = (scenario, round(float(deg_cost), 2))
    if key in _memo:
        return _memo[key]

    af = cache.annualization_factor
    n = float(params.FLEET_SIZE)

    f15 = _f15_smart_charging(scenario)
    f16 = _f16_arbitrage(scenario, deg_cost)

    smart_total = f15["total_savings_eur"] * af
    neg_abs = f15["neg_absorption_eur"] * af
    smart_only = smart_total - neg_abs  # non-negative-hour shifting saving
    arbitrage = f16["arbitrage_gross_eur"] * af
    degradation = f16["degradation_eur"] * af
    surplus_mwh = f15["neg_absorbed_mwh"] * af

    net_total = smart_only + neg_abs + arbitrage - degradation

    result = {
        "scenario": scenario,
        "deg_cost_eur_mwh": round(float(deg_cost), 2),
        "streams": {
            "smart_charging_eur": round(smart_only, 2),
            "neg_absorption_eur": round(neg_abs, 2),
            "arbitrage_eur": round(arbitrage, 2),
            "fcr_eur": None,  # deferred — needs regelleistung.net pricing
            "degradation_eur": round(degradation, 2),
        },
        "net_total_eur": round(net_total, 2),
        "per_vehicle_eur": round(net_total / n, 2),
        "surplus_mwh": round(surplus_mwh, 2),
        "benchmarks": {
            "french_eur_per_ev": params.BENCHMARK_FRENCH_EUR_PER_EV,
            "agora_2030_eur_per_ev": params.BENCHMARK_AGORA_2030_EUR_PER_EV,
        },
    }
    _memo[key] = result
    return result
