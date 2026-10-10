"""
RENTAL OS — Properties (Hostels) Router
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
from sqlalchemy import select, func
from datetime import date

from app.api.deps import SessionDep, get_current_user
from app.models.business import User
from app.models.property import Property, Unit
from app.models.tenant import Tenant
from app.models.lease import Lease
from app.models.billing import Invoice, InvoiceStatus
from app.properties.schemas import PropertyLayoutUpdate, PropertyOut, UnitOut, UnitRoomOut

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[PropertyOut])
async def list_properties(
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """List the business's hostels / properties."""
    rows = (
        await session.scalars(
            select(Property).where(
                Property.business_id == user.business_id,
                Property.is_deleted.is_(False),
            )
        )
    ).all()
    return rows


@router.get("/{property_id}/rooms", response_model=list[UnitRoomOut])
async def list_rooms(
    property_id: str,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """
    Building view: every unit enriched with tenant + lease + rent status so the
    UI can render a lit-window floor plan (red=unpaid, amber=partial,
    green=paid, blue=overpaid, slate=vacant).
    """
    units = (
        await session.scalars(
            select(Unit).where(
                Unit.property_id == property_id, Unit.is_deleted.is_(False)
            )
        )
    ).all()

    out = []
    for u in units:
        room: dict = {
            "id": str(u.id),
            "unit_number": u.unit_number,
            "unit_type": u.unit_type,
            "status": u.status,
            "monthly_rent": float(u.monthly_rent),
            "max_occupants": u.max_occupants,
            "tenant_name": None,
            "tenant_phone": None,
            "tenant_id": None,
            "lease_start": None,
            "lease_end": None,
            "duration_months": None,
            "condition_notes": None,
            "invoice_status": None,
            "invoice_balance": 0.0,
            "total_paid": 0.0,
            "rent_light": "vacant",
        }

        # Active lease for this unit
        lease = await session.scalar(
            select(Lease).where(
                Lease.unit_id == u.id,
                Lease.status == "active",
            ).order_by(Lease.start_date.desc()).limit(1)
        )
        if lease:
            tenant = await session.get(Tenant, lease.tenant_id)
            room["tenant_id"] = str(tenant.id) if tenant else None
            room["tenant_name"] = tenant.full_name if tenant else None
            room["tenant_phone"] = tenant.phone or tenant.mpesa_phone if tenant else None
            room["lease_start"] = str(lease.start_date)
            room["lease_end"] = str(lease.end_date) if lease.end_date else None
            room["condition_notes"] = lease.notes
            # duration stayed in months
            start = lease.start_date
            months = (date.today().year - start.year) * 12 + (date.today().month - start.month)
            room["duration_months"] = max(months, 0)

        # Latest invoice for this unit
        inv = await session.scalar(
            select(Invoice).where(
                Invoice.unit_id == u.id,
            ).order_by(Invoice.period_start.desc().nullslast()).limit(1)
        )
        if inv:
            room["invoice_status"] = inv.status
            room["invoice_balance"] = float(inv.balance)
            # total paid across all invoices for this unit (sum of paid_amount)
            total = await session.scalar(
                select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                    Invoice.unit_id == u.id,
                )
            )
            room["total_paid"] = float(total or 0)

        # Determine the "light" colour
        if u.status != "occupied":
            room["rent_light"] = "vacant"
        elif inv is None:
            room["rent_light"] = "paid"
        elif inv.status == InvoiceStatus.PAID.value:
            # overpaid if tenant paid more than billed
            room["rent_light"] = "overpaid" if room["total_paid"] > (float(inv.amount) + 0.001) else "paid"
        elif inv.status in ("partial", "partially_paid"):
            room["rent_light"] = "partial"
        else:  # pending / overdue / sent
            room["rent_light"] = "unpaid"

        out.append(room)

    return out


@router.get("/{property_id}/units", response_model=list[UnitOut])
async def list_units(
    property_id: str,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """List rooms within a hostel."""
    rows = (
        await session.scalars(
            select(Unit).where(
                Unit.property_id == property_id, Unit.is_deleted.is_(False)
            )
        )
    ).all()
    return rows


@router.get("/{property_id}/layout")
async def get_property_layout(
    property_id: UUID,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Return saved visual layout metadata without changing rental records."""
    prop = await session.scalar(
        select(Property).where(
            Property.id == property_id,
            Property.business_id == user.business_id,
            Property.is_deleted.is_(False),
        )
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"property_id": str(prop.id), "layout_config": prop.layout_config}


@router.put("/{property_id}/layout")
async def save_property_layout(
    property_id: UUID,
    payload: PropertyLayoutUpdate,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Save validated face/floor/section mappings for units owned by this property."""
    prop = await session.scalar(
        select(Property).where(
            Property.id == property_id,
            Property.business_id == user.business_id,
            Property.is_deleted.is_(False),
        )
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    unit_ids = [placement.unit_id for placement in payload.layout_config.placements]
    if unit_ids:
        owned_units = set(
            (await session.scalars(
                select(Unit.id).where(
                    Unit.id.in_(unit_ids),
                    Unit.property_id == prop.id,
                    Unit.business_id == user.business_id,
                    Unit.is_deleted.is_(False),
                )
            )).all()
        )
        if owned_units != set(unit_ids):
            raise HTTPException(
                status_code=422,
                detail="Every placed unit must belong to this property and business",
            )

    prop.layout_config = payload.layout_config.model_dump(mode="json")
    await session.flush()
    return {"property_id": str(prop.id), "layout_config": prop.layout_config}
