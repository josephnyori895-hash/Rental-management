from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.subscriptions.service import (
    _add_months,
    apply_verified_platform_subscription_payment,
    process_due_subscription_cancellations,
)
from tests.conftest import requires_db


def test_subscription_period_month_end_is_clamped():
    start = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    assert _add_months(start, 1) == datetime(2026, 2, 28, 12, 0, tzinfo=timezone.utc)


def test_subscription_annual_period_handles_leap_day():
    start = datetime(2024, 2, 29, 10, 0, tzinfo=timezone.utc)
    assert _add_months(start, 12) == datetime(2025, 2, 28, 10, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_unverified_platform_payment_never_touches_database():
    session = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await apply_verified_platform_subscription_payment(
            session, invoice_id="invoice-id", provider="platform-mpesa",
            provider_reference="ref-1", amount=Decimal("100.00"),
            currency="KES", provider_event_verified=False,
        )
    assert exc.value.status_code == 401
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_nonpositive_platform_payment_is_rejected_before_database_access():
    session = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await apply_verified_platform_subscription_payment(
            session, invoice_id="invoice-id", provider="platform-mpesa",
            provider_reference="ref-1", amount=Decimal("-1.00"),
            currency="KES", provider_event_verified=True,
        )
    assert exc.value.status_code == 422
    session.scalar.assert_not_awaited()


@requires_db
async def test_due_period_end_cancellation_is_processed_once(businesses, db_session):
    from sqlalchemy import select
    from app.models.subscriptions import BusinessSubscription, BusinessSubscriptionEvent

    first, _ = businesses
    subscription = BusinessSubscription(
        business_id=first.business.id,
        status="active",
        currency="KES",
        billing_interval="monthly",
        current_period_end=datetime.now(timezone.utc) - timedelta(minutes=1),
        cancel_at_period_end=True,
    )
    db_session.add(subscription)
    await db_session.flush()

    assert await process_due_subscription_cancellations(db_session) == 1
    assert subscription.status == "cancelled"
    assert subscription.cancel_at_period_end is False
    assert await process_due_subscription_cancellations(db_session) == 0

    events = (await db_session.scalars(
        select(BusinessSubscriptionEvent).where(
            BusinessSubscriptionEvent.subscription_id == subscription.id,
            BusinessSubscriptionEvent.event_type == "subscription.cancelled",
        )
    )).all()
    assert len(events) == 1
