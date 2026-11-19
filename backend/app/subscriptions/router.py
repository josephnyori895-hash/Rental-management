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
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, get_current_business, get_current_user, require_roles
from app.models.business import Business
from app.models.subscriptions import (
    BusinessSubscription, BusinessSubscriptionItem, SubscriptionCatalogItem,
    SubscriptionPriceVersion,
)
from app.subscriptions.service import (
    billable_unit_count, calculate_item_total, current_price, get_entitlements,
)

router = APIRouter(prefix="/subscriptions", tags=["platform subscriptions"])



class CatalogItemCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    item_type: str
    pricing_model: str
    features: dict = Field(default_factory=dict)
    display_order: int = 0

    @field_validator("item_type")
    @classmethod
    def valid_item_type(cls, value: str) -> str:
        if value not in {"package", "addon"}:
            raise ValueError("item_type must be package or addon")
        return value

    @field_validator("pricing_model")
    @classmethod
    def valid_pricing_model(cls, value: str) -> str:
        if value not in {"flat_recurring", "per_billable_unit", "one_time"}:
            raise ValueError("Unsupported pricing model")
        return value


class PriceVersionCreate(BaseModel):
    currency: str = Field(default="KES", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    included_units: int = Field(default=0, ge=0)
    per_unit_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    effective_from: datetime
    effective_to: datetime | None = None


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


@router.post("/admin/catalogue", status_code=201, dependencies=[Depends(require_roles("platform_admin"))])
async def create_catalogue_item(data: CatalogItemCreate, session: SessionDep):
    existing = await session.scalar(
        select(SubscriptionCatalogItem).where(SubscriptionCatalogItem.code == data.code)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Catalogue code already exists")
    item = SubscriptionCatalogItem(**data.model_dump(), active=True)
    session.add(item)
    await session.flush()
    return {"id": str(item.id), "code": item.code, "active": item.active}


@router.post("/admin/catalogue/{item_id}/prices", status_code=201,
             dependencies=[Depends(require_roles("platform_admin"))])
async def create_price_version(item_id: UUID, data: PriceVersionCreate, session: SessionDep):
    item = await session.scalar(
        select(SubscriptionCatalogItem).where(SubscriptionCatalogItem.id == item_id)
    )
    if not item or not item.active:
        raise HTTPException(status_code=404, detail="Active catalogue item not found")
    if data.effective_from.tzinfo is None:
        raise HTTPException(status_code=422, detail="effective_from must include a timezone")
    if data.effective_to is not None:
        if data.effective_to.tzinfo is None or data.effective_to <= data.effective_from:
            raise HTTPException(status_code=422, detail="effective_to must be later and timezone-aware")
    previous = (await session.execute(
        select(SubscriptionPriceVersion)
        .where(SubscriptionPriceVersion.catalog_item_id == item.id,
               SubscriptionPriceVersion.active.is_(True))
        .order_by(SubscriptionPriceVersion.effective_from.desc())
        .with_for_update()
    )).scalars().all()
    if previous and data.effective_from <= previous[0].effective_from:
        raise HTTPException(status_code=409, detail="New price must start after the latest price version")
    if previous and previous[0].effective_to is None:
        previous[0].effective_to = data.effective_from
    price = SubscriptionPriceVersion(catalog_item_id=item.id, **data.model_dump(), active=True)
    session.add(price)
    await session.flush()
    return {"id": str(price.id), "catalog_item_id": str(item.id),
            "currency": price.currency, "amount": str(price.amount),
            "effective_from": price.effective_from.isoformat(),
            "effective_to": price.effective_to.isoformat() if price.effective_to else None}


