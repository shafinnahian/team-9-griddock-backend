# GridDock — Frontend Integration Guide

**Audience:** an AI (or developer) building the GridDock frontend against this backend.
This is the *implementation* companion to **`API_GUIDELINE.md`** (the contract). Where
the API guideline defines shapes, this guide tells you **how to wire them up**: payloads,
real responses, the two user types, state model, a typed client, error handling, and a
component-by-component build plan. Every JSON block below is a **real response** captured
from the running API.

> TL;DR mental model: **one shared battery pool**, viewed from **two sides** of a
> marketplace. The whole UI is driven by **three pieces of state** — `role` (bkv|fleet),
> `scenario` (actual|depot), `degCost` (€/MWh) — and every change re-fetches.

---

## 1. The product in one paragraph

GridDock is a B2B V2G ("vehicle-to-grid") marketplace demo. A fleet of 250 EVs in the
Rhein-Main region has idle battery capacity; the grid (via a BKV / utility) will pay for
that flexibility. The backend turns 6 months of real fleet + SMARD market data into:
a **firm-capacity curve** (what can be sold), a **value stack** (what it earns, net of
battery degradation), and a **dwell scenario lever** that shows how much more is unlocked
if vehicles stay plugged like a depot. The demo's punch is **two live interactions**:
toggling **BKV ↔ Fleet** and dragging **Actual ↔ Depot** (plus a `DEG_COST` input).

---

## 2. Setup & global conventions

### 2.1 Base URL & client
- Base URL: `http://localhost:8000`, all API paths under `/api`.
- Put it in an env var: `VITE_API_URL=http://localhost:8000`.
- CORS is wide open (`*`) — no credentials needed for the demo.
- Interactive API explorer (great for poking): `http://localhost:8000/docs`.

### 2.2 Conventions you MUST respect
| Topic | Rule | Why it bites you if ignored |
|---|---|---|
| Field casing | **`snake_case`** everywhere (`available_mw`, `per_vehicle_eur`) | Don't camelCase keys when reading responses. |
| Timestamps | **Naive local German time**, ISO without zone: `"2024-06-06T08:00:00"` | **Do NOT `new Date()`-convert to UTC** — it'll shift the data by 1–2h. Treat as wall-clock strings; if charting, parse as local/naive. |
| Units | suffix-encoded: `_mw`, `_mwh`, `_eur`, `_eur_mwh`, `_pct` | A value `0.15` in `_mw` is 0.15 **MW**, not kW. |
| Data window | Everything is bounded to **2024-01-01 → 2024-06-30**. | Date pickers should clamp to this range; out-of-range requests are clamped server-side. |
| Empty ≠ error | A valid query with no rows → `200` + empty `points: []` | Render "no data in range," not an error. |
| `from` param | `from` is a JS/Python keyword — it's a **query string param**, not a body field | In the client, pass it as a string key `"from"`. |
| Request id | Every response has header `X-Request-Id` | Log it; surface it in error toasts for debugging. |

### 2.3 Enums & defaults
```ts
type Scenario = "actual" | "depot";   // default "actual"
type Role     = "bkv" | "fleet";      // default "fleet"
// deg_cost: number €/MWh, default 50, allowed 0..200 (LFP ≈ 25–30)
```

---

## 3. The two user types (READ THIS — it's the core of the UI)

Both roles read the **same pool**, but lead with different metrics and endpoints. There is
**no login**: the frontend picks a role (a top toggle) and calls that role's dashboard
path. You may also send header `X-User-Role: bkv|fleet` on shared calls (advisory only).

| | **BKV / Grid buyer** (`bkv`) | **Fleet operator** (`fleet`) |
|---|---|---|
| Who | Utility / Balancing-Responsible-Party buying flexibility (e.g. Mainova) | EV fleet/depot operator selling capacity |
| Side of market | **Demand / buyer** | **Supply / seller** |
| Headline metric | **Firm MW** vs the 1 MW market lot (`headline.metric = "firm_mw"`) | **€/vehicle/yr** (`headline.metric = "eur_per_vehicle"`) |
| One-call endpoint | `GET /api/dashboard/bkv?scenario` | `GET /api/dashboard/fleet?scenario&deg_cost` |
| Leads with | Firm capacity curve, reliability premium (imbalance-risk avoided), procurable MW | Value stack net of degradation, €/EV, guaranteed departure SoC |
| Cares about | "Can this pool fill a 1 MW lot? How firm/reliable is it?" | "What does my fleet earn? Is my battery protected?" |
| `deg_cost` relevant? | No (buyer view) | **Yes** — drives the value stack |
| Sub-data it shows | `firm_capacity`, `procurement`, `reliability` | `value_stack`, `fleet` (size, v2g count, SoC guarantee) |

**Design implication:** build **one dashboard** with a **ViewToggle** at the top. Switching
role swaps which `/api/dashboard/{role}` you call and which panels lead. The Scenario slider
and (for fleet) the DEG_COST input are shared chrome. The two role dashboards are *bundles*
— you usually don't need the individual §6 endpoints unless you want extra charts.

---

## 4. State model & when to re-fetch

Keep exactly three values in top-level state:

```ts
const [role, setRole]         = useState<Role>("fleet");
const [scenario, setScenario] = useState<Scenario>("actual");
const [degCost, setDegCost]   = useState<number>(50);
```

| State change | Re-fetch | Notes |
|---|---|---|
| `role` | the other `/api/dashboard/{role}` | swap leading panels |
| `scenario` | current role dashboard (both roles use it) | the "honesty slider" — always show `actual` context near `depot` |
| `degCost` | `fleet` dashboard / `value/stack` only | bkv view ignores it |

Static-for-the-session calls (fetch once, cache forever): `/api/scenario/presets`,
`/api/market/stats`, `/api/geography`, `/api/me`. Responses are deterministic per query —
safe to cache aggressively (e.g. React Query `staleTime: Infinity`).

---

## 5. Recommended client (typed fetch + React Query)

### 5.1 Tiny typed fetch wrapper
```ts
// lib/api.ts
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface ProblemDetail {       // RFC 9457 error envelope
  type: string; title: string; status: number; detail: string;
  instance: string; request_id: string;
  errors?: { field: string; message: string; code: string }[];
}
export class ApiError extends Error {
  constructor(public status: number, public problem: ProblemDetail | null) {
    super(problem?.detail ?? `API error ${status}`);
  }
}

export async function api<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(BASE + path);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const problem = (await res.json().catch(() => null)) as ProblemDetail | null;
    throw new ApiError(res.status, problem);
  }
  return res.json() as Promise<T>;
}
```

### 5.2 React Query hooks (one per concern)
```ts
// queryKey includes the state that drives the fetch -> automatic refetch on change
export const useBkvDashboard   = (scenario: Scenario) =>
  useQuery({ queryKey: ["bkv", scenario],            queryFn: () => api<BkvDashboard>("/api/dashboard/bkv", { scenario }) });
export const useFleetDashboard = (scenario: Scenario, degCost: number) =>
  useQuery({ queryKey: ["fleet", scenario, degCost], queryFn: () => api<FleetDashboard>("/api/dashboard/fleet", { scenario, deg_cost: degCost }) });
export const useMarketStats    = () =>
  useQuery({ queryKey: ["market-stats"], queryFn: () => api<MarketStats>("/api/market/stats"), staleTime: Infinity });
export const useGeography      = () =>
  useQuery({ queryKey: ["geography"],    queryFn: () => api<Geography>("/api/geography"),       staleTime: Infinity });
export const usePresets        = () =>
  useQuery({ queryKey: ["presets"],      queryFn: () => api<Presets>("/api/scenario/presets"),  staleTime: Infinity });

// Debounce the DEG_COST slider so dragging doesn't fire a request per pixel:
const debouncedDeg = useDebounce(degCost, 150);
const fleet = useFleetDashboard(scenario, debouncedDeg);
```

---

## 6. Endpoint reference (with real payloads)

Each entry: **purpose · params · real response · field semantics · FE usage.**

### 6.1 `GET /api/me` — active persona
**Params:** `role` (query, optional) or header `X-User-Role`; default `fleet`.
**Use:** decide which shell/labels/headline to render. Optional — you can also just hardcode
the two roles in the FE since they're fixed.
```json
{ "role": "bkv", "label": "Grid / BKV buyer", "available_roles": ["bkv", "fleet"],
  "headline_metric": "firm_mw", "default_scenario": "actual" }
```

### 6.2 `GET /api/scenario/presets` — the slider labels (F19)
**Params:** none. **Use:** label the Actual↔Depot slider; show `desc`/`dwell_assumption` as
tooltips. **Always display the `actual` floor alongside `depot` (honesty rule).**
```json
{
  "actual": { "label": "Data as-is", "desc": "Sessions exactly as logged — a conservative availability floor.",
              "dwell_assumption": "Plugged window = logged session only." },
  "depot":  { "label": "Realistic depot", "desc": "Assumes depot vehicles stay plugged overnight — climbs toward benchmarks.",
              "dwell_assumption": "Each V2G-able session extended to a minimum 12h window at ending SoC." }
}
```

### 6.3 `GET /api/pool/profile` — firm-capacity curve (F6/F7)
**Params:** `scenario` (default `actual`). **Use:** the **FirmCapacityChart** — 24 hourly
buckets, plot a P10–P90 band with P50/mean lines, and a horizontal **`lot_mw` (1.0)** line.
```json
{
  "scenario": "actual", "lot_mw": 1.0, "firm_pctl": 0.1, "firm_peak_mw": 0.1526,
  "profile": [
    { "hour": 0, "p10_mw": 0.0, "p50_mw": 0.0193, "mean_mw": 0.0252, "p90_mw": 0.0558 },
    { "hour": 1, "p10_mw": 0.0, "p50_mw": 0.0084, "mean_mw": 0.0132, "p90_mw": 0.038  }
    /* … 24 buckets, hour 0..23 … */
  ]
}
```
**Semantics:** `p10_mw` = **firm** capacity (available ~90% of the time → the grade you sell).
`p90_mw` = optimistic ceiling (do *not* sell it). `firm_peak_mw` = max P10 across the day
(the headline firm MW). **Chart tip:** Recharts `ComposedChart` — `Area` between p10/p90,
`Line` for p50/mean, `ReferenceLine y={lot_mw}`.

### 6.4 `GET /api/pool/timeseries` — raw 15-min supply (F6)
**Params:** `scenario`, `from`, `to` (ISO; default full window). **Use:** drill-down area
chart. **Request a bounded range** (e.g. a day/week) — the full window is ~17.5k points.
```json
{ "scenario": "actual", "from": "2024-06-06T08:00:00", "to": "2024-06-06T08:30:00",
  "points": [
    { "ts": "2024-06-06T08:00:00", "available_mw": 0.3883, "available_mwh": 0.3463, "n_vehicles": 23 },
    { "ts": "2024-06-06T08:15:00", "available_mw": 0.4037, "available_mwh": 0.4324, "n_vehicles": 24 }
  ] }
```

### 6.5 `GET /api/market/prices` — price & renewable series (F11/F12)
**Params:** `from`, `to`. **Use:** price line chart; shade `is_negative_price` intervals;
optional PV/residual-load overlays. Bound the range as above.
```json
{ "from": "2024-01-01T00:00:00", "to": "2024-01-01T00:30:00",
  "points": [
    { "ts": "2024-01-01T00:00:00", "price_eur_mwh": 0.1, "residual_load_mwh": 1242.75, "pv_mwh": 0.75, "is_negative_price": false }
  ] }
```
> Any numeric field may be `null` (missing SMARD value) — guard before plotting.

### 6.6 `GET /api/market/stats` — scalar KPIs (F11/F13)
**Params:** none. **Use:** KPI cards; the imbalance std/max feed the BKV "reliability
premium" story.
```json
{ "price_mean_eur_mwh": 67.58, "neg_hours": 224, "neg_hours_pct": 5.1, "daily_spread_eur_mwh": 88.9,
  "weekday_trough": { "hour": 13, "price_eur_mwh": 49.7 }, "weekday_peak": { "hour": 20, "price_eur_mwh": 110.3 },
  "imbalance_mean_eur_mwh": 73.6, "imbalance_std_eur_mwh": 311.5, "imbalance_min_eur_mwh": -5734.5, "imbalance_max_eur_mwh": 15000.0 }
```

### 6.7 `GET /api/value/stack` — the live value engine (F15–F18)
**Params:** `scenario` (default `actual`), `deg_cost` (default `50`, range `0..200`).
**Use:** **ValueStack** (stacked bar) + **SurplusCounter** + per-EV headline. This is the
endpoint that recomputes as the sliders move.
```json
{
  "scenario": "actual", "deg_cost_eur_mwh": 50.0,
  "streams": { "smart_charging_eur": 3084.98, "neg_absorption_eur": 361.86,
               "arbitrage_eur": 4274.73, "fcr_eur": null, "degradation_eur": 2081.63 },
  "net_total_eur": 5639.95, "per_vehicle_eur": 22.56, "surplus_mwh": 24.88,
  "benchmarks": { "french_eur_per_ev": 74.0, "agora_2030_eur_per_ev": 500.0 }
}
```
**CRITICAL semantics (get these right or the chart lies):**
- `streams.*` and `net_total_eur` are **FLEET-level annualised €** (all 250 vehicles).
- `per_vehicle_eur` = `net_total_eur / 250` — the **per-EV headline** (use for benchmarks).
- Streams are **disjoint & additive**: `net_total = smart_charging + neg_absorption + arbitrage − degradation (+ fcr)`.
- `degradation_eur` is a **positive cost already subtracted** — render it as a downward/red
  segment; **don't subtract it again**.
- `fcr_eur` is `null` (deferred). Render as "not yet included," **not** 0.
- `neg_absorption_eur` (paid to charge at negative prices) + `smart_charging_eur` = the total
  V1G saving (≈ €13.79/EV/yr).
- `surplus_mwh` = annualised energy absorbed at negative prices → the **mission counter**.
- `benchmarks` → draw reference markers on the per-EV headline (French €74, Agora €500).

### 6.8 `GET /api/geography` — distribution (F8)
**Params:** none. **Use:** region bar chart / simple map; `share` is a fraction (0.71 = 71%).
`kw` is summed connection power.
```json
{ "regions": [
    { "region": "Frankfurt core", "sessions": 4844, "vehicles": 250, "kw": 110422.5, "share": 0.71 },
    { "region": "Offenbach/E", "sessions": 588, "vehicles": 171, "kw": 7557.4, "share": 0.086 },
    { "region": "Wiesbaden/W", "sessions": 589, "vehicles": 173, "kw": 7437.4, "share": 0.086 },
    { "region": "Other", "sessions": 805, "vehicles": 178, "kw": 10198.9, "share": 0.118 } ],
  "top_postal_codes": [ { "postal_code": 60388, "sessions": 294, "vehicles": 170, "kw": 6926.3 } ] }
```

---

## 7. Role dashboards (the bundles you'll mostly use)

### 7.1 `GET /api/dashboard/bkv` — buyer/grid view
**Params:** `scenario`. Composes firm capacity + procurement + reliability into one call.
```json
{
  "role": "bkv", "scenario": "actual",
  "headline": { "metric": "firm_mw", "value": 0.1526, "unit": "MW" },
  "firm_capacity": { "lot_mw": 1.0, "firm_pctl": 0.1, "firm_peak_mw": 0.1526,
    "profile": [ { "hour": 9, "p10_mw": 0.1526, "p50_mw": 0.2238, "mean_mw": 0.2331, "p90_mw": 0.3376 } /* …24 */ ] },
  "procurement": { "procurable_firm_mw": 0.1526, "lots_fillable": 0, "pct_time_pool_ge_1mw": 0.0, "surplus_absorbed_mwh": 24.88 },
  "reliability": { "imbalance_mean_eur_mwh": 73.6, "imbalance_std_eur_mwh": 311.5, "imbalance_max_eur_mwh": 15000.0,
                   "note": "A firmer pool avoids exposure to imbalance-price spikes; firmness = the P10 grade." }
}
```
**Render:** headline firm-MW card; FirmCapacityChart from `firm_capacity` (same shape as 6.3);
ProcurementCard (`lots_fillable`, `pct_time_pool_ge_1mw`, `surplus_absorbed_mwh`);
ReliabilityPanel (imbalance stats + `note`). **Story:** at `actual`, firm = 0.15 MW (0 lots
fillable). Drag to `depot` → firm jumps to ~0.44 MW — visibly closer to the 1 MW lot.

### 7.2 `GET /api/dashboard/fleet` — seller/fleet view
**Params:** `scenario`, `deg_cost`. Composes the value stack + fleet trust metrics.
```json
{
  "role": "fleet", "scenario": "actual", "deg_cost_eur_mwh": 50.0,
  "headline": { "metric": "eur_per_vehicle", "value": 22.56, "unit": "€/EV/yr" },
  "value_stack": { "streams": { "smart_charging_eur": 3084.98, "neg_absorption_eur": 361.86,
      "arbitrage_eur": 4274.73, "fcr_eur": null, "degradation_eur": 2081.63 },
    "net_total_eur": 5639.95, "per_vehicle_eur": 22.56, "surplus_mwh": 24.88,
    "benchmarks": { "french_eur_per_ev": 74.0, "agora_2030_eur_per_ev": 500.0 } },
  "fleet": { "fleet_size": 250, "v2g_able_vehicles": 250, "guaranteed_departure_soc_pct": 30.0,
             "soc_guarantee_note": "Vehicles are never discharged below RESERVE_SOC, so departure SoC is guaranteed ≥ 30%." }
}
```
**Render:** €/EV headline with benchmark markers; ValueStack from `value_stack.streams`
(see 6.7 semantics); SurplusCounter from `value_stack.surplus_mwh`; SoCGuaranteeBadge from
`fleet`. **Story (the slider):** `actual`@50 = €22.56/EV → `depot`@50 = €89.06/EV; raising
`deg_cost` shrinks the stack (€25→€27.49, €120→€15.13).

---

## 8. Error handling

All errors use the RFC 9457 envelope:
```json
{ "type": "https://griddock.local/errors/validation-error", "title": "Validation Error",
  "status": 422, "detail": "deg_cost must be between 0.0 and 200.0", "instance": "/api/value/stack",
  "request_id": "req_d31a2a53c2a3",
  "errors": [ { "field": "deg_cost", "message": "got 999.0", "code": "OUT_OF_RANGE" } ] }
```

| Status | Meaning | FE action |
|---|---|---|
| `422` | invalid `scenario`/`role`/`deg_cost`, or `from >= to` | Inline hint on the offending control (read `errors[].field`). Shouldn't happen if you clamp inputs. |
| `400` | unparseable date | "Invalid date." |
| `404` | unknown path | dev error — fix the path. |
| `5xx` | server error | toast "Something went wrong," show `request_id`, allow retry. |
| network `Failed to fetch` | API down/CORS | "Cannot reach GridDock API — is it running on :8000?" |

```ts
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 422 && e.problem?.errors?.length)
      return e.problem.errors.map(f => `${f.field}: ${f.message}`).join("; ");
    if (e.status >= 500) return `Server error (${e.problem?.request_id ?? "?"}). Please retry.`;
    return e.problem?.detail ?? `Request failed (${e.status}).`;
  }
  if (e instanceof TypeError) return "Cannot reach the GridDock API on :8000.";
  return "Unexpected error.";
}
```
**Retry policy:** retry `5xx` (max 3, backoff); **never** retry `4xx`. Always render a
loading skeleton (not a blank screen) and an empty-state for `points: []`.

---

## 9. Ready-to-paste TypeScript types

```ts
export type Scenario = "actual" | "depot";
export type Role = "bkv" | "fleet";

export interface ProfileBucket { hour: number; p10_mw: number; p50_mw: number; mean_mw: number; p90_mw: number; }
export interface Presets { actual: PresetInfo; depot: PresetInfo; }
export interface PresetInfo { label: string; desc: string; dwell_assumption: string; }

export interface PoolProfile { scenario: Scenario; lot_mw: number; firm_pctl: number; firm_peak_mw: number; profile: ProfileBucket[]; }
export interface PoolPoint { ts: string; available_mw: number; available_mwh: number; n_vehicles: number; }
export interface PoolTimeseries { scenario: Scenario; from: string; to: string; points: PoolPoint[]; }

export interface MarketPoint { ts: string; price_eur_mwh: number | null; residual_load_mwh: number | null; pv_mwh: number | null; is_negative_price: boolean; }
export interface MarketPrices { from: string; to: string; points: MarketPoint[]; }
export interface HourPrice { hour: number; price_eur_mwh: number; }
export interface MarketStats {
  price_mean_eur_mwh: number; neg_hours: number; neg_hours_pct: number; daily_spread_eur_mwh: number;
  weekday_trough: HourPrice; weekday_peak: HourPrice;
  imbalance_mean_eur_mwh: number; imbalance_std_eur_mwh: number; imbalance_min_eur_mwh: number; imbalance_max_eur_mwh: number;
}

export interface ValueStreams { smart_charging_eur: number; neg_absorption_eur: number; arbitrage_eur: number; fcr_eur: number | null; degradation_eur: number; }
export interface Benchmarks { french_eur_per_ev: number; agora_2030_eur_per_ev: number; }
export interface ValueStack { scenario: Scenario; deg_cost_eur_mwh: number; streams: ValueStreams; net_total_eur: number; per_vehicle_eur: number; surplus_mwh: number; benchmarks: Benchmarks; }

export interface RegionRow { region: string; sessions: number; vehicles: number; kw: number; share: number; }
export interface PostalRow { postal_code: number; sessions: number; vehicles: number; kw: number; }
export interface Geography { regions: RegionRow[]; top_postal_codes: PostalRow[]; }

export interface Me { role: Role; label: string; available_roles: Role[]; headline_metric: string; default_scenario: Scenario; }
export interface Headline { metric: string; value: number; unit: string; }

export interface BkvDashboard {
  role: "bkv"; scenario: Scenario; headline: Headline;
  firm_capacity: { lot_mw: number; firm_pctl: number; firm_peak_mw: number; profile: ProfileBucket[]; };
  procurement: { procurable_firm_mw: number; lots_fillable: number; pct_time_pool_ge_1mw: number; surplus_absorbed_mwh: number; };
  reliability: { imbalance_mean_eur_mwh: number; imbalance_std_eur_mwh: number; imbalance_max_eur_mwh: number; note: string; };
}
export interface FleetDashboard {
  role: "fleet"; scenario: Scenario; deg_cost_eur_mwh: number; headline: Headline;
  value_stack: { streams: ValueStreams; net_total_eur: number; per_vehicle_eur: number; surplus_mwh: number; benchmarks: Benchmarks; };
  fleet: { fleet_size: number; v2g_able_vehicles: number; guaranteed_departure_soc_pct: number; soc_guarantee_note: string; };
}
```

---

## 10. Component → endpoint map & suggested layout

```
App (state: role, scenario, degCost)
├── TopBar
│   ├── ViewToggle (role)              -> swaps dashboard endpoint + leading panels
│   ├── ScenarioSlider (scenario)      <- /api/scenario/presets   (labels/tooltips)
│   └── DegCostInput (degCost)         (visible in fleet view only; debounce 150ms)
│
├── if role === "bkv":  data <- /api/dashboard/bkv?scenario
│   ├── HeadlineCard          <- headline (firm_mw, MW)
│   ├── FirmCapacityChart     <- firm_capacity.profile + lot_mw line
│   ├── ProcurementCard       <- procurement
│   └── ReliabilityPanel      <- reliability (+ /api/market/stats for extra KPIs)
│
├── if role === "fleet": data <- /api/dashboard/fleet?scenario&deg_cost
│   ├── HeadlineCard          <- headline (eur_per_vehicle) + benchmarks markers
│   ├── ValueStack            <- value_stack.streams (stacked bar; degradation negative)
│   ├── SurplusCounter        <- value_stack.surplus_mwh
│   └── SoCGuaranteeBadge     <- fleet.guaranteed_departure_soc_pct
│
└── Shared (both roles, fetch once)
    ├── GeographyPanel        <- /api/geography
    └── MarketStrip           <- /api/market/stats (+ /api/market/prices for a chart)
```

---

## 11. Performance & gotchas checklist

- [ ] Don't UTC-convert timestamps; treat as naive wall-clock strings.
- [ ] Bound `from`/`to` for `pool/timeseries` & `market/prices` (full window ≈ 17.5k pts).
- [ ] Debounce the `deg_cost` slider (~150ms) before fetching.
- [ ] Cache static endpoints (`presets`, `market/stats`, `geography`, `me`) with long staleTime.
- [ ] Treat `value_stack.streams.*` as **fleet** €; use `per_vehicle_eur` for the headline.
- [ ] Render `degradation_eur` as an already-subtracted cost; render `fcr_eur: null` as "TBD".
- [ ] Guard `null` numeric fields in market series before charting.
- [ ] Always show the `actual` baseline when displaying `depot` (honesty rule).
- [ ] Loading skeletons on every panel; empty-state for `points: []`; map errors via §8.

---

## 12. The demo moment to nail

A judge toggles **Fleet ⇄ BKV**, drags **Actual → Depot**, and nudges **DEG_COST** — and
watches **firm MW**, the **value stack (net of degradation, €/EV)**, and the **surplus
counter** recompute live against real Frankfurt fleet + SMARD data. Wire the three state
values → the two `/api/dashboard/{role}` calls, keep refetches snappy (cache + debounce),
and that single interaction proves the thesis.
```
actual @ €50  → €22.56 / EV / yr        depot @ €50  → €89.06 / EV / yr
firm 0.15 MW (actual) → 0.44 MW (depot)   vs the 1 MW sellable lot
```
