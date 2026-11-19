"""
RENTAL OS — M-Pesa Paybill (C2B) Ingestion

Daraja calls two URLs for a Paybill collection: validation (before the money
moves) and confirmation (after). Validation always accepts — rejecting there
would fail a tenant's payment with no record of it. Confirmation is where the
money is recorded: the account reference is matched to an invoice number, then
to a unit number, which is how Paybill-only tenants reconcile without STK.

A confirmation that matches nothing is still kept when the paying number
belongs to a known tenant, so it appears in the owner's reconciliation queue
instead of disappearing.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, Payment
from app.models.business import Business
from app.models.property import Unit
from app.models.tenant import Tenant
from app.notifications.service import _format_phone
from app.payments.service import apply_payment

logger = logging.getLogger(__name__)

UNPAID = ("pending", "partial", "overdue")


async def _business_for_shortcode(session: AsyncSession, shortcode: str) -> Business | None:
    """Find the operator that owns the receiving Paybill.

    Per-business shortcodes come from enrollment; a single-operator deployment
    may only have the system-level shortcode configured, so that is accepted
    when there is exactly one active business.
    """
    business = await session.scalar(
        select(Business).where(
            Business.mpesa_shortcode == shortcode,
            Business.is_active.is_(True),
        ).limit(1)
    )
    if business is not None:
        return business

    businesses = (
        await session.scalars(
            select(Business).where(Business.is_active.is_(True)).limit(2)
        )
    ).all()
    return businesses[0] if len(businesses) == 1 else None


async def _match_invoice(
    session: AsyncSession, business_id: UUID, reference: str
) -> Invoice | None:
    ref = (reference or "").strip()
    if not ref:
        return None

    invoice = await session.scalar(
        select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.invoice_number.ilike(ref),
            Invoice.status.in_(UNPAID),
        ).limit(1)
    )
    if invoice is not None:
        return invoice

    # Tenants very often type the house number as the account number.
    unit = await session.scalar(
        select(Unit).where(
            Unit.business_id == business_id,
            Unit.unit_number.ilike(ref),
            Unit.is_deleted.is_(False),
        ).limit(1)
    )
    if unit is None:
        return None

    return await session.scalar(
        select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.unit_id == unit.id,
            Invoice.status.in_(UNPAID),
            Invoice.balance > 0,
        ).order_by(Invoice.due_date.asc(), Invoice.created_at.asc()).limit(1)
    )


async def record_c2b_payment(session: AsyncSession, payload: dict) -> bool:
    """Record one Paybill confirmation. Returns False only when it cannot be kept."""
    trans_id = str(payload.get("TransID") or "").strip()
    if not trans_id:
        return False

    # Daraja retries confirmations. The TransID is the idempotency key.
    existing = await session.scalar(
        select(Payment).where(Payment.reference == trans_id).limit(1)
    )
    if existing is not None:
        return True

    shortcode = str(payload.get("BusinessShortCode") or "").strip()
    business = await _business_for_shortcode(session, shortcode)
    if business is None:
        logger.warning(
            "C2B %s: no business owns shortcode %s", trans_id, shortcode
        )
        return False

    try:
        amount = Decimal(str(payload.get("TransAmount") or "0"))
    except (InvalidOperation, ValueError):
        logger.warning("C2B %s has an invalid amount", trans_id)
        return False
    if amount <= 0:
        return False

    invoice = await _match_invoice(
        session, business.id, str(payload.get("BillRefNumber") or "")
    )
    if invoice is not None:
        await apply_payment(
            session,
            str(invoice.id),
            amount,
            method="mpesa",
            reference=trans_id,
            mpesa_raw=payload,
        )
        return True

    phone = _format_phone(str(payload.get("MSISDN") or ""))
    tenant = await session.scalar(
        select(Tenant).where(
            Tenant.business_id == business.id,
            Tenant.mpesa_phone == phone,
            Tenant.is_deleted.is_(False),
        ).limit(1)
    )
    if tenant is None:
        logger.warning(
            "C2B %s (KES %s, ref %r) matches no invoice or tenant",
            trans_id,
            amount,
            payload.get("BillRefNumber"),
        )
        return False

    session.add(
        Payment(
            business_id=business.id,
            invoice_id=None,
            tenant_id=tenant.id,
            amount=amount,
            method="mpesa",
            reference=trans_id,
            status="completed",
            mpesa_raw=payload,
        )
    )
    await session.commit()
    return True
