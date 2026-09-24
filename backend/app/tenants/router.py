"""
RENTAL OS — Tenants Router
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_business, require_roles
from app.models.business import Business, User
from app.models.billing import DepositRefund, Invoice, InvoiceType, Payment
from app.models.lease import Lease
from app.models.property import Unit
from app.models.tenant import Tenant
from app.tenants import service
from app.tenants.schemas import EnrollRequest, EnrollResponse
from sqlalchemy import select

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("")
async def list_tenants(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all tenants in the business with their unit + rent status.
    Uses batched queries to avoid N+1.
    """
    from sqlalchemy import select as sa_select
    from app.models.lease import Lease, LeaseStatus
    from app.models.billing import Invoice, InvoiceType

    # 1) Fetch tenants (paged)
    q = sa_select(Tenant).where(
        Tenant.business_id == business.id, Tenant.is_deleted.is_(False)
    )
    if search:
        q = q.where(Tenant.full_name.ilike(f"%{search}%"))
    q = q.order_by(Tenant.full_name).limit(limit).offset(offset)
    tenants = (await session.scalars(q)).all()
    if not tenants:
        return {"tenants": [], "total": 0}

    tenant_ids = [t.id for t in tenants]

    # 2) Batch fetch active leases per tenant
    lease_rows = await session.execute(
        sa_select(Lease).where(
            Lease.tenant_id.in_(tenant_ids),
            Lease.status == LeaseStatus.ACTIVE.value,
        )
    )
    leases_by_tenant: dict = {}
    for l in lease_rows.scalars().all():
        # keep only the latest lease per tenant
        existing = leases_by_tenant.get(l.tenant_id)
        if existing is None or l.created_at > existing.created_at:
            leases_by_tenant[l.tenant_id] = l

    # 3) Batch fetch units for those leases
    unit_ids = [l.unit_id for l in leases_by_tenant.values()]
    units_by_id: dict = {}
    if unit_ids:
        unit_rows = await session.execute(
            sa_select(Unit).where(Unit.id.in_(unit_ids))
        )
        for u in unit_rows.scalars().all():
            units_by_id[u.id] = u

    # 4) Batch fetch latest rent invoices
    inv_rows = await session.execute(
        sa_select(Invoice).where(
            Invoice.tenant_id.in_(tenant_ids),
            Invoice.invoice_type == InvoiceType.RENT.value,
        ).order_by(Invoice.period_start.desc().nullslast())
    )
    invoices_by_tenant: dict = {}
    for inv in inv_rows.scalars().all():
        if inv.tenant_id not in invoices_by_tenant:
            invoices_by_tenant[inv.tenant_id] = inv

    # 5) Assemble response — zero per-tenant queries
    result = []
    for t in tenants:
        lease = leases_by_tenant.get(t.id)
        unit = units_by_id.get(lease.unit_id) if lease else None
        inv = invoices_by_tenant.get(t.id)
        result.append({
            "id": str(t.id),
            "full_name": t.full_name,
            "phone": t.phone,
            "mpesa_phone": t.mpesa_phone,
            "unit_number": unit.unit_number if unit else None,
            "property_name": None,
            "rent_amount": float(lease.rent_amount) if lease else 0,
            "status": inv.status if inv else "no_lease",
            "balance": float(inv.balance or 0) if inv else 0,
            "due_date": str(inv.due_date) if inv and inv.due_date else None,
        })
    return {"tenants": result, "total": len(result)}


@router.post("/enroll", response_model=EnrollResponse, status_code=201)
async def enroll(
    data: EnrollRequest,
    session: SessionDep,
    actor: User = Depends(require_roles("owner", "manager", "agent")),
):
    """Caretaker/manager/owner enrolls a tenant into a house with M-Pesa phone."""
    try:
        result = await service.enroll_tenant(session, actor, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/{tenant_id}")
async def get_tenant_detail(
    tenant_id: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Full tenant detail: personal info, current lease, unit, payment history."""
    tenant = await session.get(Tenant, uuid.UUID(str(tenant_id)))
    if not tenant or tenant.business_id != business.id or tenant.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Current lease
    lease_q = (
        select(Lease, Unit.unit_number, Unit.monthly_rent)
        .select_from(Lease)
        .join(Unit, Lease.unit_id == Unit.id)
        .where(
            Lease.tenant_id == tenant.id,
            Lease.status == "active",
        )
        .order_by(Lease.created_at.desc())
        .limit(1)
    )
    lease_row = (await session.execute(lease_q)).first()

    # Deposit refund (if any)
    deposit_refund = await session.scalar(
        select(DepositRefund).where(
            DepositRefund.tenant_id == tenant.id,
        ).order_by(DepositRefund.refunded_at.desc()).limit(1)
    )

    # Deposit invoice status
    deposit_inv = await session.scalar(
        select(Invoice).where(
            Invoice.tenant_id == tenant.id,
            Invoice.invoice_type == InvoiceType.DEPOSIT.value,
        ).order_by(Invoice.created_at.desc()).limit(1)
    )

    # All invoices for this tenant
    inv_q = (
        select(
            Invoice.id,
            Invoice.invoice_type,
            Invoice.amount,
            Invoice.paid_amount,
            Invoice.balance,
            Invoice.status,
            Invoice.due_date,
            Invoice.period_start,
            Invoice.period_end,
            Invoice.created_at,
            Unit.unit_number,
        )
        .select_from(Invoice)
        .join(Unit, Invoice.unit_id == Unit.id)
        .where(Invoice.tenant_id == tenant.id)
        .order_by(Invoice.created_at.desc())
    )
    invoices = (await session.execute(inv_q)).all()

    # All payments for this tenant
    pay_q = (
        select(Payment)
        .where(Payment.tenant_id == tenant.id)
        .order_by(Payment.paid_at.desc())
        .limit(50)
    )
    payments = (await session.execute(pay_q)).scalars().all()

    return {
        "id": str(tenant.id),
        "full_name": tenant.full_name,
        "id_number": tenant.id_number,
        "phone": tenant.phone,
        "mpesa_phone": tenant.mpesa_phone,
        "email": tenant.email,
        "emergency_contact_name": tenant.emergency_contact_name,
        "emergency_contact_phone": tenant.emergency_contact_phone,
        "notes": tenant.notes,
        "created_at": str(tenant.created_at) if tenant.created_at else None,
        "current_lease": {
            "id": str(lease_row.Lease.id) if lease_row else None,
            "unit_number": lease_row.unit_number if lease_row else None,
            "monthly_rent": float(lease_row.monthly_rent) if lease_row and lease_row.monthly_rent else 0,
            "deposit_amount": float(lease_row.Lease.deposit_amount) if lease_row and lease_row.Lease.deposit_amount else 0,
            "start_date": str(lease_row.Lease.start_date) if lease_row and lease_row.Lease.start_date else None,
            "duration_months": (
                ((lease_row.Lease.end_date or date.today()).year - lease_row.Lease.start_date.year) * 12
                + ((lease_row.Lease.end_date or date.today()).month - lease_row.Lease.start_date.month)
                if lease_row and lease_row.Lease.start_date else 0
            ),
            "status": lease_row.Lease.status if lease_row else None,
        } if lease_row else None,
        "deposit": ({
            "amount": float(lease_row.Lease.deposit_amount or 0),
            "paid": float(deposit_inv.paid_amount or 0) if deposit_inv else 0,
            "balance": float(deposit_inv.balance or 0) if deposit_inv else float(lease_row.Lease.deposit_amount or 0),
            "status": (
                "refunded" if deposit_refund
                else "paid" if (deposit_inv and (deposit_inv.balance or 0) <= 0)
                else "partial" if (deposit_inv and (deposit_inv.balance or 0) > 0)
                else "pending"
            ),
            "refund": {
                "amount": float(deposit_refund.amount),
                "method": deposit_refund.method,
                "reason": deposit_refund.reason,
                "refunded_at": str(deposit_refund.refunded_at),
            } if deposit_refund else None,
        }) if lease_row else None,
        "invoices": [
            {
                "id": str(inv.id),
                "invoice_type": inv.invoice_type,
                "amount": float(inv.amount),
                "paid_amount": float(inv.paid_amount or 0),
                "balance": float(inv.balance or 0),
                "status": inv.status,
                "due_date": str(inv.due_date) if inv.due_date else None,
                "period": f"{inv.period_start} - {inv.period_end}" if inv.period_start and inv.period_end else None,
                "created_at": str(inv.created_at) if inv.created_at else None,
            }
            for inv in invoices
        ],
        "payments": [
            {
                "id": str(p.id),
                "amount": float(p.amount),
                "method": p.method,
                "reference": p.reference,
                "status": p.status,
                "paid_at": str(p.paid_at),
            }
            for p in payments
        ],
        "total_paid": sum(float(p.amount) for p in payments),
        "total_invoiced": sum(float(inv.amount) for inv in invoices),
    }


@router.post("/{tenant_id}/sign-lease")
async def sign_lease(
    tenant_id: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
    signer: str = "tenant",
):
    """Digitally sign the tenant's active lease (tenant or owner signature)."""
    tenant = await session.get(Tenant, uuid.UUID(tenant_id))
    if not tenant or tenant.business_id != business.id or tenant.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")

    lease = await session.scalar(
        select(Lease).where(
            Lease.tenant_id == tenant.id,
            Lease.status.in_(["pending", "active"]),
        ).order_by(Lease.created_at.desc()).limit(1)
    )
    if not lease:
        raise HTTPException(status_code=404, detail="No active lease found")

    now = datetime.now(timezone.utc)
    if signer == "tenant":
        if lease.tenant_signed_at:
            raise HTTPException(status_code=400, detail="Lease already signed by tenant")
        lease.tenant_signed_at = now
    elif signer == "owner":
        if lease.owner_signed_at:
            raise HTTPException(status_code=400, detail="Lease already signed by owner")
        lease.owner_signed_at = now
    else:
        raise HTTPException(status_code=400, detail="Signer must be 'tenant' or 'owner'")

    # Mark fully signed when both parties have signed
    if lease.tenant_signed_at and lease.owner_signed_at:
        lease.signed_at = now

    await session.commit()
    return {
        "lease_id": str(lease.id),
        "tenant_signed": bool(lease.tenant_signed_at),
        "owner_signed": bool(lease.owner_signed_at),
        "fully_signed": bool(lease.signed_at),
    }
