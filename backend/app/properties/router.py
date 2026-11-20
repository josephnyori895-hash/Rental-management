"""
RENTAL OS — Properties (Hostels) Router
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import SessionDep, get_current_user, require_roles
from app.models.billing import Invoice, InvoiceStatus
from app.models.business import User
from app.models.lease import Lease
from app.models.property import Property, Unit
from app.models.tenant import Tenant
from app.properties.schemas import (
    PropertyCreate,
    PropertyLayoutOut,
    PropertyLayoutUpdate,
    PropertyOut,
    UnitCreate,
    UnitOut,
    UnitRoomOut,
)

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("", response_model=PropertyOut)
async def create_property(
    data: PropertyCreate,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Create a property for the current business."""
    prop = Property(
        business_id=user.business_id,
        name=data.name,
        address=data.address,
        property_type=data.property_type,
        description=data.description,
    )
    session.add(prop)
    await session.commit()
    await session.refresh(prop)
    return prop


@router.post("/{property_id}/units", response_model=UnitOut)
async def create_unit(
    property_id: UUID,
    data: UnitCreate,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Add a rentable unit to an existing property."""
    prop = await owned_property(property_id, user, session)

    unit = Unit(
        business_id=user.business_id,
        property_id=prop.id,
        unit_number=data.unit_number,
        unit_type=data.unit_type,
        monthly_rent=Decimal(str(data.monthly_rent)),
        deposit_amount=Decimal(str(data.deposit_amount)),
        max_occupants=data.max_occupants,
        description=data.description,
    )
    session.add(unit)
    await session.commit()
    await session.refresh(unit)
    return unit


class CaretakerAssignRequest(BaseModel):
    user_id: UUID | None = None


async def owned_property(property_id: UUID, user: User, session) -> Property:
    """Resolve a property inside the caller's business, or 404.

    Tenant isolation lives here rather than in each handler: a property outside
    the caller's business is reported as missing, so ids from another operator
    cannot be probed for existence.
    """
    prop = await session.scalar(
        select(Property).where(
            Property.id == property_id,
            Property.business_id == user.business_id,
            Property.is_deleted.is_(False),
        )
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


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
    property_id: UUID,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """
    Building view: every unit enriched with tenant + lease + rent status so the
    UI can render a lit-window floor plan (red=unpaid, amber=partial,
    green=paid, blue=overpaid, slate=vacant).
    """
    await owned_property(property_id, user, session)
    today = date.today()
    units = (
        await session.scalars(
            select(Unit).where(
                Unit.property_id == property_id,
                Unit.business_id == user.business_id,
                Unit.is_deleted.is_(False),
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
                Lease.business_id == user.business_id,
                Lease.status == "active",
            ).order_by(Lease.start_date.desc()).limit(1)
        )
        if lease:
            tenant = await session.get(Tenant, lease.tenant_id)
            if tenant is not None and tenant.business_id != user.business_id:
                tenant = None
            # Nothing lease-derived is published unless the tenant passes the
            # ownership check: dates, duration and free-text notes belong to
            # whoever owns the lease, and a mismatched row must render blank
            # rather than half-filled.
            if tenant is not None:
                room["tenant_id"] = str(tenant.id)
                room["tenant_name"] = tenant.full_name
                room["tenant_phone"] = tenant.phone or tenant.mpesa_phone
                room["lease_start"] = str(lease.start_date)
                room["lease_end"] = str(lease.end_date) if lease.end_date else None
                room["condition_notes"] = lease.notes
                # duration stayed in months
                start = lease.start_date
                months = (today.year - start.year) * 12 + (today.month - start.month)
                room["duration_months"] = max(months, 0)

        # Latest invoice for this unit
        inv = await session.scalar(
            select(Invoice).where(
                Invoice.unit_id == u.id,
                Invoice.business_id == user.business_id,
            ).order_by(Invoice.period_start.desc().nullslast()).limit(1)
        )
        if inv:
            room["invoice_status"] = inv.status
            room["invoice_balance"] = float(inv.balance)
            # total paid across all invoices for this unit (sum of paid_amount)
            total = await session.scalar(
                select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                    Invoice.unit_id == u.id,
                    Invoice.business_id == user.business_id,
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
    property_id: UUID,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """List rooms within a hostel."""
    await owned_property(property_id, user, session)
    rows = (
        await session.scalars(
            select(Unit).where(
                Unit.property_id == property_id,
                Unit.business_id == user.business_id,
                Unit.is_deleted.is_(False),
            )
        )
    ).all()
    return rows


@router.patch("/{property_id}/caretaker")
async def assign_caretaker(
    property_id: UUID,
    data: CaretakerAssignRequest,
    session: SessionDep,
    user: User = Depends(require_roles("owner", "manager")),
):
    """Assign — or clear — the caretaker responsible for one property.

    With several caretakers on different buildings, this link is what makes
    ticket and renewal alerts reach the right person. Passing `user_id: null`
    unassigns, which routes that property's alerts back to the owner.
    """
    prop = await owned_property(property_id, user, session)

    if data.user_id is None:
        prop.manager_id = None
    else:
        staff = await session.get(User, data.user_id)
        if not staff or staff.business_id != user.business_id or not staff.is_active:
            raise HTTPException(status_code=404, detail="Staff member not found")
        if staff.role not in ("agent", "manager"):
            raise HTTPException(
                status_code=400,
                detail="Only a caretaker or manager can be assigned to a property",
            )
        prop.manager_id = staff.id

    await session.commit()
    return {
        "property_id": str(prop.id),
        "caretaker_id": str(prop.manager_id) if prop.manager_id else None,
    }


@router.get("/{property_id}/layout", response_model=PropertyLayoutOut)
async def get_property_layout(
    property_id: UUID,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Return saved visual layout metadata without changing rental records."""
    prop = await owned_property(property_id, user, session)
    return {"property_id": prop.id, "layout_config": prop.layout_config}


@router.put("/{property_id}/layout", response_model=PropertyLayoutOut)
async def save_property_layout(
    property_id: UUID,
    payload: PropertyLayoutUpdate,
    user: User = Depends(get_current_user),
    session: SessionDep = None,
):
    """Save validated face/floor/section mappings for units owned by this property."""
    prop = await owned_property(property_id, user, session)

    unit_ids = [placement.unit_id for placement in payload.layout_config.placements]
    unit_ids.extend(
        space.rentable_unit_id
        for section in payload.layout_config.sections
        for level in section.levels
        for space in level.spaces
        if space.rentable_unit_id is not None
    )
    if unit_ids:
        owned_units = set(
            (await session.scalars(
                select(Unit.id).where(
                    Unit.id.in_(set(unit_ids)),
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
