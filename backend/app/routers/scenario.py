"""Scenario presets router (F19)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import PresetsResponse
from app.services import scenario_service

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.get("/presets", response_model=PresetsResponse)
def presets() -> dict:
    return scenario_service.get_presets()
