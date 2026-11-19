"""
RENTAL OS — Payments Service

M-Pesa Daraja STK push + a callback that marks the rent invoice PAID (flipping
the owner-board light green). A dev `simulate` path marks payment without live
Daraja credentials so the flow is demoable offline.
"""

from __future__ import annotations

import base64
import datetime
import logging
import uuid
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_payment
from app.core.config import settings
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.lease import Lease, LeaseStatus
from app.models.property import Unit, UnitStatus

logger = logging.getLogger(__name__)


async def _activate_lease_if_settled(session: AsyncSession, lease_id) -> bool:
    """Turn a reserved, pending lease into an active tenancy once it is paid.

    WhatsApp enrollment reserves the unit and raises deposit/first-rent
    invoices against a pending lease. Nothing used to flip that lease to
    active, so a tenant who paid in full stayed pending forever and the unit
    never showed as occupied. Driving activation from the invoice makes it
    work identically for STK, the M-Pesa callback, cash recording and the
    simulator.
    """
    lease = await session.get(Lease, lease_id)
    if lease is None or lease.status != LeaseStatus.PENDING.value:
        return False

    unpaid = await session.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.lease_id == lease.id,
            Invoice.balance > 0,
            Invoice.status.in_(["pending", "partial", "overdue"]),
        )
    )
    if unpaid:
        return False

    lease.status = LeaseStatus.ACTIVE.value
    unit = await session.get(Unit, lease.unit_id)
    if unit is not None:
        unit.status = UnitStatus.OCCUPIED.value
        unit.current_lease_id = lease.id
    await session.commit()
    return True


async def apply_payment(
    session: AsyncSession,
    invoice_id: str,
    amount,
    method: str = "mpesa",
    reference: str | None = None,
    mpesa_raw: dict | None = None,
    business_id=None,
) -> Invoice | None:
    """Apply one payment under an invoice row lock.

    business_id is supplied by authenticated dashboard operations. Provider
    callbacks omit it because the provider transaction is resolved through its
    previously issued checkout/reference, but still pass through the same
    amount validation and idempotency checks.
    """
    try:
        parsed_invoice_id = uuid.UUID(str(invoice_id))
    except (TypeError, ValueError, AttributeError):
        return None

    invoice_query = select(Invoice).where(Invoice.id == parsed_invoice_id)
    if business_id is not None:
        invoice_query = invoice_query.where(Invoice.business_id == business_id)
    inv = await session.scalar(invoice_query.with_for_update())
    if not inv:
        return None
    if inv.status == InvoiceStatus.PAID.value:
        return inv

    try:
        amt = Decimal(str(amount)).quantize(Decimal("0.01"))
    except Exception as exc:
        raise ValueError("Payment amount must be a valid monetary amount") from exc
    if not amt.is_finite() or amt <= 0:
        raise ValueError("Payment amount must be greater than zero")
    current_balance = Decimal(str(inv.balance or 0)).quantize(Decimal("0.01"))
    if current_balance <= 0:
        return inv

    # Provider callbacks are retried. Checking after acquiring the invoice lock
    # serializes duplicate callbacks for the same invoice and prevents a repeated
    # partial payment from being applied twice.
    if reference and method in {"mpesa", "airtel", "card", "bank"}:
        existing = await session.scalar(
            select(Payment.id).where(
                Payment.business_id == inv.business_id,
                Payment.method == method,
                Payment.reference == reference,
            ).limit(1)
        )
        if existing is not None:
            return inv

    pay = Payment(
        business_id=inv.business_id,
        invoice_id=inv.id,
        lease_id=inv.lease_id,
        tenant_id=inv.tenant_id,
        amount=amt,
        method=method,
        reference=reference,
        status="completed",
        mpesa_raw=mpesa_raw,
    )
    session.add(pay)
    inv.paid_amount = (inv.paid_amount or Decimal("0")) + amt
    inv.balance = inv.amount - inv.paid_amount
    inv.status = (
        InvoiceStatus.PAID.value if inv.balance <= 0 else InvoiceStatus.PARTIAL.value
    )
    await session.commit()
    # Auto-post to general ledger. Best-effort by design — the money has
    # already moved, so the payment must stand even if the posting fails. But
    # it must never fail *quietly*: the ledger silently disagreeing with the
    # bank is the one condition that has to be audible.
    try:
        await auto_post_payment(session, pay)
    except Exception:
        logger.warning(
            "Ledger posting failed for payment %s (invoice %s)",
            pay.id, inv.id, exc_info=True,
        )

    # A move-in deposit and first rent may arrive as two separate payments;
    # the lease only activates once nothing is left outstanding.
    if inv.lease_id:
        try:
            await _activate_lease_if_settled(session, inv.lease_id)
        except Exception:
            logger.warning(
                "Lease activation failed for invoice %s", inv.id, exc_info=True
            )

    # Send SMS receipt (best-effort, don't block payment)
    try:
        from app.notifications.service import send_payment_receipt
        unit = await session.get(Unit, inv.unit_id) if inv.unit_id else None
        await send_payment_receipt(
            session, pay,
            unit_number=unit.unit_number if unit else None,
            invoice_status=inv.status,
        )
    except Exception:
        logger.warning("Receipt for payment %s was not sent", pay.id, exc_info=True)

    return inv


async def mark_paid_by_checkout(
    session: AsyncSession, checkout_id: str, amount,
    reference: str | None = None,
    mpesa_raw: dict | None = None,
) -> Invoice | None:
    inv = (
        await session.scalars(
            select(Invoice).where(Invoice.mpesa_checkout_request_id == checkout_id)
        )
    ).first()
    if not inv:
        return None
    return await apply_payment(session, str(inv.id), amount, "mpesa", reference, mpesa_raw=mpesa_raw)


async def stk_push(
    session: AsyncSession, invoice_id: str, phone: str, business_id=None
) -> str:
    """Trigger an M-Pesa STK push for an invoice owned by the requesting business."""
    try:
        parsed_invoice_id = uuid.UUID(str(invoice_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invoice not found") from exc
    invoice_query = select(Invoice).where(Invoice.id == parsed_invoice_id)
    if business_id is not None:
        invoice_query = invoice_query.where(Invoice.business_id == business_id)
    inv = await session.scalar(invoice_query)
    if not inv:
        raise ValueError("Invoice not found")
    if Decimal(str(inv.balance or 0)) <= 0:
        raise ValueError("Invoice already settled")

    cfg = settings
    if not (
        cfg.MPESA_CONSUMER_KEY
        and cfg.MPESA_CONSUMER_SECRET
        and cfg.MPESA_SHORTCODE
        and cfg.MPESA_PASSKEY
    ):
        raise RuntimeError(
            "M-Pesa Daraja credentials not configured. Set MPESA_CONSUMER_KEY / "
            "MPESA_CONSUMER_SECRET / MPESA_SHORTCODE / MPESA_PASSKEY (sandbox), or use "
            "POST /api/v1/payments/simulate to demo the green light."
        )

    env = "sandbox" if cfg.MPESA_ENVIRONMENT == "sandbox" else "api"
    base = f"https://{env}.safaricom.co.ke"
    auth = base64.b64encode(
        f"{cfg.MPESA_CONSUMER_KEY}:{cfg.MPESA_CONSUMER_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(
            f"{base}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {auth}"},
        )
        r.raise_for_status()
        token = r.json()["access_token"]

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        pwd = base64.b64encode(
            f"{cfg.MPESA_SHORTCODE}{cfg.MPESA_PASSKEY}{ts}".encode()
        ).decode()
        callback = f"{cfg.MPESA_CALLBACK_BASE}/api/v1/payments/mpesa/callback"

        payload = {
            "BusinessShortCode": cfg.MPESA_SHORTCODE,
            "Password": pwd,
            "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(inv.balance),
            "PartyA": phone,
            "PartyB": cfg.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback,
            "AccountReference": inv.invoice_number or str(inv.id)[:8],
            "TransactionDesc": "Rent payment",
        }
        rr = await c.post(
            f"{base}/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        rr.raise_for_status()
        data = rr.json()
        cid = data.get("CheckoutRequestID")
        inv.mpesa_checkout_request_id = cid
        await session.commit()
        return cid


async def stk_push_direct(session: AsyncSession, phone: str, amount: float, description: str = "Expense Payment") -> str:
    """Fire an STK push to *any* phone + amount (no invoice required — used for expense payments)."""
    cfg = settings
    if not (
        cfg.MPESA_CONSUMER_KEY
        and cfg.MPESA_CONSUMER_SECRET
        and cfg.MPESA_SHORTCODE
        and cfg.MPESA_PASSKEY
    ):
        raise RuntimeError(
            "M-Pesa Daraja credentials not configured. Set MPESA_CONSUMER_KEY / "
            "MPESA_CONSUMER_SECRET / MPESA_SHORTCODE / MPESA_PASSKEY."
        )

    env = "sandbox" if cfg.MPESA_ENVIRONMENT == "sandbox" else "api"
    base = f"https://{env}.safaricom.co.ke"
    auth = base64.b64encode(
        f"{cfg.MPESA_CONSUMER_KEY}:{cfg.MPESA_CONSUMER_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(
            f"{base}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {auth}"},
        )
        r.raise_for_status()
        token = r.json()["access_token"]

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        pwd = base64.b64encode(
            f"{cfg.MPESA_SHORTCODE}{cfg.MPESA_PASSKEY}{ts}".encode()
        ).decode()
        callback = f"{cfg.MPESA_CALLBACK_BASE}/api/v1/payments/mpesa/callback"

        payload = {
            "BusinessShortCode": cfg.MPESA_SHORTCODE,
            "Password": pwd,
            "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": cfg.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback,
            "AccountReference": "ExpensePay",
            "TransactionDesc": description[:20],
        }
        rr = await c.post(
            f"{base}/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        rr.raise_for_status()
        return rr.json().get("CheckoutRequestID", "")

