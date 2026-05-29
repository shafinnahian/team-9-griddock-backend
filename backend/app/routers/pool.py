"""Pool router (F6, F7)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import ProfileResponse
from app.services import pool_service

router = APIRouter(prefix="/api/pool", tags=["pool"])


@router.get("/profile", response_model=ProfileResponse)
def profile(scenario: str = Query("actual")) -> dict:
    return pool_service.get_profile(scenario)


@router.get("/timeseries")
def timeseries(
    scenario: str = Query("actual"),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
) -> dict:
    return pool_service.get_timeseries(scenario, from_, to)
