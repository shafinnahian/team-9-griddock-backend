"""Value router (F15-F18) — the live engine driving the demo slider."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core import params
from app.schemas import ValueStackResponse
from app.services import value_service
from app.services._query import validate_deg_cost, validate_scenario

router = APIRouter(prefix="/api/value", tags=["value"])


@router.get("/stack", response_model=ValueStackResponse)
def stack(
    scenario: str = Query("actual"),
    deg_cost: float = Query(params.DEG_COST),
) -> dict:
    validate_scenario(scenario)
    validate_deg_cost(deg_cost)
    return value_service.compute_value_stack(scenario, deg_cost)
