"""
RENTAL OS — Billing Router

- GET /billing/invoices       : list invoices for the business
- GET /billing/invoices/{id}  : single invoice detail
- POST /billing/bills         : create a utility bill (water / wifi / electricity)
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.accounting.service import auto_post_invoice
from app.api.deps import SessionDep, get_current_business
from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.business import Business
from app.models.lease import Lease
from app.models.tenant import Tenant
from app.models.property import Unit
from sqlalchemy import select

router = APIRouter(prefix="/billing", tags=["billing"])


class CreateBillRequest(BaseModel):
    unit_id: str
    bill_type: str  # water | wifi | electricity | other
    amount: float
    description: str | None = None
    due_date: date | None = None


@router.get("/invoices")
async def list_invoices(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all invoices for this business, newest first."""
    q = (
        select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.invoice_type,
            Invoice.amount,
            Invoice.paid_amount,
            Invoice.balance,
            Invoice.status,
            Invoice.due_date,
            Invoice.period_start,
            Invoice.period_end,
            Invoice.created_at,
            Invoice.tenant_id,
            Invoice.unit_id,
            Unit.unit_number,
            Tenant.full_name,
            Tenant.mpesa_phone,
        )
        .select_from(Invoice)
        .join(Unit, Invoice.unit_id == Unit.id)
        .join(Tenant, Invoice.tenant_id == Tenant.id)
        .where(Invoice.business_id == business.id)
        .order_by(Invoice.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status:
        q = q.where(Invoice.status == status)

    rows = (await session.execute(q)).all()
    total = await session.scalar(
        select(Invoice.id)
        .where(Invoice.business_id == business.id)
    )

    return {
        "total": len(rows),
        "invoices": [
            {
                "id": str(r.id),
                "invoice_number": r.invoice_number,
                "invoice_type": r.invoice_type,
                "amount": float(r.amount),
                "paid_amount": float(r.paid_amount or 0),
                "balance": float(r.balance or 0),
                "status": r.status,
                "due_date": str(r.due_date) if r.due_date else None,
                "period_start": str(r.period_start) if r.period_start else None,
                "period_end": str(r.period_end) if r.period_end else None,
                "created_at": str(r.created_at) if r.created_at else None,
                "unit_number": r.unit_number,
                "tenant_name": r.full_name,
                "tenant_phone": r.mpesa_phone,
                "tenant_id": str(r.tenant_id),
                "unit_id": str(r.unit_id),
            }
            for r in rows
        ],
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Get a single invoice with payment history."""
    inv = await session.get(Invoice, uuid.UUID(str(invoice_id)))
    if not inv or inv.business_id != business.id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    unit = await session.get(Unit, inv.unit_id)
    tenant = await session.get(Tenant, inv.tenant_id)

    payments_q = (
        select(Payment)
        .where(Payment.invoice_id == inv.id)
        .order_by(Payment.paid_at.desc())
    )
    payments = (await session.execute(payments_q)).scalars().all()

    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "invoice_type": inv.invoice_type,
        "amount": float(inv.amount),
        "paid_amount": float(inv.paid_amount or 0),
        "balance": float(inv.balance or 0),
        "status": inv.status,
        "due_date": str(inv.due_date) if inv.due_date else None,
        "period_start": str(inv.period_start) if inv.period_start else None,
        "period_end": str(inv.period_end) if inv.period_end else None,
        "unit_number": unit.unit_number if unit else None,
        "tenant_name": tenant.full_name if tenant else None,
        "tenant_phone": tenant.mpesa_phone if tenant else None,
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
    }


@router.post("/bills")
async def create_bill(
    data: CreateBillRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Create a utility bill (water, wifi, electricity) for a unit."""
    unit = await session.get(Unit, uuid.UUID(str(data.unit_id)))
    if not unit or unit.business_id != business.id:
        raise HTTPException(status_code=404, detail="Unit not found")

    if not unit.current_lease_id:
        raise HTTPException(status_code=400, detail="Unit is not occupied")

    lease = await session.get(Lease, unit.current_lease_id)
    if not lease or lease.status != "active":
        raise HTTPException(status_code=400, detail="No active lease")

    invoice = Invoice(
        business_id=business.id,
        lease_id=lease.id,
        tenant_id=lease.tenant_id,
        unit_id=unit.id,
        property_id=unit.property_id,
        invoice_type=data.bill_type,
        amount=Decimal(str(data.amount)),
        paid_amount=Decimal("0"),
        balance=Decimal(str(data.amount)),
        status=InvoiceStatus.PENDING.value,
        due_date=data.due_date,
        description=data.description,
    )
    session.add(invoice)
    await session.commit()

    # Auto-post to general ledger
    try:
        await auto_post_invoice(session, invoice)
    except Exception:
        pass  # Don't fail billing if accounting posting fails

    return {
        "invoice_id": str(invoice.id),
        "unit_number": unit.unit_number,
        "bill_type": data.bill_type,
        "amount": data.amount,
        "status": InvoiceStatus.PENDING.value,
    }
