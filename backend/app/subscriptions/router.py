"""Business-scoped Rental OS subscription selection, invoices and history.

Catalogue administration is reserved for the separate platform-admin principal.
Selection and invoice issuance never collect payment or alter landlord rent
invoices, payment credentials, or settlement destinations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OwnerDep, SessionDep, get_current_business, get_current_user
from app.platform_admin.dependencies import PlatformAdminDep
from app.platform_admin.audit import record_platform_admin_event
from app.models.business import Business
from app.models.subscriptions import (
    BusinessSubscription, BusinessSubscriptionItem, SubscriptionCatalogItem,
    SubscriptionPriceVersion, SubscriptionInvoice, SubscriptionInvoiceLine,
    BusinessSubscriptionEvent,
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


class CatalogItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    features: dict | None = None
    display_order: int | None = None
    active: bool | None = None


class PriceVersionCreate(BaseModel):
    currency: str = Field(default="KES", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    billing_interval: Literal["monthly", "quarterly", "annual", "one_time"] = "monthly"
    included_units: int = Field(default=0, ge=0)
    per_unit_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    effective_from: datetime
    effective_to: datetime | None = None


class SelectionRequest(BaseModel):
    package_code: str = Field(min_length=1, max_length=80)
    addon_codes: list[str] = Field(default_factory=list, max_length=30)


async def _catalogue(session: AsyncSession, now: datetime, include_unpriced: bool = False, include_inactive: bool = False):
    query = select(SubscriptionCatalogItem)
    if not include_inactive:
        query = query.where(SubscriptionCatalogItem.active.is_(True))
    items = (await session.execute(
        query.order_by(SubscriptionCatalogItem.display_order, SubscriptionCatalogItem.name)
    )).scalars().all()
    output = []
    for item in items:
        price = await current_price(session, item.id, now)
        if not price and not include_unpriced:
            continue
        output.append({
            "id": str(item.id), "code": item.code, "name": item.name, "description": item.description,
            "item_type": item.item_type, "pricing_model": item.pricing_model, "active": item.active,
            "features": item.features or {}, "currency": price.currency if price else None,
            "billing_interval": price.billing_interval if price else None,
            "amount": str(price.amount) if price else None,
            "included_units": price.included_units if price else None,
            "per_unit_amount": str(price.per_unit_amount) if price else None,
            "effective_from": price.effective_from.isoformat() if price else None,
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
    package_interval = None
    for code in codes:
        item = by_code[code]
        price = await current_price(session, item.id, now)
        if not price:
            raise HTTPException(status_code=409, detail=f"No effective price for {code}")
        if code == data.package_code:
            package_interval = price.billing_interval
        elif item.pricing_model != "one_time" and price.billing_interval != package_interval:
            raise HTTPException(status_code=409, detail="Recurring add-ons must use the base package billing interval")
        if currency is None:
            currency = price.currency
        elif currency != price.currency:
            raise HTTPException(status_code=409, detail="A subscription cannot mix currencies")
        amount = calculate_item_total(item, price, 1, units)
        total += amount
        lines.append((item, price, amount))
    return now, units, currency or "KES", total, lines, package_interval or "monthly"


@router.get("/catalogue")
async def read_catalogue(session: SessionDep, user=Depends(get_current_user)):
    return {"items": await _catalogue(session, datetime.now(timezone.utc))}


@router.get("/current")
async def current_subscription(
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    # A live subscription outranks a draft. Ordering by `created_at` alone let a
    # selection made today hide the subscription that is actually running.
    status_rank = case(
        {"active": 0, "trialing": 0, "past_due": 1, "draft": 2},
        value=BusinessSubscription.status,
        else_=3,
    )
    sub = (await session.execute(
        select(BusinessSubscription)
        .where(BusinessSubscription.business_id == business.id,
               BusinessSubscription.status.in_(("active", "trialing", "past_due", "draft")))
        .order_by(status_rank, BusinessSubscription.created_at.desc())
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
    _, units, currency, total, lines, interval = await _price_selection(session, data, business)
    return {
        "currency": currency, "billing_interval": interval, "billable_units": units, "subtotal": str(total),
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
    owner: OwnerDep = None,
):
    now, units, currency, total, lines, interval = await _price_selection(session, data, business)
    # Serialize selections per business and prevent multiple live subscriptions.
    await session.scalar(select(Business).where(Business.id == business.id).with_for_update())
    live = await session.scalar(
        select(BusinessSubscription.id).where(
            BusinessSubscription.business_id == business.id,
            BusinessSubscription.status.in_(("active", "trialing", "past_due")),
        ).with_for_update()
    )
    if live:
        raise HTTPException(status_code=409, detail="An active subscription already exists; use the change-plan workflow")
    drafts = (await session.scalars(
        select(BusinessSubscription).where(
            BusinessSubscription.business_id == business.id,
            BusinessSubscription.status == "draft",
        ).with_for_update()
    )).all()
    for previous in drafts:
        open_invoice = await session.scalar(
            select(SubscriptionInvoice.id).where(
                SubscriptionInvoice.subscription_id == previous.id,
                SubscriptionInvoice.status.in_(("draft", "open")),
            ).limit(1)
        )
        if open_invoice:
            raise HTTPException(status_code=409, detail="An unpaid subscription invoice already exists")
        previous.status = "cancelled"
        session.add(BusinessSubscriptionEvent(
            business_id=business.id, subscription_id=previous.id,
            event_type="selection.replaced", actor_user_id=owner.id,
            event_metadata={"reason": "new_selection"},
        ))
    sub = BusinessSubscription(
        business_id=business.id, status="draft", currency=currency, billing_interval=interval,
    )
    session.add(sub)
    await session.flush()
    session.add(BusinessSubscriptionEvent(
        business_id=business.id, subscription_id=sub.id,
        event_type="selection.created", actor_user_id=owner.id,
        event_metadata={"currency": currency, "billing_interval": interval, "total": str(total)},
    ))
    for item, price, amount in lines:
        session.add(BusinessSubscriptionItem(
            subscription_id=sub.id, catalog_item_id=item.id, price_version_id=price.id,
            item_code_snapshot=item.code, item_name_snapshot=item.name, quantity=1,
            billing_interval_snapshot=price.billing_interval,
            unit_amount_snapshot=price.amount, total_amount_snapshot=amount,
            features_snapshot=item.features or {},
        ))
    await session.flush()
    return {
        "subscription_id": str(sub.id), "status": "draft",
        "currency": currency, "billing_interval": interval, "billable_units": units, "total": str(total),
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


@router.get("/admin/catalogue")
async def admin_catalogue(session: SessionDep, admin: PlatformAdminDep):
    return {"items": await _catalogue(session, datetime.now(timezone.utc), include_unpriced=True, include_inactive=True)}


@router.post("/admin/catalogue", status_code=201)
async def create_catalogue_item(data: CatalogItemCreate, session: SessionDep, admin: PlatformAdminDep, request: Request):
    if data.item_type == "package" and data.pricing_model == "one_time":
        raise HTTPException(status_code=422, detail="Base packages must use recurring pricing")
    existing = await session.scalar(
        select(SubscriptionCatalogItem).where(SubscriptionCatalogItem.code == data.code)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Catalogue code already exists")
    item = SubscriptionCatalogItem(**data.model_dump(), active=True)
    session.add(item)
    await session.flush()
    record_platform_admin_event(session, admin, "catalogue.item.created", target_type="subscription_catalog_item", target_id=str(item.id), metadata={"code": item.code, "item_type": item.item_type}, request=request)
    return {"id": str(item.id), "code": item.code, "active": item.active}


@router.put("/admin/catalogue/{item_id}")
async def update_catalogue_item(
    item_id: UUID,
    data: CatalogItemUpdate,
    session: SessionDep,
    admin: PlatformAdminDep,
    request: Request,
):
    item = await session.scalar(
        select(SubscriptionCatalogItem)
        .where(SubscriptionCatalogItem.id == item_id)
        .with_for_update()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Catalogue item not found")
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No catalogue changes supplied")
    for key, value in changes.items():
        if value is None and key != "description":
            raise HTTPException(status_code=422, detail=f"{key} cannot be null")
        setattr(item, key, value)
    record_platform_admin_event(
        session, admin, "catalogue.item.updated",
        target_type="subscription_catalog_item", target_id=str(item.id),
        metadata={"changed_fields": sorted(changes.keys()), "active": item.active},
        request=request,
    )
    await session.flush()
    return {"id": str(item.id), "code": item.code, "active": item.active,
            "name": item.name, "features": item.features or {}}


@router.post("/admin/catalogue/{item_id}/prices", status_code=201)
async def create_price_version(item_id: UUID, data: PriceVersionCreate, session: SessionDep, admin: PlatformAdminDep, request: Request):
    item = await session.scalar(
        select(SubscriptionCatalogItem).where(SubscriptionCatalogItem.id == item_id)
    )
    if not item or not item.active:
        raise HTTPException(status_code=404, detail="Active catalogue item not found")
    if item.item_type == "package" and data.billing_interval == "one_time":
        raise HTTPException(status_code=422, detail="Base packages must have a recurring billing interval")
    if (item.pricing_model == "one_time") != (data.billing_interval == "one_time"):
        raise HTTPException(status_code=422, detail="One-time pricing must use the one_time billing interval")
    if data.effective_from.tzinfo is None:
        raise HTTPException(status_code=422, detail="effective_from must include a timezone")
    if data.effective_to is not None:
        if data.effective_to.tzinfo is None or data.effective_to <= data.effective_from:
            raise HTTPException(status_code=422, detail="effective_to must be later and timezone-aware")
    # Serialize price-version writes even when the item has no rows yet.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"subscription-price:{item.id}"},
    )
    previous = (await session.execute(
        select(SubscriptionPriceVersion)
        .where(SubscriptionPriceVersion.catalog_item_id == item.id,
               SubscriptionPriceVersion.active.is_(True))
        .order_by(SubscriptionPriceVersion.effective_from.desc())
        .with_for_update()
    )).scalars().all()
    if previous and data.effective_from <= previous[0].effective_from:
        raise HTTPException(status_code=409, detail="New price must start after the latest price version")
    if previous and previous[0].effective_to is not None and data.effective_from < previous[0].effective_to:
        raise HTTPException(status_code=409, detail="New price overlaps an existing effective period")
    if previous and previous[0].effective_to is None:
        previous[0].effective_to = data.effective_from
    price = SubscriptionPriceVersion(catalog_item_id=item.id, **data.model_dump(), active=True)
    session.add(price)
    await session.flush()
    record_platform_admin_event(session, admin, "catalogue.price.created", target_type="subscription_catalog_item", target_id=str(item.id), metadata={"price_version_id": str(price.id), "currency": price.currency, "billing_interval": price.billing_interval, "amount": str(price.amount), "effective_from": price.effective_from.isoformat()}, request=request)
    return {"id": str(price.id), "catalog_item_id": str(item.id),
            "currency": price.currency, "amount": str(price.amount),
            "effective_from": price.effective_from.isoformat(),
            "effective_to": price.effective_to.isoformat() if price.effective_to else None}




@router.post("/{subscription_id}/invoice", status_code=201)
async def issue_subscription_invoice(
    subscription_id: UUID,
    session: SessionDep,
    business: Business = Depends(get_current_business),
    owner: OwnerDep = None,
):
    """Issue a Rental OS subscription invoice for a saved draft selection.

    This creates only a platform invoice. It does not call a payment provider,
    alter landlord rent records, or activate the subscription.
    """
    sub = await session.scalar(
        select(BusinessSubscription)
        .where(
            BusinessSubscription.id == subscription_id,
            BusinessSubscription.business_id == business.id,
        )
        .with_for_update()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription selection not found")
    if sub.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft selection can be invoiced")

    existing = await session.scalar(
        select(SubscriptionInvoice)
        .where(
            SubscriptionInvoice.subscription_id == sub.id,
            SubscriptionInvoice.status.in_(("draft", "open")),
        )
        .order_by(SubscriptionInvoice.created_at.desc())
        .limit(1)
    )
    if existing:
        return {
            "invoice_id": str(existing.id), "invoice_number": existing.invoice_number,
            "status": existing.status, "currency": existing.currency,
            "total": str(existing.total), "due_at": existing.due_at.isoformat() if existing.due_at else None,
            "idempotent": True,
        }

    items = (await session.scalars(
        select(BusinessSubscriptionItem)
        .where(BusinessSubscriptionItem.subscription_id == sub.id)
        .order_by(BusinessSubscriptionItem.created_at, BusinessSubscriptionItem.id)
    )).all()
    if not items:
        raise HTTPException(status_code=409, detail="Subscription selection has no billable items")
    total = sum((Decimal(item.total_amount_snapshot) for item in items), Decimal("0.00"))
    if total <= 0:
        raise HTTPException(status_code=409, detail="Zero-value subscriptions need an explicit activation flow")

    now = datetime.now(timezone.utc)
    invoice = SubscriptionInvoice(
        business_id=business.id,
        subscription_id=sub.id,
        invoice_number=f"ROS-SUB-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
        currency=sub.currency,
        billing_interval=sub.billing_interval,
        subtotal=total,
        total=total,
        status="open",
        due_at=now + timedelta(days=7),
    )
    session.add(invoice)
    await session.flush()
    for index, item in enumerate(items, start=1):
        session.add(SubscriptionInvoiceLine(
            invoice_id=invoice.id,
            line_number=index,
            item_code_snapshot=item.item_code_snapshot,
            item_name_snapshot=item.item_name_snapshot,
            quantity=item.quantity,
            billing_interval_snapshot=item.billing_interval_snapshot,
            unit_amount=item.unit_amount_snapshot,
            total_amount=item.total_amount_snapshot,
            features_snapshot=item.features_snapshot or {},
        ))
    session.add(BusinessSubscriptionEvent(
        business_id=business.id,
        subscription_id=sub.id,
        event_type="invoice.issued",
        actor_user_id=owner.id,
        event_metadata={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number,
                        "currency": invoice.currency, "total": str(invoice.total)},
    ))
    await session.flush()
    return {
        "invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number,
        "status": invoice.status, "currency": invoice.currency,
        "billing_interval": invoice.billing_interval, "total": str(invoice.total),
        "due_at": invoice.due_at.isoformat(), "idempotent": False,
        "notice": "Rental OS subscription invoice created. No payment was initiated and the subscription remains a draft.",
    }


@router.get("/invoices")
async def list_subscription_invoices(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    limit: int = 50,
    offset: int = 0,
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    invoices = (await session.scalars(
        select(SubscriptionInvoice)
        .where(SubscriptionInvoice.business_id == business.id)
        .order_by(SubscriptionInvoice.created_at.desc())
        .limit(limit).offset(offset)
    )).all()
    return {"invoices": [{
        "id": str(invoice.id), "invoice_number": invoice.invoice_number,
        "subscription_id": str(invoice.subscription_id), "status": invoice.status,
        "currency": invoice.currency, "total": str(invoice.total),
        "due_at": invoice.due_at.isoformat() if invoice.due_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
    } for invoice in invoices], "limit": limit, "offset": offset}


@router.get("/invoices/{invoice_id}")
async def get_subscription_invoice(
    invoice_id: UUID,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    invoice = await session.scalar(
        select(SubscriptionInvoice).where(
            SubscriptionInvoice.id == invoice_id,
            SubscriptionInvoice.business_id == business.id,
        )
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Subscription invoice not found")
    lines = (await session.scalars(
        select(SubscriptionInvoiceLine)
        .where(SubscriptionInvoiceLine.invoice_id == invoice.id)
        .order_by(SubscriptionInvoiceLine.line_number)
    )).all()
    return {
        "id": str(invoice.id), "invoice_number": invoice.invoice_number,
        "subscription_id": str(invoice.subscription_id), "status": invoice.status,
        "currency": invoice.currency, "billing_interval": invoice.billing_interval,
        "subtotal": str(invoice.subtotal), "total": str(invoice.total),
        "due_at": invoice.due_at.isoformat() if invoice.due_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "lines": [{
            "line_number": line.line_number, "code": line.item_code_snapshot,
            "name": line.item_name_snapshot, "quantity": line.quantity,
            "billing_interval": line.billing_interval_snapshot,
            "unit_amount": str(line.unit_amount), "total_amount": str(line.total_amount),
            "features": line.features_snapshot or {},
        } for line in lines],
    }


@router.get("/{subscription_id}/events")
async def subscription_events(
    subscription_id: UUID,
    session: SessionDep,
    business: Business = Depends(get_current_business),
    limit: int = 50,
):
    limit = max(1, min(limit, 100))
    sub = await session.scalar(select(BusinessSubscription.id).where(
        BusinessSubscription.id == subscription_id,
        BusinessSubscription.business_id == business.id,
    ))
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    events = (await session.scalars(
        select(BusinessSubscriptionEvent)
        .where(BusinessSubscriptionEvent.subscription_id == subscription_id)
        .order_by(desc(BusinessSubscriptionEvent.created_at))
        .limit(limit)
    )).all()
    return {"events": [{
        "event_type": event.event_type,
        "metadata": event.event_metadata or {},
        "created_at": event.created_at.isoformat(),
    } for event in events]}
