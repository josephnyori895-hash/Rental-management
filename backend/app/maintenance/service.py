"""
RENTAL OS — Maintenance Service
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.maintenance import MaintenanceTicket, TicketStatus
from app.models.property import Unit, Property
from app.models.tenant import Tenant
from app.models.business import User


async def create_ticket(
    session: AsyncSession,
    business_id: UUID,
    data: dict,
    reported_by: UUID | None = None,
) -> dict:
    ticket = MaintenanceTicket(
        business_id=business_id,
        property_id=UUID(data["property_id"]),
        unit_id=UUID(data["unit_id"]) if data.get("unit_id") else None,
        tenant_id=UUID(data["tenant_id"]) if data.get("tenant_id") else None,
        reported_by=reported_by,
        title=data["title"],
        description=data.get("description"),
        category=data.get("category", "other"),
        priority=data.get("priority", "medium"),
        tenant_visible=data.get("tenant_visible", True),
    )
    session.add(ticket)
    await session.flush()
    return await _ticket_to_dict(session, ticket)


async def get_tickets(
    session: AsyncSession,
    business_id: UUID,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    property_id: UUID | None = None,
    assigned_to: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    q = select(MaintenanceTicket).where(MaintenanceTicket.business_id == business_id)
    if status:
        q = q.where(MaintenanceTicket.status == status)
    if priority:
        q = q.where(MaintenanceTicket.priority == priority)
    if category:
        q = q.where(MaintenanceTicket.category == category)
    if property_id:
        q = q.where(MaintenanceTicket.property_id == property_id)
    if assigned_to:
        q = q.where(MaintenanceTicket.assigned_to == assigned_to)
    
    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.scalar(count_q)) or 0
    
    q = q.order_by(MaintenanceTicket.created_at.desc()).offset(offset).limit(limit)
    rows = (await session.scalars(q)).all()
    
    result = []
    for t in rows:
        result.append(await _ticket_to_dict(session, t))
    return result, total


async def get_ticket_detail(session: AsyncSession, business_id: UUID, ticket_id: UUID) -> dict | None:
    t = await session.scalar(
        select(MaintenanceTicket).where(
            MaintenanceTicket.id == ticket_id,
            MaintenanceTicket.business_id == business_id,
        )
    )
    if not t:
        return None
    return await _ticket_to_dict(session, t)


async def update_ticket(
    session: AsyncSession,
    business_id: UUID,
    ticket_id: UUID,
    data: dict,
) -> dict | None:
    t = await session.scalar(
        select(MaintenanceTicket).where(
            MaintenanceTicket.id == ticket_id,
            MaintenanceTicket.business_id == business_id,
        )
    )
    if not t:
        return None
    
    for field in ("status", "priority", "assigned_to", "title", "description",
                  "category", "estimated_cost", "actual_cost", "vendor_name",
                  "vendor_phone", "resolution_notes", "tenant_visible"):
        if field in data:
            setattr(t, field, data[field])
    
    if data.get("status") in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value):
        t.resolved_at = datetime.now(timezone.utc)
    
    await session.flush()
    return await _ticket_to_dict(session, t)


async def _ticket_to_dict(session: AsyncSession, t: MaintenanceTicket) -> dict:
    unit = await session.get(Unit, t.unit_id) if t.unit_id else None
    prop = await session.get(Property, t.property_id) if t.property_id else None
    tenant = await session.get(Tenant, t.tenant_id) if t.tenant_id else None
    assignee = await session.get(User, t.assigned_to) if t.assigned_to else None
    
    return {
        "id": str(t.id),
        "property_id": str(t.property_id),
        "property_name": prop.name if prop else None,
        "unit_id": str(t.unit_id) if t.unit_id else None,
        "unit_number": unit.unit_number if unit else None,
        "tenant_id": str(t.tenant_id) if t.tenant_id else None,
        "tenant_name": tenant.full_name if tenant else None,
        "reported_by": str(t.reported_by) if t.reported_by else None,
        "assigned_to": str(t.assigned_to) if t.assigned_to else None,
        "assigned_name": assignee.full_name if assignee else None,
        "title": t.title,
        "description": t.description,
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "estimated_cost": float(t.estimated_cost) if t.estimated_cost else None,
        "actual_cost": float(t.actual_cost) if t.actual_cost else None,
        "vendor_name": t.vendor_name,
        "vendor_phone": t.vendor_phone,
        "resolution_notes": t.resolution_notes,
        "resolved_at": str(t.resolved_at) if t.resolved_at else None,
        "tenant_visible": t.tenant_visible,
        "created_at": str(t.created_at),
        "updated_at": str(t.updated_at),
    }
