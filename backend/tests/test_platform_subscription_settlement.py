from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.subscriptions.service import (
    _add_months,
    apply_verified_platform_subscription_payment,
)


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
