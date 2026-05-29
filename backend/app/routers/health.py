"""Liveness and readiness probes (ops only — not for the UI)."""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.cache import cache
from app.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict[str, object]:
    """Readiness: dependencies (database) are reachable."""
    checks: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001 - report degraded, never leak the error
        checks["database"] = "error"

    checks["cache"] = "ok" if cache.loaded else "cold"

    ok = checks.get("database") == "ok" and checks.get("cache") == "ok"
    response.status_code = 200 if ok else 503
    return {"status": "ok" if ok else "degraded", "checks": checks}
