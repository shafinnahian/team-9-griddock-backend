"""Market router (F11, F12, F13)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import MarketStatsResponse
from app.services import market_service

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/prices")
def prices(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
) -> dict:
    return market_service.get_prices(from_, to)


@router.get("/stats", response_model=MarketStatsResponse)
def stats() -> dict:
    return market_service.get_stats()
