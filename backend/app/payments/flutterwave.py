"""
RENTAL OS — Flutterwave Hosted Checkout

One gateway for card, bank transfer and mobile money. The tenant is sent to a
hosted checkout; the webhook settles the invoice once Flutterwave confirms the
charge. ``tx_ref`` is derived from the invoice id, so the webhook needs no
extra mapping table, and the webhook is authenticated with the shared
``verif-hash`` secret.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Invoice, Payment
from app.models.tenant import Tenant
from app.payments.service import apply_payment

logger = logging.getLogger(__name__)

PREFIX = "rent-"

# Flutterwave reports the rail it used; map it onto our payment methods.
_METHOD_BY_RAIL = {
    "card": "card",
    "banktransfer": "bank",
    "bank_transfer": "bank",
    "mobilemoney": "mpesa",
    "mobile_money": "mpesa",
}


def tx_ref_for(invoice_id) -> str:
    return f"{PREFIX}{invoice_id}"


def invoice_id_from_tx_ref(reference: str | None) -> str | None:
    if not reference or not reference.startswith(PREFIX):
        return None
    candidate = reference[len(PREFIX):].strip()
    try:
        UUID(candidate)
    except ValueError:
        return None
    return candidate


def _configured() -> bool:
    return bool(settings.FLUTTERWAVE_SECRET_KEY)


async def create_checkout(session: AsyncSession, invoice_id: str) -> dict:
    """Create a hosted checkout and return its URL."""
    if not _configured():
        raise RuntimeError(
            "Card/bank checkout is not configured. Set FLUTTERWAVE_SECRET_KEY."
        )

    inv = await session.get(Invoice, UUID(str(invoice_id)))
    if inv is None:
        raise ValueError("Invoice not found")
    if inv.balance <= 0:
        raise ValueError("Invoice already settled")

    tenant = await session.get(Tenant, inv.tenant_id)
    email = (
        getattr(tenant, "email", None)
        or f"tenant-{str(inv.tenant_id)[:8]}@rentalos.local"
    )

    payload = {
        "tx_ref": tx_ref_for(inv.id),
        "amount": float(inv.balance),
        "currency": settings.FLUTTERWAVE_CURRENCY,
        "redirect_url": settings.FLUTTERWAVE_REDIRECT_URL
        or f"{settings.MPESA_CALLBACK_BASE}/payments/complete",
        "customer": {
            "email": email,
            "phonenumber": (tenant.whatsapp_phone or tenant.phone) if tenant else None,
            "name": tenant.full_name if tenant else None,
        },
        "customizations": {
            "title": "Rent payment",
            "description": inv.invoice_number or f"Invoice {str(inv.id)[:8]}",
        },
    }

    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            f"{settings.FLUTTERWAVE_BASE_URL}/payments",
            headers={"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()

    link = (body.get("data") or {}).get("link")
    if not link:
        raise RuntimeError(f"Flutterwave did not return a checkout link: {body}")
    return {"checkout_url": link, "tx_ref": payload["tx_ref"]}


async def handle_webhook(session: AsyncSession, payload: dict) -> Invoice | None:
    """Settle the invoice referenced by a successful charge.completed webhook."""
    if payload.get("event") != "charge.completed":
        return None

    data = payload.get("data") or {}
    if str(data.get("status") or "").lower() != "successful":
        return None

    invoice_id = invoice_id_from_tx_ref(data.get("tx_ref"))
    amount = data.get("amount")
    if invoice_id is None or amount is None:
        logger.warning("Flutterwave webhook with unusable tx_ref/amount: %s", payload)
        return None

    # Flutterwave transaction ids are the idempotency key; webhooks retry.
    provider_ref = str(data.get("id") or data.get("flw_ref") or data.get("tx_ref"))
    existing = await session.scalar(
        select(Payment).where(Payment.reference == provider_ref).limit(1)
    )
    if existing is not None:
        return existing.invoice

    method = _METHOD_BY_RAIL.get(
        str(data.get("payment_type") or "").lower(), "card"
    )
    return await apply_payment(
        session,
        invoice_id,
        amount,
        method=method,
        reference=provider_ref,
        mpesa_raw=payload,
    )
