"""02 — F9 (market spine) + F10 (renewables) + F11/F12 (price/surplus features).

Merges the SMARD exports on the 15-min ts; the hourly day-ahead price is
forward-filled to 15-min by flooring ts to the hour. Writes fact_market_15min.

    python scripts/02_load_market.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from scripts._common import read_smard, truncate_then_insert  # noqa: E402

MARKET_COLS = [
    "ts",
    "price_eur_mwh",
    "grid_load_mwh",
    "residual_load_mwh",
    "renewable_gen_mwh",
    "pv_mwh",
    "imbalance_price_eur_mwh",
    "resid_load_forecast_mwh",
    "is_negative_price",
]


def main() -> None:
    # Actual consumption -> grid load + residual load (defines the 15-min spine).
    load = read_smard(
        "Actual_consumption_*.csv",
        {"grid_load_mwh": "grid load", "residual_load_mwh": "Residual load"},
    )
    # Actual generation -> renewable sum + PV (F10).
    gen_raw = read_smard(
        "Actual_generation_*.csv",
        {
            "wind_off": "Wind offshore",
            "wind_on": "Wind onshore",
            "pv_mwh": "Photovoltaics",
        },
    )
    gen = pd.DataFrame({"ts": gen_raw["ts"]})
    gen["renewable_gen_mwh"] = (
        gen_raw["wind_off"] + gen_raw["wind_on"] + gen_raw["pv_mwh"]
    )
    gen["pv_mwh"] = gen_raw["pv_mwh"]

    # Forecasted consumption -> residual-load forecast.
    fc = read_smard(
        "Forecasted_consumption_*.csv",
        {"resid_load_forecast_mwh": "Residual load"},
    )
    # Balancing energy -> imbalance price.
    bal = read_smard(
        "Balancing_energy_*.csv", {"imbalance_price_eur_mwh": "Price"}
    )
    # Day-ahead -> hourly DE/LU price.
    price = read_smard(
        "Day-ahead_prices_*.csv", {"price_eur_mwh": "Germany/Luxembourg"}
    )

    # F9: 15-min spine from consumption; ffill hourly price by flooring ts to hour.
    spine = load[["ts"]].copy()
    price_by_hour = price.set_index("ts")["price_eur_mwh"]
    spine["price_eur_mwh"] = spine["ts"].dt.floor("h").map(price_by_hour)

    m = (
        spine.merge(load, on="ts")
        .merge(gen, on="ts")
        .merge(fc, on="ts")
        .merge(bal, on="ts")
    )
    m["is_negative_price"] = m["price_eur_mwh"] < 0

    m = m[MARKET_COLS]
    n = truncate_then_insert("fact_market_15min", m)
    print(
        f"02: fact_market_15min={n}, price_mean={m['price_eur_mwh'].mean():.2f}, "
        f"neg_15min={int(m['is_negative_price'].sum())}"
    )


if __name__ == "__main__":
    main()
