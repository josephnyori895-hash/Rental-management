"""
RENTAL OS — Billing Router

- GET /billing/invoices       : list invoices for the business (paginated)
- GET /billing/invoices/{id}  : single invoice detail
- POST /billing/bills         : DEPRECATED — free-form bill, no tariff or meter behind
                                it. Use POST /billing/utilities/readings instead.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator

from app.accounting.service import auto_post_invoice
from app.billing.utilities import income_code_for
from app.api.deps import SessionDep, get_current_business
from app.models.billing import Invoice, InvoiceStatus, Payment
from app.models.business import Business
from app.models.lease import Lease
from app.models.tenant import Tenant
from app.models.property import Unit
from app.models.utilities import UtilityType
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# The only bill types this endpoint may raise. It is a utility-bill endpoint,
# superseded by `POST /billing/utilities/readings`; rent and deposit invoices
# are raised by tenant enrollment instead.
#
# `bill_type` used to be unvalidated free text stored verbatim as
# `invoice_type`, so a typo silently invented a new invoice type, and anything
# that happened to spell "deposit" was posted as rental income. Validating
# against the utilities the rest of the system knows about removes both.
ALLOWED_BILL_TYPES: tuple[str, ...] = tuple(kind.value for kind in UtilityType)


class CreateBillRequest(BaseModel):
    unit_id: str
    bill_type: str
    amount: float
    description: str | None = None
    due_date: date | None = None

    @field_validator("bill_type")
    @classmethod
    def _must_be_a_known_utility(cls, value: str) -> str:
        """Reject anything this endpoint cannot price or post to an account.

        Case and surrounding whitespace are normalised rather than rejected:
        the value is a label a person typed, and "Water" is not an error. An
        unexpected *word*, however, is — it used to become a new
        `invoice_type` and post wherever the default income account happened
        to point.
        """
        normalised = str(value).strip().lower()
        if normalised not in ALLOWED_BILL_TYPES:
            raise ValueError(
                "bill_type must be one of "
                f"{', '.join(ALLOWED_BILL_TYPES)}; got {value!r}"
            )
        return normalised


@router.get("/invoices")
async def list_invoices(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all invoices for this business, newest first."""
    # One filter list feeds both the page query and the count, so the two can
    # never drift apart (a count that ignores the status filter lies about
    # how many pages exist).
    filters = [Invoice.business_id == business.id]
    if status:
        filters.append(Invoice.status == status)

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
        .where(*filters)
        .order_by(Invoice.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    rows = (await session.execute(q)).all()
    # `total` is every matching invoice, not the size of this page — callers
    # paginate with it.
    total = await session.scalar(
        select(func.count()).select_from(Invoice).where(*filters)
    ) or 0

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
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


@router.post("/bills", deprecated=True)
async def create_bill(
    data: CreateBillRequest,
    session: SessionDep,
    response: Response,
    business: Business = Depends(get_current_business),
):
    """**Deprecated.** Create a free-form utility bill for a unit.

    Superseded by `POST /billing/utilities/readings`, which prices the charge
    from a configured tariff and a meter reading rather than accepting an
    arbitrary amount. Kept working (with a `Deprecation` header) so existing
    clients do not break; `bill_type` here is unvalidated free text, so a typo
    silently becomes a new `invoice_type`.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v1/billing/utilities/readings>; rel="successor-version"'
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

    # Auto-post to general ledger — best-effort, but never silent. This is the
    # exact path that hid a broken revenue account: the invoice was created and
    # the tenant billed, while the ledger received nothing at all.
    #
    # The income account comes from the bill type, not from the rental-income
    # default, so this legacy endpoint now books a water bill to the same
    # account as its replacement. Previously `bill_type="water"` and
    # `POST /billing/utilities/readings` disagreed about where water income
    # goes — same word, two accounts.
    try:
        await auto_post_invoice(
            session, invoice, income_code=income_code_for(data.bill_type)
        )
    except Exception:
        logger.warning(
            "Ledger posting failed for invoice %s", invoice.id, exc_info=True
        )

    return {
        "invoice_id": str(invoice.id),
        "unit_number": unit.unit_number,
        "bill_type": data.bill_type,
        "amount": data.amount,
        "status": InvoiceStatus.PENDING.value,
    }
