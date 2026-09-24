"""
RENTAL OS — Payments Service

M-Pesa Daraja STK push + a callback that marks the rent invoice PAID (flipping
the owner-board light green). A dev `simulate` path marks payment without live
Daraja credentials so the flow is demoable offline.
"""

from __future__ import annotations

import base64
import datetime
import uuid
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_payment
from app.core.config import settings
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.property import Unit


async def apply_payment(
    session: AsyncSession,
    invoice_id: str,
    amount,
    method: str = "mpesa",
    reference: str | None = None,
    mpesa_raw: dict | None = None,
) -> Invoice | None:
    inv = await session.get(Invoice, uuid.UUID(str(invoice_id)))
    if not inv:
        return None
    if inv.status == InvoiceStatus.PAID.value:
        return inv
    amt = Decimal(str(amount))
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
    # Auto-post to general ledger
    try:
        await auto_post_payment(session, pay)
    except Exception:
        pass  # Don't fail the payment if accounting posting fails

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
        pass

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


async def stk_push(session: AsyncSession, invoice_id: str, phone: str) -> str:
    """Trigger an M-Pesa STK push to the tenant's phone. Returns CheckoutRequestID."""
    inv = await session.get(Invoice, uuid.UUID(str(invoice_id)))
    if not inv:
        raise ValueError("Invoice not found")

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

