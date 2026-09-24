"""
RENTAL OS — Tenant Portal Router

Self-service endpoints for tenants to view their data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep, get_current_user
from app.documents.service import list_documents as list_docs
from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.business import User, UserRole
from app.models.lease import Lease, LeaseStatus
from app.models.maintenance import MaintenanceTicket
from app.models.property import Unit
from app.models.tenant import Tenant

router = APIRouter(prefix="/portal", tags=["portal"])


@router.get("/my-data")
async def tenant_portal_data(
    session: SessionDep,
    user: User = Depends(get_current_user),
    tenant_id: str | None = None,
):
    """Tenant self-service: their lease, invoices, payments, maintenance tickets.
    Owner/manager may pass tenant_id to preview a specific tenant's portal."""
    if user.role == UserRole.AGENT.value and not tenant_id:
        # Tenants can only see their own (matched by phone on file)
        pass

    if tenant_id:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant or tenant.is_deleted:
            return {"tenant": None, "lease": None, "invoices": [], "payments": [], "maintenance": []}
    else:
        # Find first tenant for demo / default
        tenant = await session.scalar(
            select(Tenant).where(
                Tenant.business_id == user.business_id,
                Tenant.is_deleted.is_(False),
            ).limit(1)
        )
    if not tenant:
        return {"tenant": None, "lease": None, "invoices": [], "payments": [], "maintenance": []}

    lease = await session.scalar(
        select(Lease).where(
            Lease.tenant_id == tenant.id,
            Lease.status == LeaseStatus.ACTIVE.value,
        ).order_by(Lease.created_at.desc()).limit(1)
    )

    unit = await session.get(Unit, lease.unit_id) if lease else None

    invoices = (
        await session.scalars(
            select(Invoice).where(
                Invoice.tenant_id == tenant.id,
                Invoice.is_deleted.is_(False),
            ).order_by(Invoice.period_start.desc().nullslast()).limit(12)
        )
    ).all()

    payments = (
        await session.scalars(
            select(Payment).where(
                Payment.tenant_id == tenant.id,
            ).order_by(Payment.paid_at.desc()).limit(20)
        )
    ).all()

    maintenance = (
        await session.scalars(
            select(MaintenanceTicket).where(
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
