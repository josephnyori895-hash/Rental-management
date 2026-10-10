"""
RENTAL OS — Tenant Service

Caretaker enrollment: creates the tenant, assigns the house (unit), opens an
active lease and raises the first rent invoice and any deposit invoice (light
starts RED until paid), posting both to the ledger. After saving, fires a
WhatsApp welcome message to the tenant.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_invoice
from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, UnitStatus
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


async def enroll_tenant(session: AsyncSession, actor, data) -> dict:
    unit = await session.get(Unit, uuid.UUID(str(data.unit_id)))
    if not unit or unit.business_id != actor.business_id or unit.is_deleted:
        raise ValueError("Unit not found for this business")

    tenant = Tenant(
        business_id=actor.business_id,
        full_name=data.full_name,
        id_number=data.id_number,
        phone=data.phone,
        mpesa_phone=data.mpesa_phone,
        # Use WhatsApp phone if given, otherwise fall back to M-Pesa number
        whatsapp_phone=getattr(data, "whatsapp_phone", None) or data.mpesa_phone,
        email=data.email,
    )
    session.add(tenant)
    await session.flush()

    rent = Decimal(str(data.rent_amount)) if data.rent_amount is not None else unit.monthly_rent

    lease = Lease(
        business_id=actor.business_id,
        unit_id=unit.id,
        tenant_id=tenant.id,
        property_id=unit.property_id,
        start_date=data.start_date,
        rent_amount=rent,
        deposit_amount=Decimal(str(data.deposit_amount)),
        payment_day=data.payment_day,
        payment_frequency="monthly",
        status=LeaseStatus.ACTIVE.value,
    )
    session.add(lease)
    await session.flush()

    unit.status = UnitStatus.OCCUPIED.value
    unit.current_lease_id = lease.id

    period_end = data.start_date + timedelta(days=30)

    # ── Rent invoice (always created) ──
    invoice = Invoice(
        business_id=actor.business_id,
        lease_id=lease.id,
        tenant_id=tenant.id,
        unit_id=unit.id,
        property_id=unit.property_id,
        invoice_type=InvoiceType.RENT.value,
        period_start=data.start_date,
        period_end=period_end,
        due_date=data.start_date,
        amount=rent,
        paid_amount=Decimal("0"),
        balance=rent,
        status=InvoiceStatus.PENDING.value,
    )
    session.add(invoice)

    # ── Deposit invoice (created only when deposit > 0) ──
    deposit = Decimal(str(data.deposit_amount)) if data.deposit_amount else Decimal("0")
    deposit_invoice: Invoice | None = None
    if deposit > 0:
        deposit_invoice = Invoice(
            business_id=actor.business_id,
            lease_id=lease.id,
            tenant_id=tenant.id,
            unit_id=unit.id,
            property_id=unit.property_id,
            invoice_type=InvoiceType.DEPOSIT.value,
            period_start=data.start_date,
            period_end=data.start_date,
            due_date=data.start_date,
            amount=deposit,
            paid_amount=Decimal("0"),
            balance=deposit,
            status=InvoiceStatus.PENDING.value,
        )
        session.add(deposit_invoice)

    await session.flush()
    await session.commit()

    # ── Post both invoices to the ledger ──
    # Enrollment is the only path that raises a rent or deposit invoice, and it
    # raised both without posting either: every tenancy started with invoices
    # the ledger had never heard of, so the rent roll and the balance sheet
    # disagreed from day one. Rent credits rental income; the deposit credits
    # Security Deposits Payable, because a deposit is a liability rather than
    # revenue (see `accounting.service.credit_account_code`).
    #
    # Best-effort — losing an enrollment to a ledger problem would be worse —
    # but logged, never swallowed.
    try:
        await auto_post_invoice(session, invoice)
        if deposit_invoice is not None:
            await auto_post_invoice(session, deposit_invoice)
    except Exception:
        logger.warning(
            "Ledger posting failed for enrollment of tenant %s (lease %s)",
            tenant.id, lease.id, exc_info=True,
        )

    return_data = {
        "tenant_id": str(tenant.id),
        "lease_id": str(lease.id),
        "invoice_id": str(invoice.id),
        "unit_number": unit.unit_number,
        "rent_amount": float(rent),
        "message": "Tenant enrolled. Rent invoice pending — board light is RED until payment.",
        "whatsapp_sent": False,
    }

    # ── Fire WhatsApp welcome message (non-blocking) ──
    try:
        from app.notifications import service as notif_svc
        prop = await session.get(Property, unit.property_id)
        prop_name = prop.name if prop else "the hostel"
        await notif_svc.send_wa_enrollment_prompt(
            session=session,
            business_id=actor.business_id,
            tenant=tenant,
            property_name=prop_name,
            unit_number=unit.unit_number,
            rent_amount=float(rent),
            deposit_amount=float(data.deposit_amount) if data.deposit_amount else None,
        )
        return_data["whatsapp_sent"] = True
    except Exception:
        # WA failure must never break enrollment
        pass

    return return_data
