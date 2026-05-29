"""Integration smoke tests against the live app (cache warmed from Postgres).

These assert the §5 anchors flow through the HTTP layer and the role layer
composes correctly. Require the ETL to have run (run_all.py).
"""

from __future__ import annotations


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready(client):
    body = client.get("/ready").json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["cache"] == "ok"


def test_scenario_presets(client):
    body = client.get("/api/scenario/presets").json()
    assert set(body) == {"actual", "depot"}
    assert "12" in body["depot"]["dwell_assumption"]


def test_pool_profile_firm_peak(client):
    body = client.get("/api/pool/profile?scenario=actual").json()
    assert body["lot_mw"] == 1.0
    peak = max(body["profile"], key=lambda b: b["p10_mw"])
    assert peak["hour"] == 9
    assert abs(peak["p10_mw"] - 0.15) < 0.02


def test_pool_timeseries_dst_day(client):
    # The 2024-06-06 08:00 interval exposed the DST bug; must read 23 vehicles.
    r = client.get(
        "/api/pool/timeseries",
        params={"scenario": "actual", "from": "2024-06-06T08:00:00", "to": "2024-06-06T08:15:00"},
    ).json()
    assert r["points"][0]["n_vehicles"] == 23


def test_market_stats_anchors(client):
    s = client.get("/api/market/stats").json()
    assert abs(s["price_mean_eur_mwh"] - 67.58) < 0.5
    assert s["neg_hours"] == 224
    assert abs(s["imbalance_std_eur_mwh"] - 311.5) < 5


def test_value_stack_anchors_and_slider(client):
    actual = client.get("/api/value/stack?scenario=actual&deg_cost=50").json()
    depot = client.get("/api/value/stack?scenario=depot&deg_cost=50").json()
    # total V1G saving anchor ~€13/EV/yr
    v1g_per_ev = (actual["streams"]["smart_charging_eur"] + actual["streams"]["neg_absorption_eur"]) / 250
    assert abs(v1g_per_ev - 13.0) < 2.0
    # the honesty slider: depot lifts per-vehicle value well above actual
    assert depot["per_vehicle_eur"] > actual["per_vehicle_eur"]
    assert actual["streams"]["fcr_eur"] is None


def test_value_stack_degradation_monotonic(client):
    lo = client.get("/api/value/stack?scenario=actual&deg_cost=10").json()
    hi = client.get("/api/value/stack?scenario=actual&deg_cost=150").json()
    # higher degradation cost => lower net value
    assert hi["per_vehicle_eur"] < lo["per_vehicle_eur"]
    # surplus (F15, negative-price absorption) is degradation-independent
    assert lo["surplus_mwh"] == hi["surplus_mwh"]


def test_geography_frankfurt_share(client):
    body = client.get("/api/geography").json()
    fc = next(r for r in body["regions"] if r["region"] == "Frankfurt core")
    assert abs(fc["share"] - 0.71) < 0.02
    assert len(body["top_postal_codes"]) > 0


def test_me_roles(client):
    assert client.get("/api/me?role=bkv").json()["role"] == "bkv"
    assert client.get("/api/me", headers={"X-User-Role": "fleet"}).json()["role"] == "fleet"


def test_dashboard_bkv(client):
    body = client.get("/api/dashboard/bkv?scenario=actual").json()
    assert body["role"] == "bkv"
    assert body["headline"]["metric"] == "firm_mw"
    assert body["firm_capacity"]["lot_mw"] == 1.0
    assert len(body["firm_capacity"]["profile"]) == 24
    assert "imbalance_std_eur_mwh" in body["reliability"]


def test_dashboard_fleet(client):
    body = client.get("/api/dashboard/fleet?scenario=depot&deg_cost=50").json()
    assert body["role"] == "fleet"
    assert body["headline"]["metric"] == "eur_per_vehicle"
    assert body["fleet"]["guaranteed_departure_soc_pct"] == 30.0
    assert body["fleet"]["fleet_size"] == 250
    assert "streams" in body["value_stack"]


def test_validation_errors(client):
    assert client.get("/api/pool/profile?scenario=bogus").status_code == 422
    assert client.get("/api/value/stack?deg_cost=999").status_code == 422
    assert client.get("/api/me?role=driver").status_code == 422
