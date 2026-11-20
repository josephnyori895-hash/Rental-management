"""Rental OS platform invoices: issuance, snapshots and tenant isolation.

These are Rental OS's own invoices — what it charges a landlord for the
software. They are deliberately separate from landlord rent invoices and
tenant payments, so every test here also checks that the rent side is
untouched.

The immutability trigger on `subscription_invoice_lines` is created by the
migration, not by `Base.metadata.create_all`, so it is exercised by the
fresh-install migration check rather than here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select

from tests.conftest import requires_db

BASE = "/api/v1/subscriptions"
NOW = datetime.now(timezone.utc)


async def make_item(session, code: str, *, amount: str = "1000.00", currency: str = "KES"):
    """A priced package, effective from yesterday."""
    from app.models.subscriptions import (
        SubscriptionCatalogItem,
        SubscriptionPriceVersion,
    )

    item = SubscriptionCatalogItem(
        code=code,
        name=code.replace("-", " ").title(),
        item_type="package",
        pricing_model="flat_recurring",
        features={"core": True},
        active=True,
        display_order=0,
    )
    session.add(item)
    await session.flush()

    price = SubscriptionPriceVersion(
        catalog_item_id=item.id,
        currency=currency,
        amount=Decimal(amount),
        included_units=0,
        per_unit_amount=Decimal("0.00"),
        effective_from=NOW - timedelta(days=1),
        active=True,
    )
    session.add(price)
    await session.flush()
    return item, price


async def draft_selection(client, business, code: str) -> str:
    response = await client.post(
        f"{BASE}/select", headers=business.bearer, json={"package_code": code}
    )
    assert response.status_code == 201, response.text
    return response.json()["subscription_id"]


@requires_db
async def test_issuing_an_invoice_records_snapshots_and_no_rent_movement(
    client, businesses, db_session
):
    """The invoice, its line snapshots and the event exist; rent is untouched."""
    from app.models.billing import Invoice, Payment
    from app.models.subscriptions import (
        BusinessSubscriptionEvent,
        SubscriptionInvoice,
        SubscriptionInvoiceLine,
    )

    first, _ = businesses
    await make_item(db_session, "invoice-plan", amount="1500.00")

    rent_invoices_before = await db_session.scalar(select(func.count(Invoice.id)))
    rent_payments_before = await db_session.scalar(select(func.count(Payment.id)))

    subscription_id = await draft_selection(client, first, "invoice-plan")
    issued = await client.post(f"{BASE}/{subscription_id}/invoice", headers=first.bearer)
    assert issued.status_code == 201, issued.text

    body = issued.json()
    assert body["idempotent"] is False
    assert body["status"] == "open"
    assert body["currency"] == "KES"
    assert body["billing_interval"] == "monthly"
    assert body["total"] == "1500.00"
    assert body["invoice_number"].startswith("ROS-SUB-")

    invoice = await db_session.scalar(
        select(SubscriptionInvoice).where(
            SubscriptionInvoice.id == UUID(body["invoice_id"])
        )
    )
    assert invoice is not None
    assert invoice.billing_interval == "monthly"
    assert invoice.subtotal == Decimal("1500.00")
    assert invoice.total == Decimal("1500.00")
    assert invoice.status == "open"
    assert invoice.due_at is not None

    lines = (
        await db_session.scalars(
            select(SubscriptionInvoiceLine)
            .where(SubscriptionInvoiceLine.invoice_id == invoice.id)
            .order_by(SubscriptionInvoiceLine.line_number)
        )
    ).all()
    assert len(lines) == 1
    line = lines[0]
    assert line.line_number == 1
    assert line.item_code_snapshot == "invoice-plan"
    assert line.billing_interval_snapshot == "monthly"
    assert line.quantity == 1
    assert line.unit_amount == Decimal("1500.00")
    assert line.total_amount == Decimal("1500.00")

    event = await db_session.scalar(
        select(BusinessSubscriptionEvent).where(
            BusinessSubscriptionEvent.subscription_id == UUID(subscription_id),
            BusinessSubscriptionEvent.event_type == "invoice.issued",
        )
    )
    assert event is not None
    assert event.event_metadata["invoice_id"] == body["invoice_id"]

    # Rental OS billing must never post to the landlord's rent ledger.
    assert await db_session.scalar(select(func.count(Invoice.id))) == rent_invoices_before
    assert await db_session.scalar(select(func.count(Payment.id))) == rent_payments_before


@requires_db
async def test_a_second_issue_request_returns_the_same_open_invoice(
    client, businesses, db_session
):
    from app.models.subscriptions import SubscriptionInvoice

    first, _ = businesses
    await make_item(db_session, "idempotent-plan")
    subscription_id = await draft_selection(client, first, "idempotent-plan")

    first_issue = await client.post(f"{BASE}/{subscription_id}/invoice", headers=first.bearer)
    second_issue = await client.post(f"{BASE}/{subscription_id}/invoice", headers=first.bearer)
    assert second_issue.status_code == 201, second_issue.text
    assert second_issue.json()["idempotent"] is True
    assert second_issue.json()["invoice_id"] == first_issue.json()["invoice_id"]

    count = await db_session.scalar(
        select(func.count(SubscriptionInvoice.id)).where(
            SubscriptionInvoice.subscription_id == UUID(subscription_id)
        )
    )
    assert count == 1


@requires_db
async def test_invoice_detail_and_list_are_scoped_to_the_calling_business(
    client, businesses, db_session
):
    first, second = businesses
    await make_item(db_session, "scoped-plan", amount="2500.00")
    subscription_id = await draft_selection(client, first, "scoped-plan")
    issued = await client.post(f"{BASE}/{subscription_id}/invoice", headers=first.bearer)
    invoice_id = issued.json()["invoice_id"]

    detail = await client.get(f"{BASE}/invoices/{invoice_id}", headers=first.bearer)
    assert detail.status_code == 200, detail.text
    assert detail.json()["billing_interval"] == "monthly"
    assert detail.json()["total"] == "2500.00"
    assert len(detail.json()["lines"]) == 1

    listing = await client.get(f"{BASE}/invoices", headers=first.bearer)
    assert listing.status_code == 200
    assert invoice_id in {row["id"] for row in listing.json()["invoices"]}

    # The other operator must not be able to read or list it.
    foreign_detail = await client.get(f"{BASE}/invoices/{invoice_id}", headers=second.bearer)
    assert foreign_detail.status_code == 404, foreign_detail.text
    foreign_list = await client.get(f"{BASE}/invoices", headers=second.bearer)
    assert foreign_list.status_code == 200
    assert invoice_id not in {row["id"] for row in foreign_list.json()["invoices"]}


@requires_db
async def test_only_a_draft_selection_can_be_invoiced(client, businesses, db_session):
    from app.models.subscriptions import BusinessSubscription

    first, _ = businesses
    item, price = await make_item(db_session, "live-plan")

    live = BusinessSubscription(
        business_id=first.business.id,
        status="active",
        currency=price.currency,
        billing_interval="monthly",
    )
    db_session.add(live)
    await db_session.flush()

    response = await client.post(f"{BASE}/{live.id}/invoice", headers=first.bearer)
    assert response.status_code == 409, response.text
