"""Rental OS platform subscriptions: isolation, authorization and money rules.

The unit tests in `test_subscription_pricing.py` cover arithmetic. This file
covers the properties that cannot be proven without a database and a real ASGI
client:

  * one operator cannot read, quote or select against another operator's
    subscription state;
  * a normal business user cannot touch the platform catalogue, and staff
    provisioning cannot mint a platform administrator;
  * a selection is a draft — it never activates, charges, or posts rent;
  * entitlements come only from active/trialing subscriptions of the caller's
    own business, never from the request payload;
  * the database itself refuses negative money, unknown statuses and the other
    shapes the API is also supposed to reject.

Every write goes through the `db_session` fixture, which runs inside a
savepoint that is always rolled back, so `rental_test` is left as it was found.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from tests.conftest import requires_db

BASE = "/api/v1/subscriptions"
NOW = datetime.now(timezone.utc)


# ── Builders ────────────────────────────────────────────────────────


async def make_item(
    session,
    code: str,
    *,
    item_type: str = "package",
    pricing_model: str = "flat_recurring",
    features: dict | None = None,
    active: bool = True,
    amount: str | None = "1000.00",
    included_units: int = 0,
    per_unit: str = "0.00",
    currency: str = "KES",
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
):
    """A catalogue item plus one price version (pass ``amount=None`` for none)."""
    from app.models.subscriptions import (
        SubscriptionCatalogItem,
        SubscriptionPriceVersion,
    )

    item = SubscriptionCatalogItem(
        code=code,
        name=code.replace("_", " ").title(),
        item_type=item_type,
        pricing_model=pricing_model,
        features=features or {},
        active=active,
        display_order=0,
    )
    session.add(item)
    await session.flush()

    price = None
    if amount is not None:
        price = SubscriptionPriceVersion(
            catalog_item_id=item.id,
            currency=currency,
            amount=Decimal(amount),
            included_units=included_units,
            per_unit_amount=Decimal(per_unit),
            effective_from=effective_from or (NOW - timedelta(days=1)),
            effective_to=effective_to,
            active=True,
        )
        session.add(price)
        await session.flush()
    return item, price


async def make_platform_admin(session, business):
    """Platform staff. Provisioned out-of-band, never through `/auth/staff`."""
    from app.core.security import hash_password
    from app.models.business import User

    user = User(
        business_id=business.id,
        email=f"platform-{uuid4().hex[:10]}@rental.os",
        password_hash=hash_password("platform-password"),
        full_name="Platform Admin",
        role="platform_admin",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


def bearer_for(user) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def add_subscription(session, business, item, price, *, status="active", features=None):
    from app.models.subscriptions import BusinessSubscription, BusinessSubscriptionItem

    subscription = BusinessSubscription(
        business_id=business.id, status=status, currency=price.currency
    )
    session.add(subscription)
    await session.flush()
    session.add(
        BusinessSubscriptionItem(
            subscription_id=subscription.id,
            catalog_item_id=item.id,
            price_version_id=price.id,
            item_code_snapshot=item.code,
            item_name_snapshot=item.name,
            quantity=1,
            unit_amount_snapshot=price.amount,
            total_amount_snapshot=price.amount,
            features_snapshot=features if features is not None else (item.features or {}),
        )
    )
    await session.flush()
    return subscription


async def add_unit(session, seeded, *, number: str, deleted: bool = False):
    from app.models.property import Unit, UnitStatus

    unit = Unit(
        business_id=seeded.business.id,
        property_id=seeded.property.id,
        unit_number=number,
        status=UnitStatus.AVAILABLE.value,
        monthly_rent=Decimal("10000"),
        is_deleted=deleted,
    )
    session.add(unit)
    await session.flush()
    return unit


async def expect_refused(session, obj) -> None:
    """Insert that the database must refuse, without poisoning the transaction."""
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(obj)
            await session.flush()


# ── Unauthenticated access ──────────────────────────────────────────


@requires_db
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", f"{BASE}/catalogue", None),
        ("get", f"{BASE}/current", None),
        ("get", f"{BASE}/entitlements/sms_reminders", None),
        ("post", f"{BASE}/quote", {"package_code": "starter"}),
        ("post", f"{BASE}/select", {"package_code": "starter"}),
        ("get", f"{BASE}/admin/catalogue", None),
        (
            "post",
            f"{BASE}/admin/catalogue",
            {
                "code": "x1",
                "name": "X",
                "item_type": "package",
                "pricing_model": "flat_recurring",
            },
        ),
    ],
)
async def test_unauthenticated_requests_are_rejected(method, path, payload, client):
    if method == "get":
        response = await client.get(path)
    else:
        response = await client.post(path, json=payload)
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


# ── Authorization: catalogue is platform-admin only ─────────────────


@requires_db
async def test_business_owner_cannot_manage_the_platform_catalogue(
    client, businesses, db_session
):
    first, _ = businesses
    item, _price = await make_item(db_session, "owner-probe")

    created = await client.post(
        f"{BASE}/admin/catalogue",
        headers=first.bearer,
        json={
            "code": "owner-made",
            "name": "Owner Made",
            "item_type": "package",
            "pricing_model": "flat_recurring",
        },
    )
    assert created.status_code == 403, created.text

    priced = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=first.bearer,
        json={"amount": "1.00", "effective_from": NOW.isoformat()},
    )
    assert priced.status_code == 403, priced.text

    admin_list = await client.get(f"{BASE}/admin/catalogue", headers=first.bearer)
    assert admin_list.status_code == 403, admin_list.text


@requires_db
async def test_staff_provisioning_cannot_mint_a_platform_administrator(
    client, businesses, db_session
):
    """An owner must not be able to grant themselves the catalogue role."""
    from app.models.business import User

    first, _ = businesses
    attempted = []
    for role in ("platform_admin", "owner"):
        email = f"escalate-{role}@alpha.test"
        attempted.append(email)
        response = await client.post(
            "/api/v1/auth/staff",
            headers=first.bearer,
            json={
                "full_name": "Escalation Attempt",
                "email": email,
                "password": "escalation123",
                "role": role,
            },
        )
        assert response.status_code == 422, f"{role}: {response.status_code} {response.text}"

    created = await db_session.scalar(
        select(func.count(User.id)).where(User.email.in_(attempted))
    )
    assert created == 0


@requires_db
async def test_platform_admin_can_create_a_catalogue_item(client, businesses, db_session):
    first, _ = businesses
    admin = await make_platform_admin(db_session, first.business)

    created = await client.post(
        f"{BASE}/admin/catalogue",
        headers=bearer_for(admin),
        json={
            "code": "platform-made",
            "name": "Platform Made",
            "item_type": "package",
            "pricing_model": "flat_recurring",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["code"] == "platform-made"


# ── Catalogue visibility ────────────────────────────────────────────


@requires_db
async def test_catalogue_hides_inactive_items_and_items_without_an_effective_price(
    client, businesses, db_session
):
    first, _ = businesses
    await make_item(db_session, "visible-plan")
    await make_item(db_session, "retired-plan", active=False)
    await make_item(db_session, "future-plan", effective_from=NOW + timedelta(days=30))
    await make_item(db_session, "priceless-plan", amount=None)

    response = await client.get(f"{BASE}/catalogue", headers=first.bearer)
    assert response.status_code == 200, response.text
    codes = {item["code"] for item in response.json()["items"]}

    assert "visible-plan" in codes
    assert "retired-plan" not in codes
    assert "future-plan" not in codes
    assert "priceless-plan" not in codes


@requires_db
async def test_catalogue_is_identical_for_every_business(client, businesses, db_session):
    first, second = businesses
    await make_item(db_session, "shared-plan", amount="2500.00")

    alpha = await client.get(f"{BASE}/catalogue", headers=first.bearer)
    bravo = await client.get(f"{BASE}/catalogue", headers=second.bearer)
    assert alpha.status_code == 200 and bravo.status_code == 200

    alpha_items = {i["code"]: i for i in alpha.json()["items"]}
    bravo_items = {i["code"]: i for i in bravo.json()["items"]}
    assert alpha_items["shared-plan"]["amount"] == "2500.00"
    assert bravo_items["shared-plan"]["amount"] == "2500.00"


# ── Selection validation ────────────────────────────────────────────


@requires_db
@pytest.mark.parametrize(
    ("request_body", "expected"),
    [
        ({"package_code": "ghost-plan"}, 422),
        ({"package_code": "some-addon"}, 422),
        ({"package_code": "base-plan", "addon_codes": ["base-plan"]}, 422),
        ({"package_code": "base-plan", "addon_codes": ["some-addon", "some-addon"]}, 422),
        ({"package_code": "base-plan", "addon_codes": ["other-package"]}, 422),
        ({"package_code": "base-plan", "addon_codes": ["ghost-addon"]}, 422),
    ],
)
async def test_invalid_selections_are_rejected(request_body, expected, client, businesses, db_session):
    first, _ = businesses
    await make_item(db_session, "base-plan")
    await make_item(db_session, "some-addon", item_type="addon")
    await make_item(db_session, "other-package", item_type="package")
    await make_item(db_session, "ghost-addon", item_type="addon", active=False)

    response = await client.post(f"{BASE}/quote", headers=first.bearer, json=request_body)
    assert response.status_code == expected, response.text


@requires_db
async def test_a_selection_cannot_mix_currencies(client, businesses, db_session):
    first, _ = businesses
    await make_item(db_session, "kes-plan", currency="KES")
    await make_item(db_session, "usd-addon", item_type="addon", currency="USD")

    response = await client.post(
        f"{BASE}/quote",
        headers=first.bearer,
        json={"package_code": "kes-plan", "addon_codes": ["usd-addon"]},
    )
    assert response.status_code == 409, response.text


@requires_db
async def test_selection_fails_closed_when_no_price_is_effective(client, businesses, db_session):
    first, _ = businesses
    await make_item(
        db_session,
        "lapsed-plan",
        effective_from=NOW - timedelta(days=10),
        effective_to=NOW - timedelta(days=1),
    )

    response = await client.post(
        f"{BASE}/quote", headers=first.bearer, json={"package_code": "lapsed-plan"}
    )
    assert response.status_code == 409, response.text


# ── Pricing behaviour through the real endpoint ─────────────────────


@requires_db
async def test_flat_recurring_quote_is_decimal_and_exact(client, businesses, db_session):
    first, _ = businesses
    await make_item(db_session, "flat-plan", amount="1250.55")

    response = await client.post(
        f"{BASE}/quote", headers=first.bearer, json={"package_code": "flat-plan"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == "1250.55"
    assert body["currency"] == "KES"
    assert body["subtotal"] == body["total"]


@requires_db
async def test_billable_units_count_every_non_deleted_unit_of_the_caller(
    client, businesses, db_session
):
    """Occupied and available count; soft-deleted does not; other tenants never."""
    from app.models.property import Unit

    first, second = businesses
    # The seed already gives each business one occupied unit.
    await add_unit(db_session, first, number="A2")
    await add_unit(db_session, first, number="A3")
    await add_unit(db_session, first, number="A4", deleted=True)

    await make_item(
        db_session,
        "metered-plan",
        pricing_model="per_billable_unit",
        amount="500.00",
        included_units=0,
        per_unit="25.00",
    )

    alpha = await client.post(
        f"{BASE}/quote", headers=first.bearer, json={"package_code": "metered-plan"}
    )
    assert alpha.status_code == 200, alpha.text
    assert alpha.json()["billable_units"] == 3
    assert alpha.json()["total"] == "575.00"

    bravo = await client.post(
        f"{BASE}/quote", headers=second.bearer, json={"package_code": "metered-plan"}
    )
    assert bravo.status_code == 200, bravo.text
    assert bravo.json()["billable_units"] == 1
    assert bravo.json()["total"] == "525.00"

    live_units = await db_session.scalar(
        select(func.count(Unit.id)).where(
            Unit.business_id == first.business.id, Unit.is_deleted.is_(False)
        )
    )
    assert live_units == 3


@requires_db
async def test_included_units_are_subtracted_from_the_billable_count(
    client, businesses, db_session
):
    first, _ = businesses
    await make_item(
        db_session,
        "bundled-plan",
        pricing_model="per_billable_unit",
        amount="500.00",
        included_units=5,
        per_unit="25.00",
    )

    response = await client.post(
        f"{BASE}/quote", headers=first.bearer, json={"package_code": "bundled-plan"}
    )
    assert response.status_code == 200, response.text
    # One unit, five included: the allowance covers it.
    assert response.json()["total"] == "500.00"


@requires_db
async def test_one_time_pricing_quotes_like_a_flat_fee(client, businesses, db_session):
    first, _ = businesses
    await make_item(db_session, "setup-fee", pricing_model="one_time", amount="7500.00")

    response = await client.post(
        f"{BASE}/quote", headers=first.bearer, json={"package_code": "setup-fee"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == "7500.00"


# ── Draft-only selection ────────────────────────────────────────────


@requires_db
async def test_select_creates_a_draft_and_nothing_else(client, businesses, db_session):
    from app.models.billing import Invoice, Payment
    from app.models.subscriptions import (
        BusinessSubscription,
        BusinessSubscriptionItem,
        SubscriptionInvoice,
        SubscriptionPayment,
    )

    first, _ = businesses
    await make_item(db_session, "draft-plan", features={"reports": True})

    invoices_before = await db_session.scalar(select(func.count(Invoice.id)))
    payments_before = await db_session.scalar(select(func.count(Payment.id)))

    response = await client.post(
        f"{BASE}/select", headers=first.bearer, json={"package_code": "draft-plan"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert "not active" in body["notice"]
    assert "no payment was taken" in body["notice"]

    subscription = await db_session.get(BusinessSubscription, body["subscription_id"])
    assert subscription is not None
    assert subscription.status == "draft"
    assert subscription.starts_at is None

    lines = await db_session.scalar(
        select(func.count(BusinessSubscriptionItem.id)).where(
            BusinessSubscriptionItem.subscription_id == subscription.id
        )
    )
    assert lines == 1

    # No money moved and no rent record was touched.
    assert await db_session.scalar(select(func.count(SubscriptionInvoice.id))) == 0
    assert await db_session.scalar(select(func.count(SubscriptionPayment.id))) == 0
    assert await db_session.scalar(select(func.count(Invoice.id))) == invoices_before
    assert await db_session.scalar(select(func.count(Payment.id))) == payments_before

    # A draft grants no entitlement.
    entitlements = await client.get(f"{BASE}/entitlements/reports", headers=first.bearer)
    assert entitlements.json()["enabled"] is False


@requires_db
async def test_selection_snapshots_price_and_features(client, businesses, db_session):
    from app.models.subscriptions import BusinessSubscriptionItem

    first, _ = businesses
    await make_item(db_session, "snapshot-plan", amount="999.00", features={"api": True})

    response = await client.post(
        f"{BASE}/select", headers=first.bearer, json={"package_code": "snapshot-plan"}
    )
    assert response.status_code == 201, response.text

    line = await db_session.scalar(select(BusinessSubscriptionItem))
    assert line.item_code_snapshot == "snapshot-plan"
    assert line.unit_amount_snapshot == Decimal("999.00")
    assert line.total_amount_snapshot == Decimal("999.00")
    assert line.features_snapshot == {"api": True}


# ── Entitlements ────────────────────────────────────────────────────


@requires_db
@pytest.mark.parametrize(
    ("status", "enabled"),
    [
        ("active", True),
        ("trialing", True),
        ("draft", False),
        ("past_due", False),
        ("cancelled", False),
    ],
)
async def test_entitlements_follow_subscription_status(
    status, enabled, client, businesses, db_session
):
    first, _ = businesses
    item, price = await make_item(db_session, "feature-plan", features={"sms_reminders": True})
    await add_subscription(db_session, first.business, item, price, status=status)

    response = await client.get(f"{BASE}/entitlements/sms_reminders", headers=first.bearer)
    assert response.status_code == 200, response.text
    assert response.json()["enabled"] is enabled


@requires_db
async def test_entitlements_do_not_cross_business_boundaries(client, businesses, db_session):
    first, second = businesses
    item, price = await make_item(db_session, "cross-plan", features={"premium": True})
    await add_subscription(db_session, first.business, item, price, status="active")

    alpha = await client.get(f"{BASE}/entitlements/premium", headers=first.bearer)
    bravo = await client.get(f"{BASE}/entitlements/premium", headers=second.bearer)
    assert alpha.json()["enabled"] is True
    assert bravo.json()["enabled"] is False
    assert "premium" not in bravo.json()["entitlements"]


@requires_db
async def test_entitlement_cannot_be_obtained_from_the_request(client, businesses, db_session):
    """The value is read from the database, never from what the caller sends."""
    first, _ = businesses
    await make_item(db_session, "plain-plan")

    await client.post(
        f"{BASE}/select",
        headers=first.bearer,
        json={"package_code": "plain-plan", "features": {"gold": True}, "entitled": True},
    )

    for path in (f"{BASE}/entitlements/gold?enabled=true", f"{BASE}/entitlements/gold?entitled=1"):
        response = await client.get(path, headers=first.bearer)
        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert response.json()["entitlements"].get("gold") is None


# ── Tenant isolation ────────────────────────────────────────────────


@requires_db
async def test_current_subscription_is_scoped_to_the_caller(client, businesses, db_session):
    first, second = businesses
    item, price = await make_item(db_session, "isolated-plan")
    alpha_sub = await add_subscription(db_session, first.business, item, price, status="active")

    alpha = await client.get(f"{BASE}/current", headers=first.bearer)
    bravo = await client.get(f"{BASE}/current", headers=second.bearer)

    assert alpha.status_code == 200 and bravo.status_code == 200
    assert alpha.json()["subscription"]["id"] == str(alpha_sub.id)
    assert bravo.json()["subscription"] is None
    assert str(alpha_sub.id) not in bravo.text


@requires_db
async def test_draft_does_not_shadow_an_active_subscription(client, businesses, db_session):
    """`/current` must report the live subscription, not the newest draft."""
    first, _ = businesses
    item, price = await make_item(db_session, "live-plan")
    live = await add_subscription(db_session, first.business, item, price, status="active")
    await add_subscription(db_session, first.business, item, price, status="draft")

    response = await client.get(f"{BASE}/current", headers=first.bearer)
    assert response.status_code == 200, response.text
    assert response.json()["subscription"]["status"] == "active"
    assert response.json()["subscription"]["id"] == str(live.id)


# ── Price version effective dates ───────────────────────────────────


@requires_db
async def test_price_effective_window_boundaries(db_session, businesses):
    from app.subscriptions.service import current_price

    first, _ = businesses
    start = NOW.replace(microsecond=0)
    end = start + timedelta(days=10)
    item, _price = await make_item(
        db_session, "window-plan", effective_from=start, effective_to=end
    )

    assert await current_price(db_session, item.id, start) is not None
    assert await current_price(db_session, item.id, end - timedelta(seconds=1)) is not None
    # `effective_to` is exclusive: the replacement price owns that instant.
    assert await current_price(db_session, item.id, end) is None
    assert await current_price(db_session, item.id, start - timedelta(seconds=1)) is None


@requires_db
async def test_new_price_must_start_after_the_latest_version(client, businesses, db_session):
    first, _ = businesses
    item, _price = await make_item(db_session, "versioned-plan", effective_from=NOW)
    admin = await make_platform_admin(db_session, first.business)
    headers = bearer_for(admin)

    same_start = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={"amount": "2000.00", "effective_from": NOW.isoformat()},
    )
    assert same_start.status_code == 409, same_start.text

    earlier = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={"amount": "2000.00", "effective_from": (NOW - timedelta(days=5)).isoformat()},
    )
    assert earlier.status_code == 409, earlier.text

    later = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={"amount": "2000.00", "effective_from": (NOW + timedelta(days=1)).isoformat()},
    )
    assert later.status_code == 201, later.text
    assert later.json()["effective_to"] is None


@requires_db
async def test_price_version_rejects_naive_and_inverted_windows(client, businesses, db_session):
    first, _ = businesses
    item, _price = await make_item(db_session, "windowed-plan")
    admin = await make_platform_admin(db_session, first.business)
    headers = bearer_for(admin)

    naive = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={"amount": "10.00", "effective_from": "2030-01-01T00:00:00"},
    )
    assert naive.status_code == 422, naive.text

    inverted = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={
            "amount": "10.00",
            "effective_from": "2030-01-01T00:00:00+00:00",
            "effective_to": "2029-01-01T00:00:00+00:00",
        },
    )
    assert inverted.status_code == 422, inverted.text


@requires_db
async def test_price_version_rejects_bad_currency_and_negative_amount(
    client, businesses, db_session
):
    first, _ = businesses
    item, _price = await make_item(db_session, "priced-plan")
    admin = await make_platform_admin(db_session, first.business)
    headers = bearer_for(admin)

    bad_currency = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={
            "amount": "10.00",
            "currency": "kes",
            "effective_from": (NOW + timedelta(days=2)).isoformat(),
        },
    )
    assert bad_currency.status_code == 422, bad_currency.text

    negative = await client.post(
        f"{BASE}/admin/catalogue/{item.id}/prices",
        headers=headers,
        json={"amount": "-1.00", "effective_from": (NOW + timedelta(days=2)).isoformat()},
    )
    assert negative.status_code == 422, negative.text


# ── Database-level constraints ──────────────────────────────────────


@requires_db
async def test_database_refuses_invalid_catalogue_and_price_shapes(db_session):
    from app.models.subscriptions import (
        SubscriptionCatalogItem,
        SubscriptionPriceVersion,
    )

    await expect_refused(
        db_session,
        SubscriptionCatalogItem(
            code="bad-type",
            name="Bad",
            item_type="module",
            pricing_model="flat_recurring",
            features={},
            active=True,
            display_order=0,
        ),
    )

    await expect_refused(
        db_session,
        SubscriptionCatalogItem(
            code="bad-model",
            name="Bad",
            item_type="package",
            pricing_model="per_seat",
            features={},
            active=True,
            display_order=0,
        ),
    )

    item = SubscriptionCatalogItem(
        code="good-item",
        name="Good",
        item_type="package",
        pricing_model="flat_recurring",
        features={},
        active=True,
        display_order=0,
    )
    db_session.add(item)
    await db_session.flush()

    await expect_refused(
        db_session,
        SubscriptionPriceVersion(
            catalog_item_id=item.id,
            currency="KES",
            amount=Decimal("-0.01"),
            included_units=0,
            per_unit_amount=Decimal("0"),
            effective_from=NOW,
            active=True,
        ),
    )
    await expect_refused(
        db_session,
        SubscriptionPriceVersion(
            catalog_item_id=item.id,
            currency="kes",
            amount=Decimal("1"),
            included_units=0,
            per_unit_amount=Decimal("0"),
            effective_from=NOW,
            active=True,
        ),
    )
    await expect_refused(
        db_session,
        SubscriptionPriceVersion(
            catalog_item_id=item.id,
            currency="KES",
            amount=Decimal("1"),
            included_units=0,
            per_unit_amount=Decimal("0"),
            effective_from=NOW,
            effective_to=NOW - timedelta(days=1),
            active=True,
        ),
    )


@requires_db
async def test_database_refuses_invalid_subscription_status_and_quantity(
    db_session, businesses
):
    from app.models.subscriptions import BusinessSubscription, BusinessSubscriptionItem

    first, _ = businesses
    item, price = await make_item(db_session, "constrained-plan")

    await expect_refused(
        db_session,
        BusinessSubscription(business_id=first.business.id, status="comped", currency="KES"),
    )

    subscription = BusinessSubscription(
        business_id=first.business.id, status="draft", currency="KES"
    )
    db_session.add(subscription)
    await db_session.flush()

    await expect_refused(
        db_session,
        BusinessSubscriptionItem(
            subscription_id=subscription.id,
            catalog_item_id=item.id,
            price_version_id=price.id,
            item_code_snapshot=item.code,
            item_name_snapshot=item.name,
            quantity=0,
            unit_amount_snapshot=Decimal("1"),
            total_amount_snapshot=Decimal("1"),
            features_snapshot={},
        ),
    )
    await expect_refused(
        db_session,
        BusinessSubscriptionItem(
            subscription_id=subscription.id,
            catalog_item_id=item.id,
            price_version_id=price.id,
            item_code_snapshot=item.code,
            item_name_snapshot=item.name,
            quantity=1,
            unit_amount_snapshot=Decimal("-1"),
            total_amount_snapshot=Decimal("-1"),
            features_snapshot={},
        ),
    )


@requires_db
async def test_database_refuses_duplicate_catalogue_codes_and_duplicate_lines(
    db_session, businesses
):
    from app.models.subscriptions import (
        BusinessSubscription,
        BusinessSubscriptionItem,
        SubscriptionCatalogItem,
    )

    first, _ = businesses
    item, price = await make_item(db_session, "unique-plan")

    await expect_refused(
        db_session,
        SubscriptionCatalogItem(
            code="unique-plan",
            name="Duplicate",
            item_type="package",
            pricing_model="flat_recurring",
            features={},
            active=True,
            display_order=0,
        ),
    )

    subscription = BusinessSubscription(
        business_id=first.business.id, status="draft", currency="KES"
    )
    db_session.add(subscription)
    await db_session.flush()

    db_session.add(
        BusinessSubscriptionItem(
            subscription_id=subscription.id,
            catalog_item_id=item.id,
            price_version_id=price.id,
            item_code_snapshot=item.code,
            item_name_snapshot=item.name,
            quantity=1,
            unit_amount_snapshot=Decimal("1"),
            total_amount_snapshot=Decimal("1"),
            features_snapshot={},
        )
    )
    await db_session.flush()

    await expect_refused(
        db_session,
        BusinessSubscriptionItem(
            subscription_id=subscription.id,
            catalog_item_id=item.id,
            price_version_id=price.id,
            item_code_snapshot=item.code,
            item_name_snapshot=item.name,
            quantity=2,
            unit_amount_snapshot=Decimal("1"),
            total_amount_snapshot=Decimal("2"),
            features_snapshot={},
        ),
    )


@requires_db
async def test_deleting_a_business_cascades_its_subscriptions(db_session, businesses):
    from app.models.business import Business
    from app.models.subscriptions import BusinessSubscription

    item, price = await make_item(db_session, "cascade-plan")
    business = Business(name="Cascade Co", slug=f"cascade-{uuid4().hex}", owner_id=uuid4())
    db_session.add(business)
    await db_session.flush()

    subscription = await add_subscription(db_session, business, item, price)

    await db_session.delete(business)
    await db_session.flush()

    # Count from the database: the identity map would still hold the object.
    remaining = await db_session.scalar(
        select(func.count(BusinessSubscription.id)).where(
            BusinessSubscription.id == subscription.id
        )
    )
    assert remaining == 0


@requires_db
async def test_a_priced_catalogue_item_cannot_be_deleted(db_session, businesses):
    """RESTRICT: history referenced by a price version is not silently cascaded."""
    item, _price = await make_item(db_session, "restricted-plan")

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(item)
            await db_session.flush()
