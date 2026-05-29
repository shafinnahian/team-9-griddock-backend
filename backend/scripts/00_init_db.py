"""00 — create all tables (Calc-Spec §1). Idempotent: safe to re-run.

Run inside the api container (numeric module names can't use ``-m``):
    docker compose exec api python scripts/00_init_db.py
"""

from __future__ import annotations

import pathlib
import sys

# Make the backend root (parent of app/ and scripts/) importable when this
# file is executed directly: `python scripts/00_init_db.py`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import Base  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    tables = sorted(inspect(engine).get_table_names())
    print(f"create_all done. Tables present ({len(tables)}): {', '.join(tables)}")
    expected = {
        "dim_vehicle",
        "fact_session",
        "fact_pool_15min",
        "fact_market_15min",
        "agg_hourly_profile",
    }
    missing = expected - set(tables)
    if missing:
        raise SystemExit(f"ERROR: missing tables after create_all: {sorted(missing)}")
    print("All 5 expected tables exist.")


if __name__ == "__main__":
    main()
