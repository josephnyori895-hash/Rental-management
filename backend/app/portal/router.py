"""
RENTAL OS — Tenant Portal Router

Owner-facing preview of a tenant's portal: lease, invoices, payments,
maintenance and documents, scoped to the owner's business.

The route is mounted owner-only. Tenant self-service — a tenant authenticating
as themselves — is not implemented here and would require its own credential
flow and its own mount, not a query parameter.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep, get_current_user
from app.documents.service import list_documents as list_docs
from app.models.billing import Invoice, Payment
from app.models.business import User
from app.models.lease import Lease, LeaseStatus
from app.models.maintenance import MaintenanceTicket
from app.models.property import Unit
from app.models.tenant import Tenant

router = APIRouter(prefix="/portal", tags=["portal"])


def _as_uuid(value: str) -> uuid.UUID | None:
    """Parse a path/query id, treating malformed input as "not found".

    A 500 on garbage input is both a bad answer and a hint that the id was
    parsed somewhere unexpected; 404 is the only correct response for an id that
    cannot resolve to a record this caller may see.
    """
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


async def _portal_tenant(session, user, tenant_id: str | None) -> Tenant | None:
    """Resolve the tenant this caller may inspect, or None.

    Ownership is decided here and only here. `tenant_id` is a request value, so
    it is compared against the caller's business rather than trusted.
    """
    if tenant_id is None:
        return await session.scalar(
            select(Tenant)
            .where(
                Tenant.business_id == user.business_id,
                Tenant.is_deleted.is_(False),
            )
            .order_by(Tenant.created_at)
            .limit(1)
        )

    parsed = _as_uuid(tenant_id)
    if parsed is None:
        return None

    return await session.scalar(
        select(Tenant).where(
            Tenant.id == parsed,
            Tenant.business_id == user.business_id,
            Tenant.is_deleted.is_(False),
        )
    )


@router.get("/my-data")
async def tenant_portal_data(
    session: SessionDep,
    user: User = Depends(get_current_user),
    tenant_id: str | None = None,
):
    """One tenant's portal view, assembled for the owner console.

    This route is mounted owner-only, so it is a preview: an owner opens a
    tenant's portal to see what that tenant sees. Two rules follow from that and
    are enforced here rather than trusted from the URL:

    - a `tenant_id` belonging to another business is not found, never served,
      and is reported as 404 so its existence is not confirmed;
    - every record assembled below is filtered by the owner's business as well
      as by tenant, so a tenant row with a foreign invoice, payment or document
      attached cannot leak that record through this view.
    """
    tenant = await _portal_tenant(session, user, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    lease = await session.scalar(
        select(Lease).where(
            Lease.business_id == user.business_id,
            Lease.tenant_id == tenant.id,
            Lease.status == LeaseStatus.ACTIVE.value,
        ).order_by(Lease.created_at.desc()).limit(1)
    )

    unit = await session.get(Unit, lease.unit_id) if lease else None
    if unit is not None and unit.business_id != user.business_id:
        unit = None

    invoices = (
        await session.scalars(
            select(Invoice).where(
                Invoice.business_id == user.business_id,
                Invoice.tenant_id == tenant.id,
            ).order_by(Invoice.period_start.desc().nullslast()).limit(12)
        )
    ).all()

    payments = (
        await session.scalars(
            select(Payment).where(
                Payment.business_id == user.business_id,
                Payment.tenant_id == tenant.id,
            ).order_by(Payment.paid_at.desc()).limit(20)
        )
    ).all()

    maintenance = (
        await session.scalars(
            select(MaintenanceTicket).where(
                MaintenanceTicket.business_id == user.business_id,
                MaintenanceTicket.tenant_id == tenant.id,
                MaintenanceTicket.tenant_visible == True,
            ).order_by(MaintenanceTicket.created_at.desc()).limit(10)
        )
    ).all()

    return {
        "tenant": {
            "id": str(tenant.id),
            "full_name": tenant.full_name,
            "phone": tenant.phone,
            "mpesa_phone": tenant.mpesa_phone,
            "unit_number": unit.unit_number if unit else None,
            "unit_id": str(unit.id) if unit else None,
        },
        "lease": {
            "id": str(lease.id) if lease else None,
            "rent_amount": float(lease.rent_amount) if lease else 0,
            "start_date": str(lease.start_date) if lease else None,
            "status": lease.status if lease else None,
            "tenant_signed": bool(lease.tenant_signed_at) if lease else False,
            "owner_signed": bool(lease.owner_signed_at) if lease else False,
        } if lease else None,
        "invoices": [
            {
                "id": str(inv.id),
                "type": inv.invoice_type,
                "amount": float(inv.amount),
                "paid_amount": float(inv.paid_amount or 0),
                "balance": float(inv.balance or 0),
                "status": inv.status,
                "due_date": str(inv.due_date) if inv.due_date else None,
                "period": f"{inv.period_start} - {inv.period_end}" if inv.period_start and inv.period_end else None,
            }
            for inv in invoices
        ],
        "payments": [
            {
                "id": str(p.id),
                "amount": float(p.amount),
                "method": p.method,
                "reference": p.reference,
                "paid_at": str(p.paid_at),
            }
            for p in payments
        ],
        "maintenance": [
            {
                "id": str(m.id),
                "title": m.title,
                "category": m.category,
                "priority": m.priority,
                "status": m.status,
                "created_at": str(m.created_at),
            }
            for m in maintenance
        ],
        "documents": [
            {
                "id": str(d.id),
                "original_name": d.original_name,
                "category": d.category,
                "file_size": d.file_size,
            }
            for d in await list_docs(session, user.business_id, tenant_id=tenant.id)
        ],
        "summary": {
            "total_invoiced": sum(float(inv.amount) for inv in invoices),
            "total_paid": sum(float(inv.paid_amount or 0) for inv in invoices),
            "balance_due": sum(float(inv.balance or 0) for inv in invoices),
        },
    }
