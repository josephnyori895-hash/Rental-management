"""
RENTAL OS — Expenses Router
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, get_current_user, require_roles
from app.expenses import service
from app.models.business import User

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", status_code=201)
async def create_expense(
    data: dict,
    session: SessionDep,
    user: User = Depends(require_roles("owner", "manager")),
):
    """Record an operational expense."""
    try:
        return await service.create_expense(session, user.business_id, data)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("")
async def list_expenses(
    category: str | None = Query(None),
    property_id: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """List expenses with filters."""
    pid = UUID(property_id) if property_id else None
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    expenses, total = await service.get_expenses(session, user.business_id, category, pid, fd, td, limit, offset)
    return {"expenses": expenses, "total": total, "limit": limit, "offset": offset}


@router.get("/summary")
async def expense_summary(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Aggregated expense totals by category."""
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    return await service.get_expense_summary(session, user.business_id, fd, td)
