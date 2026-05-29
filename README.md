# GridDock Backend

V2G marketplace analytics API for the Rhein-Main EV fleet demo. FastAPI + PostgreSQL,
implementing the feature set `F1–F19` from `docs/infra_guideline/`.

Frontend docs:
- **[API_GUIDELINE.md](API_GUIDELINE.md)** — the HTTP contract (endpoints, shapes, conventions).
- **[FE_INTEGRATION_GUIDE.md](FE_INTEGRATION_GUIDE.md)** — how to wire it up: real payloads, the
  two user types, state model, a typed client, error handling, TS types, component map.

## Architecture

Three layers (`routers → services → models`). Routers never touch SQL; services
never touch HTTP. Static tables (sessions, market, pool, profile — both `actual`
and `depot` scenarios) are precomputed by ETL; scenario/`deg_cost`-dependent value
(F15/16/18) is computed live on a warm in-memory cache so the demo sliders stay
interactive.

```
griddock-backend/
├── docker-compose.yml          # db (postgres:16) + api (fastapi)
├── API_GUIDELINE.md            # the FE-facing HTTP contract
├── data/                       # CSVs (mounted into the api container)
│   ├── source/nml_ev_sessions.md       # supply source (→ NML_ev_sessions.csv)
│   ├── *_Quarterhour.csv / *_Hour.csv  # SMARD market data
│   └── _golden_*.csv                   # prebuilt artifacts (validation oracles)
└── backend/
    ├── Dockerfile · requirements.txt
    ├── app/
    │   ├── main.py             # FastAPI app, CORS, request-id, error handlers, startup cache warm
    │   ├── db.py · models.py   # engine/session + the 5 ORM tables
    │   ├── cache.py            # warm pandas read-cache (loaded at startup)
    │   ├── schemas.py          # Pydantic response shapes (the contract)
    │   ├── errors.py           # RFC 9457 error envelope
    │   ├── core/params.py      # ALL model constants (Calc-Spec §0)
    │   ├── core/config.py      # env config (pydantic-settings, fail-fast)
    │   ├── routers/            # health, scenario, pool, market, value, geography
    │   └── services/           # pool, market, value (F15-18), geo, scenario, _query
    └── scripts/                # ETL 00→05 + run_all (00b prep, 01-04 build, 05 validate)
```

## Run

```bash
docker compose up -d db                          # 1. Postgres (waits healthy)
docker compose up -d --build api                 # 2. build + start the API
docker compose exec api python scripts/run_all.py  # 3. load + validate all tables
# API: http://localhost:8000   ·   OpenAPI docs: http://localhost:8000/docs
```

Step 3 runs the full ETL (`00_init_db → 00b prep → 01–04 build → 05 validate`) and
asserts the Calc-Spec §5 checklist (**19/19**) against the golden artifacts. It is
idempotent — safe to re-run. To create tables only (no data): `python scripts/00_init_db.py`.

Quick verify:
```bash
curl localhost:8000/ready                                   # {"database":"ok","cache":"ok"}
curl "localhost:8000/api/value/stack?scenario=depot&deg_cost=50"
```

## API surface

All under `/api`, JSON, snake_case. Full contract + response shapes in
[API_GUIDELINE.md](API_GUIDELINE.md). Live now:

| Method · Path | Query | Feature |
|---|---|---|
| `GET /api/scenario/presets` | — | F19 dwell presets |
| `GET /api/pool/profile` | `scenario` | F6/F7 firm-capacity curve vs 1 MW lot |
| `GET /api/pool/timeseries` | `scenario, from, to` | F6 15-min supply series |
| `GET /api/market/prices` | `from, to` | F11/F12 price + renewable series |
| `GET /api/market/stats` | — | F11/F13 scalar market KPIs |
| `GET /api/value/stack` | `scenario, deg_cost` | F15–F18 live value engine |
| `GET /api/geography` | — | F8 regional / postal distribution |
| `GET /api/me` | `role` | active persona (also reads `X-User-Role`) |
| `GET /api/dashboard/bkv` | `scenario` | buyer/grid view (firm MW, reliability, procurement) |
| `GET /api/dashboard/fleet` | `scenario, deg_cost` | seller view (value stack, €/EV, SoC guarantee) |
| `GET /health`, `GET /ready` | — | liveness / readiness (db + cache) |

The two user types (`bkv` / `fleet`) are role-scoped composition views over the
shared pool — no auth; role is in the path. See API_GUIDELINE.md §4.

Run tests: `docker compose exec api python -m pytest tests/ -q` (24 tests).

## Build status

- [x] **Phase 1** — scaffold, config, models, `create_all`, health.
- [x] **Phase 2** — ETL `00→05` (all tables, both scenarios; **19/19 §5 checks pass**).
- [x] **Phase 3** — services + the 7 shared analytics endpoints (live value engine + warm cache).
- [x] **Phase 4** — role layer (`/me`, `/dashboard/{bkv,fleet}`) + pytest suite (**24 tests pass**).

Backend complete. All 10 API endpoints + health live; frontend can be built against API_GUIDELINE.md.

## Notes

- Demo-grade: no auth, `create_all` (no Alembic), permissive CORS. User types
  (`bkv` / `fleet`) are role-scoped views over one shared pool, not authenticated
  accounts — see API_GUIDELINE.md §0.
- `data/` is mounted read-write (not `:ro`) because the ETL prep step derives
  `NML_ev_sessions.csv` from `data/source/nml_ev_sessions.md`.
- The SMARD grid has 17,468 intervals, not 17,472: the **2024-03-31 DST**
  spring-forward removes 4 fifteen-minute slots. The pool builder maps timestamps
  via `searchsorted` on the real grid (gap-safe), not arithmetic indices.
- `/api/value/stack` `streams` are **fleet-level annualised €**; `per_vehicle_eur`
  is the per-EV headline. `(smart_charging + neg_absorption)/250` ≈ €13.79/EV/yr.
