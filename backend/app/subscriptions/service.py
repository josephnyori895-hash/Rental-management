"""Pricing and entitlement rules for Rental OS platform subscriptions."""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Unit
from app.models.subscriptions import (
    BusinessSubscription, BusinessSubscriptionItem, SubscriptionCatalogItem,
    SubscriptionPriceVersion, SubscriptionInvoice, SubscriptionPayment,
    BusinessSubscriptionEvent,
)

CENT = Decimal("0.01")
SUPPORTED_PRICING = {"flat_recurring", "per_billable_unit", "one_time"}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


async def billable_unit_count(session: AsyncSession, business_id) -> int:
    """Count all non-deleted units, occupied or available, across this business."""
    return int(await session.scalar(
        select(func.count(Unit.id)).where(
            Unit.business_id == business_id,
            Unit.is_deleted.is_(False),
        )
    ) or 0)


async def current_price(session: AsyncSession, item_id, now: datetime):
    result = await session.execute(
        select(SubscriptionPriceVersion)
        .where(
            SubscriptionPriceVersion.catalog_item_id == item_id,
            SubscriptionPriceVersion.active.is_(True),
            SubscriptionPriceVersion.effective_from <= now,
            (SubscriptionPriceVersion.effective_to.is_(None) |
             (SubscriptionPriceVersion.effective_to > now)),
        )
        .order_by(SubscriptionPriceVersion.effective_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def calculate_item_total(item: SubscriptionCatalogItem, price: SubscriptionPriceVersion,
                         quantity: int, billable_units: int) -> Decimal:
    if quantity < 1:
        raise HTTPException(status_code=422, detail="Quantity must be at least one")
    if price.amount < 0 or price.per_unit_amount < 0:
        raise HTTPException(status_code=409, detail="Catalogue price is invalid")
    if item.pricing_model not in SUPPORTED_PRICING:
        raise HTTPException(status_code=409, detail=f"Pricing model {item.pricing_model} is not enabled yet")
    if item.pricing_model == "per_billable_unit":
        units = max(0, billable_units - price.included_units)
        return money((price.amount + Decimal(units) * price.per_unit_amount) * quantity)
    return money(price.amount * quantity)


async def get_entitlements(session: AsyncSession, business_id) -> dict:
    """Merge feature snapshots only from an active or trialing subscription."""
    result = await session.execute(
        select(BusinessSubscriptionItem.features_snapshot)
        .join(BusinessSubscription, BusinessSubscription.id == BusinessSubscriptionItem.subscription_id)
        .where(
            BusinessSubscription.business_id == business_id,
            BusinessSubscription.status.in_(("active", "trialing")),
        )
    )
    merged: dict = {}
    for features in result.scalars():
        for key, value in (features or {}).items():
            if isinstance(value, bool):
                merged[key] = bool(merged.get(key, False) or value)
            elif isinstance(value, (int, float)):
                merged[key] = max(merged.get(key, 0), value)
            else:
                merged[key] = value
    return merged



def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


async def apply_verified_platform_subscription_payment(
    session: AsyncSession,
    *,
    invoice_id,
    provider: str,
    provider_reference: str,
    amount: Decimal,
    currency: str,
    provider_event_verified: bool,
) -> dict:
    """Apply a verified Rental OS platform-payment event exactly once.

    This function is intentionally not an HTTP endpoint. Only a future
    provider-specific webhook adapter may call it after cryptographic
    verification using Rental OS's own provider credentials. Never pass
    landlord payment credentials or landlord rent invoice identifiers here.
    """
    if provider_event_verified is not True:
        raise HTTPException(status_code=401, detail="Unverified platform payment event")
    if not provider or len(provider) > 40 or not provider_reference or len(provider_reference) > 160:
        raise HTTPException(status_code=422, detail="Invalid payment provider reference")
    try:
        paid_amount = Decimal(str(amount))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid payment amount")
    if not paid_amount.is_finite() or paid_amount <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be positive and finite")
    if not isinstance(currency, str) or len(currency) != 3 or currency != currency.upper():
        raise HTTPException(status_code=422, detail="Invalid payment currency")

    duplicate = await session.scalar(
        select(SubscriptionPayment).where(
            SubscriptionPayment.provider == provider,
            SubscriptionPayment.provider_reference == provider_reference,
        ).with_for_update()
    )
    if duplicate:
        if (duplicate.invoice_id != invoice_id or duplicate.amount != paid_amount
                or duplicate.currency != currency or duplicate.status != "succeeded"):
            raise HTTPException(status_code=409, detail="Payment reference was already used for a different payment")
        return {"payment_id": str(duplicate.id), "status": "succeeded", "idempotent": True}

    invoice = await session.scalar(
        select(SubscriptionInvoice).where(
            SubscriptionInvoice.id == invoice_id,
        ).with_for_update()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Platform subscription invoice not found")
    if invoice.status != "open":
        raise HTTPException(status_code=409, detail="Subscription invoice is not payable")
    if paid_amount != Decimal(invoice.total):
        raise HTTPException(status_code=409, detail="Payment amount does not match the platform invoice")
    if currency != invoice.currency:
        raise HTTPException(status_code=409, detail="Payment currency does not match the platform invoice")

    subscription = await session.scalar(
        select(BusinessSubscription).where(
            BusinessSubscription.id == invoice.subscription_id,
            BusinessSubscription.business_id == invoice.business_id,
        ).with_for_update()
    )
    if not subscription or subscription.status != "draft":
        raise HTTPException(status_code=409, detail="Subscription is not awaiting initial activation")

    now = datetime.now(timezone.utc)
    payment = SubscriptionPayment(
        business_id=invoice.business_id,
        invoice_id=invoice.id,
        provider=provider,
        provider_reference=provider_reference,
        amount=paid_amount,
        currency=currency,
        status="succeeded",
        received_at=now,
    )
    session.add(payment)
    invoice.status = "paid"
    invoice.paid_at = now
    subscription.status = "active"
    subscription.starts_at = now
    subscription.current_period_start = now
    if subscription.billing_interval == "monthly":
        subscription.current_period_end = _add_months(now, 1)
    elif subscription.billing_interval == "quarterly":
        subscription.current_period_end = _add_months(now, 3)
    elif subscription.billing_interval == "annual":
        subscription.current_period_end = _add_months(now, 12)
    else:
        raise HTTPException(status_code=409, detail="Unsupported subscription billing interval")

    session.add(BusinessSubscriptionEvent(
        business_id=invoice.business_id,
        subscription_id=subscription.id,
        event_type="subscription.activated",
        event_metadata={
            "invoice_id": str(invoice.id), "payment_id": str(payment.id),
            "provider": provider, "provider_reference": provider_reference,
            "currency": currency, "amount": str(paid_amount),
        },
    ))
    await session.flush()
    return {"payment_id": str(payment.id), "status": "succeeded", "idempotent": False}
