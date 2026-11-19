"""Pricing and entitlement rules for Rental OS platform subscriptions."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Unit
from app.models.subscriptions import (
    BusinessSubscription, BusinessSubscriptionItem, SubscriptionCatalogItem,
    SubscriptionPriceVersion,
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
