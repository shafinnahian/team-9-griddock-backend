# GridDock Backend

V2G marketplace analytics API for the Rhein-Main EV fleet demo. FastAPI + PostgreSQL,
implementing the feature set `F1–F19` from `docs/infra_guideline/`.

The HTTP contract the frontend codes against is **[API_GUIDELINE.md](API_GUIDELINE.md)**.

## Architecture

Three layers (`routers → services → models`). Routers never touch SQL; services
never touch HTTP. Static tables (sessions, market, pool, profile — both `actual`
and `depot` scenarios) are precomputed by ETL; scenario/`deg_cost`-dependent value
(F15/16/18) is computed live so the demo sliders stay interactive.

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
    │   ├── main.py             # FastAPI app, CORS, request-id, error handlers
    │   ├── db.py · models.py   # engine/session + the 5 ORM tables
    │   ├── core/params.py      # ALL model constants (Calc-Spec §0)
    │   ├── core/config.py      # env config (pydantic-settings, fail-fast)
    │   ├── errors.py           # RFC 9457 error envelope
    │   └── routers/ services/  # added in Phases 3–4
    └── scripts/                # ETL (00→05), added in Phase 2
```

## Run

```bash
docker compose up -d db          # start Postgres (waits healthy)
docker compose up -d --build api # build + start the API
docker compose exec api python scripts/00_init_db.py   # create the 5 tables
# API: http://localhost:8000   ·   OpenAPI docs: http://localhost:8000/docs
```

Health checks: `GET /health` (liveness), `GET /ready` (readiness incl. DB).

## Build status

- [x] **Phase 1** — scaffold, config, models, `create_all`, health.
- [x] **Phase 2** — ETL `00→05` (all tables, both scenarios; **19/19 §5 checks pass**).
- [ ] **Phase 3** — services + shared analytics endpoints.
- [ ] **Phase 4** — role layer (`/me`, `/dashboard/{bkv,fleet}`) + tests.

Load the data: `docker compose exec api python scripts/run_all.py`

## Notes

- Demo-grade: no auth, `create_all` (no Alembic), permissive CORS. User types
  (`bkv` / `fleet`) are role-scoped views over one shared pool, not authenticated
  accounts — see API_GUIDELINE.md §0.
- `data/` is mounted read-write (not `:ro`) because the ETL prep step derives
  `NML_ev_sessions.csv` from `data/source/nml_ev_sessions.md`.
