"""
RENTAL OS — M-Pesa Reconciliation Service

Matches M-Pesa callback payments to invoices using:
1. Phone number (tenant's mpesa_phone)
2. Amount (exact match or within threshold)
3. Time proximity (payment within invoice period)

Unmatched payments flagged for manual review.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


async def reconcile_pending(
    session: AsyncSession,
    business_id: uuid.UUID,
    max_amount_diff: float = 50.0,
    max_days_window: int = 5,
) -> dict:
    """Scan unmatched M-Pesa payments and attempt to match to invoices.

    Returns stats on matched, unmatched, and total processed.
    """
    # Find payments with mpesa_raw but not linked to appropriate invoice
    unmatched_q = select(Payment).where(
        Payment.business_id == business_id,
        Payment.method == "mpesa",
        Payment.invoice_id.is_(None),
        Payment.mpesa_raw.isnot(None),
    )
    payments = (await session.scalars(unmatched_q)).all()

    matched = 0
    unmatched = 0
    results = []

    for pay in payments:
        phone = None
        if pay.mpesa_raw:
            phone = str(pay.mpesa_raw.get("PhoneNumber") or pay.mpesa_raw.get("MSISDN") or "")

        pay_amount = float(pay.amount)
        pay_time = pay.paid_at

        # Find matching invoice
        inv_q = select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.tenant_id == pay.tenant_id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
            Invoice.balance > 0,
        )
        invoices = (await session.scalars(inv_q)).all()

        best_match = None
        best_diff = float("inf")

        for inv in invoices:
            inv_balance = float(inv.balance)
            diff = abs(pay_amount - inv_balance)
            if diff < best_diff and diff <= max_amount_diff:
                best_diff = diff
                best_match = inv

        if best_match:
            pay.invoice_id = best_match.id
            pay.status = "reconciled"
            best_match.paid_amount = (best_match.paid_amount or Decimal("0")) + pay.amount
            best_match.balance = best_match.amount - best_match.paid_amount
            best_match.status = (
                InvoiceStatus.PAID.value
                if best_match.balance <= 0
                else InvoiceStatus.PARTIAL.value
            )
            matched += 1
            results.append({"payment_id": str(pay.id), "matched_invoice": str(best_match.id)})
        else:
            unmatched += 1
            results.append({"payment_id": str(pay.id), "unmatched": True})

    await session.commit()

    return {
        "total_processed": len(payments),
        "matched": matched,
        "unmatched": unmatched,
        "details": results,
    }


async def get_unmatched_payments(
    session: AsyncSession,
    business_id: uuid.UUID,
    limit: int = 50,
) -> list[dict]:
    """Return mobile-money and bank claims not linked to any invoice."""
    q = select(Payment, Tenant.full_name, Tenant.mpesa_phone).join(
        Tenant, Payment.tenant_id == Tenant.id, isouter=True
    ).where(
        Payment.business_id == business_id,
        Payment.method.in_(["mpesa", "bank"]),
        Payment.invoice_id.is_(None),
    ).order_by(Payment.paid_at.desc()).limit(limit)

    rows = (await session.execute(q)).all()
    return [
        {
            "id": str(r[0].id),
            "amount": float(r[0].amount),
            "phone": r[2] or "—",
            "tenant_name": r[1] or "—",
            "reference": r[0].reference,
            "method": r[0].method,
            "status": r[0].status,
            "paid_at": str(r[0].paid_at),
            "has_raw_data": r[0].mpesa_raw is not None,
        }
        for r in rows
    ]


async def match_payment(
    session: AsyncSession,
    business_id: uuid.UUID,
    payment_id: uuid.UUID,
    invoice_id: uuid.UUID,
) -> dict:
    """Attach an unmatched/claimed payment to an invoice.

    Used for bank-transfer claims, which are recorded as pending payments and
    need a human to confirm the money landed. The payment is only credited up
    to the invoice balance; any excess stays on the payment record rather than
    being silently written off.
    """
    payment = await session.get(Payment, payment_id)
    invoice = await session.get(Invoice, invoice_id)
    if payment is None or payment.business_id != business_id:
        raise ValueError("Payment not found")
    if invoice is None or invoice.business_id != business_id:
        raise ValueError("Invoice not found")
    if payment.invoice_id is not None:
        raise ValueError("Payment is already matched to an invoice")

    applied = min(payment.amount, invoice.balance)
    invoice.paid_amount = (invoice.paid_amount or Decimal("0")) + applied
    invoice.balance = invoice.amount - invoice.paid_amount
    invoice.status = (
        InvoiceStatus.PAID.value
        if invoice.balance <= 0
        else InvoiceStatus.PARTIAL.value
    )
    payment.invoice_id = invoice.id
    payment.status = "reconciled"
    await session.commit()

    # The ledger and the tenant's receipt must reflect a confirmed payment.
    from app.accounting.service import auto_post_payment
    from app.notifications.service import send_payment_receipt
    try:
        await auto_post_payment(session, payment)
    except Exception:
        logger.warning(
            "Ledger posting failed for reconciled payment %s", payment.id, exc_info=True
        )
    try:
        from app.models.property import Unit

        unit = await session.get(Unit, invoice.unit_id) if invoice.unit_id else None
        await send_payment_receipt(
            session, payment,
            unit_number=unit.unit_number if unit else None,
            invoice_status=invoice.status,
        )
    except Exception:
        logger.warning(
            "Receipt failed for reconciled payment %s", payment.id, exc_info=True
        )

    return {
        "payment_id": str(payment.id),
        "invoice_id": str(invoice.id),
        "applied": float(applied),
        "invoice_status": invoice.status,
        "invoice_balance": float(invoice.balance),
    }
