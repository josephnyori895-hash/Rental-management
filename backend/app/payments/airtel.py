"""
RENTAL OS — Airtel Money Collections

Airtel Africa's merchant API: OAuth token, then a payment request that prompts
the subscriber's Airtel wallet. The reference carries the invoice id, so the
callback can settle the right invoice without another lookup table.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Invoice, Payment
from app.payments.service import apply_payment

logger = logging.getLogger(__name__)

PREFIX = "rent-"


def reference_for(invoice_id) -> str:
    return f"{PREFIX}{invoice_id}"


def invoice_id_from_reference(reference: str | None) -> str | None:
    if not reference or not reference.startswith(PREFIX):
        return None
    candidate = reference[len(PREFIX):].strip()
    try:
        UUID(candidate)
    except ValueError:
        return None
    return candidate


def _configured() -> bool:
    return bool(settings.AIRTEL_CLIENT_ID and settings.AIRTEL_CLIENT_SECRET)


async def _token(client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"{settings.AIRTEL_BASE_URL}/auth/oauth2/token",
        json={
            "client_id": settings.AIRTEL_CLIENT_ID,
            "client_secret": settings.AIRTEL_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def collect(
    session: AsyncSession, invoice_id: str, phone: str, business_id=None
) -> dict:
    """Prompt an Airtel Money wallet to pay an invoice owned by this business."""
    if not _configured():
        raise RuntimeError(
            "Airtel Money is not configured. Set AIRTEL_CLIENT_ID and "
            "AIRTEL_CLIENT_SECRET."
        )

    try:
        parsed_invoice_id = UUID(str(invoice_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invoice not found") from exc
    invoice_query = select(Invoice).where(Invoice.id == parsed_invoice_id)
    if business_id is not None:
        invoice_query = invoice_query.where(Invoice.business_id == business_id)
    inv = await session.scalar(invoice_query)
    if inv is None:
        raise ValueError("Invoice not found")
    if inv.balance <= 0:
        raise ValueError("Invoice already settled")

    reference = reference_for(inv.id)
    # Airtel takes a number, not a Decimal: quantise to cents rather than
    # truncating with int(), which silently under-collected fractional balances.
    amount = float(Decimal(inv.balance).quantize(Decimal("0.01")))

    async with httpx.AsyncClient(timeout=25) as client:
        token = await _token(client)
        response = await client.post(
            f"{settings.AIRTEL_BASE_URL}/merchant/v1/payments/",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Country": settings.AIRTEL_COUNTRY,
                "X-Currency": settings.AIRTEL_CURRENCY,
            },
            json={
                "reference": reference,
                "subscriber": {
                    "country": settings.AIRTEL_COUNTRY,
                    "currency": settings.AIRTEL_CURRENCY,
                    "msisdn": phone,
                },
                "transaction": {
                    "amount": amount,
                    "country": settings.AIRTEL_COUNTRY,
                    "currency": settings.AIRTEL_CURRENCY,
                    "id": str(inv.id),
                },
            },
        )
        response.raise_for_status()
        return response.json()


async def handle_callback(session: AsyncSession, payload: dict) -> Invoice | None:
    """Settle the invoice named in a successful Airtel callback.

    Only ``status_code == "TS"`` (transaction success) is credited. The
    provider transaction id is the idempotency key because callbacks are
    retried.
    """
    transaction = (payload or {}).get("transaction") or {}
    if str(transaction.get("status_code") or "").upper() != "TS":
        return None

    invoice_id = invoice_id_from_reference(transaction.get("reference"))
    amount = transaction.get("amount")
    if invoice_id is None or amount is None:
        logger.warning("Airtel callback without a usable reference/amount: %s", payload)
        return None

    provider_ref = (
        transaction.get("airtel_money_id")
        or transaction.get("id")
        or transaction.get("reference")
    )
    if provider_ref:
        existing = await session.scalar(
            select(Payment).where(Payment.reference == str(provider_ref)).limit(1)
        )
        if existing is not None:
            return existing.invoice

    return await apply_payment(
        session,
        invoice_id,
        amount,
        method="airtel",
        reference=str(provider_ref) if provider_ref else None,
        mpesa_raw=payload,
    )
