"""Role layer — the two user types (API_GUIDELINE.md §4).

Demo-grade: no authentication. Role is expressed in the path
(/dashboard/{bkv,fleet}); /me also accepts ?role= or the X-User-Role header.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query

from app.core import params
from app.schemas import BkvDashboardResponse, FleetDashboardResponse, MeResponse
from app.services import dashboard_service
from app.services._query import validate_deg_cost, validate_role

router = APIRouter(prefix="/api", tags=["role"])


@router.get("/me", response_model=MeResponse)
def me(
    role: str | None = Query(None),
    x_user_role: str | None = Header(None),
) -> dict:
    chosen = role or x_user_role or "fleet"
    validate_role(chosen)
    return dashboard_service.get_me(chosen)


@router.get("/dashboard/bkv", response_model=BkvDashboardResponse)
def dashboard_bkv(scenario: str = Query("actual")) -> dict:
    return dashboard_service.get_bkv_dashboard(scenario)


@router.get("/dashboard/fleet", response_model=FleetDashboardResponse)
def dashboard_fleet(
    scenario: str = Query("actual"),
    deg_cost: float = Query(params.DEG_COST),
) -> dict:
    validate_deg_cost(deg_cost)
    return dashboard_service.get_fleet_dashboard(scenario, deg_cost)
