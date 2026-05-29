"""Market services — F11/F12 (price/surplus series) and F11/F13 (scalar stats)."""

from __future__ import annotations

import pandas as pd

from app.cache import cache
from app.services._query import resolve_range


def get_prices(frm: str | None, to: str | None) -> dict:
    start, end = resolve_range(frm, to)
    df = cache.market[(cache.market["ts"] >= start) & (cache.market["ts"] < end)].sort_values("ts")

    def _f(x) -> float | None:
        return None if pd.isna(x) else round(float(x), 3)

    points = [
        {
            "ts": r.ts.isoformat(),
            "price_eur_mwh": _f(r.price_eur_mwh),
            "residual_load_mwh": _f(r.residual_load_mwh),
            "pv_mwh": _f(r.pv_mwh),
            "is_negative_price": bool(r.is_negative_price),
        }
        for r in df.itertuples(index=False)
    ]
    return {"from": start.isoformat(), "to": end.isoformat(), "points": points}


def get_stats() -> dict:
    """F11 + F13 scalar KPIs over the full window."""
    m = cache.market
    price = m["price_eur_mwh"]

    neg_hours = int(m.loc[m["is_negative_price"], "ts"].dt.floor("h").nunique())
    total_hours = int(m["ts"].dt.floor("h").nunique())
    daily_spread = (
        m.assign(day=m["ts"].dt.normalize())
        .groupby("day")["price_eur_mwh"]
        .agg(lambda s: s.max() - s.min())
        .mean()
    )

    wk = m[m["ts"].dt.dayofweek < 5].copy()
    wk["hour"] = wk["ts"].dt.hour
    hod = wk.groupby("hour")["price_eur_mwh"].mean()
    trough_h = int(hod.idxmin())
    peak_h = int(hod.idxmax())

    imb = m["imbalance_price_eur_mwh"].dropna()

    return {
        "price_mean_eur_mwh": round(float(price.mean()), 2),
        "neg_hours": neg_hours,
        "neg_hours_pct": round(100.0 * neg_hours / total_hours, 1),
        "daily_spread_eur_mwh": round(float(daily_spread), 1),
        "weekday_trough": {"hour": trough_h, "price_eur_mwh": round(float(hod.loc[trough_h]), 1)},
        "weekday_peak": {"hour": peak_h, "price_eur_mwh": round(float(hod.loc[peak_h]), 1)},
        "imbalance_mean_eur_mwh": round(float(imb.mean()), 1),
        "imbalance_std_eur_mwh": round(float(imb.std(ddof=0)), 1),
        "imbalance_min_eur_mwh": round(float(imb.min()), 1),
        "imbalance_max_eur_mwh": round(float(imb.max()), 1),
    }
