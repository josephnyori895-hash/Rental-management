"""
RENTAL OS — Dashboard Router
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, get_current_user
from app.dashboard import schemas, service
from app.models.business import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/owner/board", response_model=service.OwnerBoard)
async def owner_board(
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Owner business console — animated hostel/room board + money totals."""
    return await service.get_owner_board(session, user.business_id)


@router.get("/owner/metrics", response_model=schemas.OwnerMetrics)
async def owner_metrics(
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Headline KPIs for the Business Console telemetry row."""
    return await service.get_owner_metrics(session, user.business_id)


@router.get("/owner/performance-history", response_model=list[schemas.PerformancePoint])
async def owner_performance_history(
    months: int = 6,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Collected-vs-arrears trend for the console chart (default: last 6 months)."""
    return await service.get_performance_history(session, user.business_id, months)
