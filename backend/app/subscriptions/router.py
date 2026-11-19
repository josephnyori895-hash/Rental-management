"""Authenticated business-facing Rental OS subscription endpoints.

Catalogue changes are platform-admin operations; this initial slice exposes
read/quote/select only. Selection creates a draft and never charges a card,
starts an STK push, or alters landlord rent invoices/payments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, get_current_business, get_current_user, require_roles
from app.models.business import Business
from app.models.subscriptions import (
    BusinessSubscription, BusinessSubscriptionItem, SubscriptionCatalogItem,
)
from app.subscriptions.service import (
    billable_unit_count, calculate_item_total, current_price, get_entitlements,
)

router = APIRouter(prefix="/subscriptions", tags=["platform subscriptions"])


class SelectionRequest(BaseModel):
    package_code: str = Field(min_length=1, max_length=80)
    addon_codes: list[str] = Field(default_factory=list, max_length=30)


async def _catalogue(session: AsyncSession, now: datetime):
    items = (await session.execute(
        select(SubscriptionCatalogItem)
        .where(SubscriptionCatalogItem.active.is_(True))
        .order_by(SubscriptionCatalogItem.display_order, SubscriptionCatalogItem.name)
    )).scalars().all()
    output = []
    for item in items:
        price = await current_price(session, item.id, now)
        if not price:
            continue
        output.append({
            "code": item.code, "name": item.name, "description": item.description,
            "item_type": item.item_type, "pricing_model": item.pricing_model,
            "features": item.features or {}, "currency": price.currency,
            "amount": str(price.amount), "included_units": price.included_units,
            "per_unit_amount": str(price.per_unit_amount),
            "effective_from": price.effective_from.isoformat(),
        })
    return output


async def _price_selection(session: AsyncSession, data: SelectionRequest, business: Business):
    if len(set(data.addon_codes)) != len(data.addon_codes):
        raise HTTPException(status_code=422, detail="Duplicate add-ons are not allowed")
    now = datetime.now(timezone.utc)
    codes = [data.package_code, *data.addon_codes]
    items = (await session.execute(
        select(SubscriptionCatalogItem).where(
            SubscriptionCatalogItem.code.in_(codes),
            SubscriptionCatalogItem.active.is_(True),
        )
    )).scalars().all()
    by_code = {item.code: item for item in items}
    if len(by_code) != len(codes):
        raise HTTPException(status_code=422, detail="Unknown or inactive catalogue item")
    package = by_code[data.package_code]
    if package.item_type != "package":
        raise HTTPException(status_code=422, detail="Selected base item is not a package")
    if any(by_code[code].item_type != "addon" for code in data.addon_codes):
        raise HTTPException(status_code=422, detail="Optional selections must be add-ons")

    units = await billable_unit_count(session, business.id)
    lines, total, currency = [], Decimal("0.00"), None
    for code in codes:
        item = by_code[code]
        price = await current_price(session, item.id, now)
        if not price:
            raise HTTPException(status_code=409, detail=f"No effective price for {code}")
        if currency is None:
            currency = price.currency
        elif currency != price.currency:
            raise HTTPException(status_code=409, detail="A subscription cannot mix currencies")
        amount = calculate_item_total(item, price, 1, units)
        total += amount
        lines.append((item, price, amount))
    return now, units, currency or "KES", total, lines


@router.get("/catalogue")
async def read_catalogue(session: SessionDep, user=Depends(get_current_user)):
    return {"items": await _catalogue(session, datetime.now(timezone.utc))}


@router.get("/current")
async def current_subscription(
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    sub = (await session.execute(
        select(BusinessSubscription)
        .where(BusinessSubscription.business_id == business.id,
               BusinessSubscription.status.in_(("active", "trialing", "past_due", "draft")))
        .order_by(BusinessSubscription.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    return {
        "legacy_tier": business.subscription_tier,
        "legacy_trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
        "subscription": None if sub is None else {
            "id": str(sub.id), "status": sub.status, "currency": sub.currency,
            "starts_at": sub.starts_at.isoformat() if sub.starts_at else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        },
        "entitlements": await get_entitlements(session, business.id),
    }


@router.post("/quote")
async def quote_subscription(
    data: SelectionRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    _, units, currency, total, lines = await _price_selection(session, data, business)
    return {
        "currency": currency, "billable_units": units, "subtotal": str(total),
        "total": str(total),
        "items": [{
            "code": item.code, "name": item.name,
            "quantity": 1, "amount": str(amount),
            "features": item.features or {},
        } for item, _, amount in lines],
        "notice": "Quote only. No payment has been initiated and no subscription has been activated.",
    }


@router.post("/select", status_code=201)
async def select_subscription(
    data: SelectionRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    now, units, currency, total, lines = await _price_selection(session, data, business)
    sub = BusinessSubscription(
        business_id=business.id, status="draft", currency=currency,
    )
    session.add(sub)
    await session.flush()
    for item, price, amount in lines:
        session.add(BusinessSubscriptionItem(
            subscription_id=sub.id, catalog_item_id=item.id, price_version_id=price.id,
            item_code_snapshot=item.code, item_name_snapshot=item.name, quantity=1,
            unit_amount_snapshot=price.amount, total_amount_snapshot=amount,
            features_snapshot=item.features or {},
        ))
    await session.flush()
    return {
        "subscription_id": str(sub.id), "status": "draft",
        "currency": currency, "billable_units": units, "total": str(total),
        "notice": "Selection saved as a draft. It is not active and no payment was taken.",
    }


@router.get("/entitlements/{feature}")
async def check_entitlement(
    feature: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    entitlements = await get_entitlements(session, business.id)
    return {"feature": feature, "enabled": bool(entitlements.get(feature, False)),
            "entitlements": entitlements}


@router.get("/admin/catalogue", dependencies=[Depends(require_roles("platform_admin"))])
async def admin_catalogue(session: SessionDep):
    return {"items": await _catalogue(session, datetime.now(timezone.utc))}
