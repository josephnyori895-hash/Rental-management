"""
RENTAL OS — Tenant Service

Caretaker enrollment: creates the tenant, assigns the house (unit), opens an
active lease and raises the first rent invoice (light starts RED until paid).
After saving, fires a WhatsApp welcome message to the tenant.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, UnitStatus
from app.models.tenant import Tenant


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
