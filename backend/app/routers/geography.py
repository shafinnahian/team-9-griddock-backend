"""Geography router (F8)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import GeographyResponse
from app.services import geo_service

router = APIRouter(prefix="/api", tags=["geography"])


@router.get("/geography", response_model=GeographyResponse)
def geography() -> dict:
    return geo_service.get_geography()
