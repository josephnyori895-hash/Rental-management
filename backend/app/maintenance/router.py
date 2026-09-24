"""
RENTAL OS — Maintenance Router
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, get_current_user, require_roles
from app.maintenance import service
from app.models.business import User

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post("/tickets", status_code=201)
async def create_ticket(
    data: dict,
    session: SessionDep,
    user: User = Depends(require_roles("owner", "manager", "agent")),
):
    """Create a new maintenance ticket."""
    try:
        return await service.create_ticket(session, user.business_id, data, reported_by=user.id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/tickets")
async def list_tickets(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    property_id: str | None = Query(None),
    assigned_to: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """List maintenance tickets with filters."""
    pid = UUID(property_id) if property_id else None
    at = UUID(assigned_to) if assigned_to else None
    tickets, total = await service.get_tickets(
        session, user.business_id, status, priority, category, pid, at, limit, offset,
    )
    return {"tickets": tickets, "total": total, "limit": limit, "offset": offset}


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    """Get full ticket detail."""
    t = await service.get_ticket_detail(session, user.business_id, UUID(ticket_id))
    if not t:
        raise HTTPException(404, detail="Ticket not found")
    return t


@router.patch("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    data: dict,
    session: SessionDep,
    user: User = Depends(require_roles("owner", "manager", "agent")),
):
    """Update ticket status, assignment, or details."""
    t = await service.update_ticket(session, user.business_id, UUID(ticket_id), data)
    if not t:
        raise HTTPException(404, detail="Ticket not found")
    return t


@router.get("/summary")
async def maintenance_summary(
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    """Aggregated counts for dashboard widgets."""
    from sqlalchemy import func, select
    from app.models.maintenance import MaintenanceTicket
    
    biz_id = user.business_id
    
    total = await session.scalar(
        select(func.count()).select_from(MaintenanceTicket).where(MaintenanceTicket.business_id == biz_id)
    ) or 0
    open_count = await session.scalar(
        select(func.count()).select_from(MaintenanceTicket).where(
            MaintenanceTicket.business_id == biz_id,
            MaintenanceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    ) or 0
    resolved_count = await session.scalar(
        select(func.count()).select_from(MaintenanceTicket).where(
            MaintenanceTicket.business_id == biz_id,
            MaintenanceTicket.status.in_(["resolved", "closed"]),
        )
    ) or 0
    urgent_count = await session.scalar(
        select(func.count()).select_from(MaintenanceTicket).where(
            MaintenanceTicket.business_id == biz_id,
            MaintenanceTicket.priority == "urgent",
            MaintenanceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    ) or 0
    
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved_count,
        "urgent": urgent_count,
    }
