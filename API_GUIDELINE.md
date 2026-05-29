# GridDock Backend — API Guideline (Frontend Build Contract)

**Audience:** an AI (or developer) building the GridDock frontend. This document is the *single source of truth* for the HTTP contract. The backend implements exactly what is described here; the frontend should code against it without guessing.

**Pairs with:** `docs/infra_guideline/GridDock_DataModel_and_Calc_Spec.md` (feature IDs `F1–F19`, constants, validation numbers) and `GridDock_Infrastructure_Guideline.md` (architecture).

**For implementation** (real payloads, the two user types, state model, a typed client, error handling, TS types, component map) see **`FE_INTEGRATION_GUIDE.md`** — this file is the *what*, that one is the *how*.

---

## 0. Conventions (apply to every endpoint)

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000` (FE reads from `VITE_API_URL`). All API paths are under `/api`. |
| Format | JSON request/response. Field names are **`snake_case`** (all-Python stack; consistent everywhere). |
| Timestamps | ISO-8601 **naive local German time**, second precision, e.g. `"2024-01-01T09:15:00"`. No timezone suffix — the dataset is naive CET/CEST by design (Calc-Spec §0). Do **not** convert in the FE. |
| Time grain | Physical/market series are **15-minute**; day-ahead price is hourly forward-filled to 15-min; profiles are hourly (24 buckets). |
| Units | Power = **MW**, energy = **MWh**, price = **€/MWh**, money = **€**, per-vehicle = **€/EV/yr**, SoC = **%**. Units are in field-name suffixes (`_mw`, `_mwh`, `_eur`, `_eur_mwh`, `_pct`). |
| Data window | All series are bounded to **2024-01-01 00:00 → 2024-06-30 24:00**. Requests outside this clamp to the window. |
| CORS | `*` (local demo only). |
| Caching | Responses are deterministic for the same query (static dataset). FE may cache by query key (e.g. TanStack Query `staleTime`). |
| Request ID | Every response carries `X-Request-Id`. Echo it in bug reports. |
| Empty vs error | A valid query with no rows returns `200` with an empty array, **not** `404`. |

### Role / user-type model (demo-grade, no authentication)

GridDock serves **two user types**, both viewing the *same* shared pool from opposite sides of the marketplace:

- **`bkv`** — Balancing Responsible Party / grid operator / utility (the **buyer** of flexibility).
- **`fleet`** — EV fleet operator (the **seller** of battery capacity).

The demo has **no login/passwords**. The FE picks a role and:
- calls the **role-specific dashboard path** (`/api/dashboard/bkv` or `/api/dashboard/fleet`), and
- optionally sends header **`X-User-Role: bkv|fleet`** on shared endpoints (advisory only; does not change shared responses).

> **Future (not implemented):** role would come from an auth-token claim, and a `fleet_id` would scope data per operator. The path/contract below is forward-compatible with that.

---

## 1. Error format (RFC 9457 envelope)

Every non-2xx response uses this shape:

```json
{
  "type": "https://griddock.local/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "scenario must be one of: actual, depot",
  "instance": "/api/pool/profile",
  "request_id": "req_7f3a8b2c",
  "errors": [
    { "field": "scenario", "message": "must be one of: actual, depot", "code": "INVALID_ENUM" }
  ]
}
```

| Status | When |
|---|---|
| `200` | Success (incl. empty arrays). |
| `400` | Malformed request (bad date syntax, unparseable param). |
| `422` | Parsed but invalid value (unknown `scenario`, `deg_cost` out of range, `from` after `to`). |
| `404` | Unknown path / unknown `role`. |
| `500` | Unexpected server error (never leaks stack traces). |

**FE rule:** map `422` to inline field hints, `5xx` to a retry/toast, `Failed to fetch` to an offline banner. Never render raw `detail` for `5xx`.

---

## 2. Enums & shared types

```ts
type Scenario = "actual" | "depot";   // F19 dwell lever — the demo's spine
type Role     = "bkv" | "fleet";

// Hourly availability bucket (F7)
interface ProfileBucket {
  hour: number;        // 0..23
  p10_mw: number;      // FIRM capacity (~90% available) — the headline reliability grade
  p50_mw: number;      // median / best-effort
  mean_mw: number;
  p90_mw: number;      // optimistic ceiling (do NOT sell this)
}

// 15-min supply point (F6)
interface PoolPoint {
  ts: string;
  available_mw: number;
  available_mwh: number;
  n_vehicles: number;
}

// 15-min market point (F11/F12)
interface MarketPoint {
  ts: string;
  price_eur_mwh: number | null;
  residual_load_mwh: number | null;
  pv_mwh: number | null;
  is_negative_price: boolean;
}
```

**Defaults & ranges:** `scenario` default `"actual"`. `deg_cost` default `50.0`, allowed `0..200` (€/MWh; LFP ≈ 25–30). `from`/`to` default to the full window if omitted.

---

## 3. Shared (role-agnostic) endpoints

> **Status:** all §3 *and* §4 endpoints are **implemented and live** (examples show real responses); 24 tests pass. The backend contract is complete — the FE can be built against this document.

These power both user views. The FE composes them, or uses the role dashboards in §4 which bundle them.

### 3.1 `GET /api/scenario/presets`
The two dwell presets for the slider (F19). **Always show `actual` (floor) alongside `depot`.**

**Response**
```json
{
  "actual": {
    "label": "Data as-is",
    "desc": "Sessions exactly as logged — a conservative availability floor.",
    "dwell_assumption": "Plugged window = logged session only."
  },
  "depot": {
    "label": "Realistic depot",
    "desc": "Assumes depot vehicles stay plugged overnight — climbs toward benchmarks.",
    "dwell_assumption": "Each V2G-able session extended to a minimum 12h overnight window at ending SoC."
  }
}
```

### 3.2 `GET /api/pool/profile`
Hourly firm-capacity curve vs the 1 MW market lot (F6/F7). Powers the **FirmCapacityChart**.

| Query | Type | Default | Notes |
|---|---|---|---|
| `scenario` | `Scenario` | `actual` | |

**Response**
```json
{
  "scenario": "actual",
  "lot_mw": 1.0,
  "firm_pctl": 0.10,
  "firm_peak_mw": 0.15,
  "profile": [
    { "hour": 0, "p10_mw": 0.0, "p50_mw": 0.0, "mean_mw": 0.0, "p90_mw": 0.0 },
    "... 24 buckets, hour 0..23 ..."
  ]
}
```
> Validation anchor: `actual` peak at hour 9 → `p10_mw ≈ 0.15`, `mean_mw ≈ 0.23`, `p90_mw ≈ 0.34`.

### 3.3 `GET /api/pool/timeseries`
Raw 15-min supply series (F6). Powers detail/area charts.

| Query | Type | Default | Notes |
|---|---|---|---|
| `from` | ISO datetime | window start | inclusive |
| `to` | ISO datetime | window end | exclusive |
| `scenario` | `Scenario` | `actual` | |

> **FE guidance:** the full window is ~17.5k points. Request a bounded range (e.g. one week) for line charts; the backend returns all points in-range without pagination, so keep ranges sane.

**Response**
```json
{
  "scenario": "actual",
  "from": "2024-03-01T00:00:00",
  "to": "2024-03-08T00:00:00",
  "points": [ { "ts": "2024-03-01T00:00:00", "available_mw": 0.06, "available_mwh": 0.08, "n_vehicles": 3 } ]
}
```

### 3.4 `GET /api/market/prices`
15-min market series (F11/F12). Powers price/renewable charts and the negative-price highlights.

| Query | Type | Default |
|---|---|---|
| `from` | ISO datetime | window start |
| `to` | ISO datetime | window end |

**Response**
```json
{
  "from": "2024-03-01T00:00:00",
  "to": "2024-03-08T00:00:00",
  "points": [
    { "ts": "2024-03-01T00:00:00", "price_eur_mwh": 49.7, "residual_load_mwh": 12000.0, "pv_mwh": 0.0, "is_negative_price": false }
  ]
}
```

### 3.5 `GET /api/market/stats`
Scalar market KPIs (F11/F13). Powers KPI cards. No params.

**Response**
```json
{
  "price_mean_eur_mwh": 67.58,
  "neg_hours": 224,
  "neg_hours_pct": 5.1,
  "daily_spread_eur_mwh": 88.9,
  "weekday_trough": { "hour": 13, "price_eur_mwh": 49.7 },
  "weekday_peak":   { "hour": 20, "price_eur_mwh": 110.3 },
  "imbalance_mean_eur_mwh": 73.6,
  "imbalance_std_eur_mwh": 311.5,
  "imbalance_min_eur_mwh": -5734.0,
  "imbalance_max_eur_mwh": 15000.0
}
```

### 3.6 `GET /api/value/stack`
The **live** value engine (F15–F18). Recomputes per `(scenario, deg_cost)` — this is the interactive moment. Powers **ValueStack** + **SurplusCounter**.

| Query | Type | Default | Range |
|---|---|---|---|
| `scenario` | `Scenario` | `actual` | |
| `deg_cost` | number (€/MWh) | `50.0` | `0..200` |

**Response** (real values, `actual` @ deg_cost 50)
```json
{
  "scenario": "actual",
  "deg_cost_eur_mwh": 50.0,
  "streams": {
    "smart_charging_eur": 3084.98,
    "neg_absorption_eur": 361.86,
    "arbitrage_eur": 4274.73,
    "fcr_eur": null,
    "degradation_eur": 2081.63
  },
  "net_total_eur": 5639.95,
  "per_vehicle_eur": 22.56,
  "surplus_mwh": 24.88,
  "benchmarks": { "french_eur_per_ev": 74, "agora_2030_eur_per_ev": 500 }
}
```

**Units & semantics (important for the FE):**
- **`streams.*` and `net_total_eur` are FLEET-level, annualised €** (the whole 250-vehicle fleet, ×365/182-days). Use them for the stacked-bar **ValueStack**.
- **`per_vehicle_eur`** = `net_total_eur / 250` — the per-EV headline. Use it for the headline number and benchmark comparison.
- The streams are **disjoint and additive**: `net_total = smart_charging + neg_absorption + arbitrage − degradation (+ fcr)`. `smart_charging` is the saving from shifting charging to cheaper non-negative hours; `neg_absorption` is the bonus from being *paid* to charge at negative prices. Their sum is the total V1G saving (≈ €13.79/EV/yr → the doc's "≈€13/EV/yr" anchor).
- `degradation_eur` is a **positive cost**, already subtracted in `net_total_eur` (don't subtract it again).
- `fcr_eur` is `null` (deferred — needs regelleistung.net pricing). Render as "not yet included," not zero.
- `surplus_mwh` = annualised energy absorbed at negative prices (the **SurplusCounter** mission metric).

**Live-slider behaviour the FE drives** (verified): `actual`→`depot` lifts `per_vehicle_eur` from **€22.56 → €89.06**; raising `deg_cost` shrinks arbitrage (€25→€27.49, €50→€22.56, €120→€15.13/EV/yr). Validation anchors (`actual`, deg_cost 50): total V1G ≈ €13/EV/yr, net arbitrage ≈ €9/EV/yr.

### 3.7 `GET /api/geography`
Regional / postal distribution (F8). Powers **GeographyPanel**. No params.

**Response**
```json
{
  "regions": [
    { "region": "Frankfurt core", "sessions": 4844, "vehicles": 250, "kw": 0.0, "share": 0.71 },
    { "region": "Offenbach/E",    "sessions": 588,  "vehicles": 171, "kw": 0.0, "share": 0.086 },
    { "region": "Wiesbaden/W",    "sessions": 589,  "vehicles": 173, "kw": 0.0, "share": 0.086 },
    { "region": "Other",          "sessions": 0, "vehicles": 0, "kw": 0.0, "share": 0.0 }
  ],
  "top_postal_codes": [
    { "postal_code": 60313, "sessions": 0, "vehicles": 0, "kw": 0.0 }
  ]
}
```

---

## 4. Role-scoped endpoints (the two user types)

### 4.1 `GET /api/me`
Reports the active persona so the FE can pick its shell, labels, and headline metric.

| Query | Type | Default |
|---|---|---|
| `role` | `Role` | `fleet` |

(Also accepts `X-User-Role` header; query param wins.)

**Response**
```json
{
  "role": "bkv",
  "label": "Grid / BKV buyer",
  "available_roles": ["bkv", "fleet"],
  "headline_metric": "firm_mw",
  "default_scenario": "actual"
}
```

### 4.2 `GET /api/dashboard/bkv` — buyer / grid view
One call that composes everything the **BKV** view needs (firm capacity vs lot, reliability premium, procurement, surplus). Leads with **firm MW** and **imbalance-risk avoided**.

| Query | Type | Default |
|---|---|---|
| `scenario` | `Scenario` | `actual` |

**Response**
```json
{
  "role": "bkv",
  "scenario": "actual",
  "headline": { "metric": "firm_mw", "value": 0.15, "unit": "MW" },
  "firm_capacity": {
    "lot_mw": 1.0,
    "firm_pctl": 0.10,
    "firm_peak_mw": 0.15,
    "profile": [ { "hour": 9, "p10_mw": 0.15, "p50_mw": 0.22, "mean_mw": 0.23, "p90_mw": 0.34 } ]
  },
  "procurement": {
    "procurable_firm_mw": 0.15,
    "lots_fillable": 0,
    "pct_time_pool_ge_1mw": 0.0,
    "surplus_absorbed_mwh": 0.0
  },
  "reliability": {
    "imbalance_mean_eur_mwh": 73.6,
    "imbalance_std_eur_mwh": 311.5,
    "imbalance_max_eur_mwh": 15000.0,
    "note": "A firmer pool avoids exposure to imbalance-price spikes; firmness = the P10 grade."
  }
}
```

### 4.3 `GET /api/dashboard/fleet` — seller / fleet view
One call that composes everything the **fleet operator** needs (value stack net of degradation, €/vehicle, guaranteed departure SoC). Leads with **€/vehicle** and the **SoC guarantee**.

| Query | Type | Default | Range |
|---|---|---|---|
| `scenario` | `Scenario` | `actual` | |
| `deg_cost` | number | `50.0` | `0..200` |

**Response**
```json
{
  "role": "fleet",
  "scenario": "actual",
  "deg_cost_eur_mwh": 50.0,
  "headline": { "metric": "eur_per_vehicle", "value": 13.0, "unit": "€/EV/yr" },
  "value_stack": {
    "streams": {
      "smart_charging_eur": 0.0,
      "neg_absorption_eur": 0.0,
      "arbitrage_eur": 0.0,
      "fcr_eur": null,
      "degradation_eur": 0.0
    },
    "net_total_eur": 0.0,
    "per_vehicle_eur": 13.0,
    "surplus_mwh": 0.0,
    "benchmarks": { "french_eur_per_ev": 74, "agora_2030_eur_per_ev": 500 }
  },
  "fleet": {
    "fleet_size": 250,
    "v2g_able_vehicles": 213,
    "guaranteed_departure_soc_pct": 30.0,
    "soc_guarantee_note": "Vehicles are never discharged below RESERVE_SOC, so departure SoC is guaranteed ≥ 30%."
  }
}
```

---

## 5. Health (ops, not for UI)

| Path | Returns |
|---|---|
| `GET /health` | `{ "status": "ok" }` (liveness) |
| `GET /ready` | `{ "status": "ok"\|"degraded", "checks": { "database": "ok", "cache": "ok" } }`, `503` if degraded |

---

## 6. Suggested FE composition (single dashboard, two views)

Top-level **ViewToggle** switches `role` (`bkv` ↔ `fleet`); a persistent **ScenarioSlider** drives `scenario` and a **DegCost input** drives `deg_cost`. On any change, refetch.

| Component | Endpoint(s) | Shown to |
|---|---|---|
| ScenarioSlider | `/api/scenario/presets` (labels) | both |
| FirmCapacityChart (P10/50/mean/P90 band + 1 MW lot line) | `/api/dashboard/bkv` → `firm_capacity` (or `/api/pool/profile`) | BKV-led |
| ReliabilityPanel (imbalance-risk avoided) | `/api/dashboard/bkv` → `reliability` | BKV-led |
| ProcurementCard (procurable MW, lots fillable, % time ≥1 MW) | `/api/dashboard/bkv` → `procurement` | BKV-led |
| ValueStack (stacked streams, net of degradation) | `/api/dashboard/fleet` → `value_stack` (or `/api/value/stack`) | Fleet-led |
| PerVehicleHeadline + benchmark markers | `/api/dashboard/fleet` → `headline` + `value_stack.benchmarks` | Fleet-led |
| SoCGuaranteeBadge | `/api/dashboard/fleet` → `fleet` | Fleet-led |
| SurplusCounter | `value_stack.surplus_mwh` / `procurement.surplus_absorbed_mwh` | both |
| GeographyPanel | `/api/geography` | both |
| MarketKPIs / PriceChart | `/api/market/stats`, `/api/market/prices` | both |

**State:** keep `role`, `scenario`, `degCost` in top-level state; everything else derives from fetches keyed on those three. No client-side routing needed (one screen). Always render `actual` context when showing `depot` (honesty rule, F19).

---

## 7. Definition of done (contract level)

The FE can: toggle **BKV ↔ Fleet**, drag **Actual ↔ Depot**, adjust **DEG_COST**, and watch **firm MW**, the **value stack (net of degradation, €/vehicle)**, and the **surplus** recompute live — against real Frankfurt fleet data and real SMARD prices. The `/api/dashboard/{role}` endpoints make each view a single fetch.
