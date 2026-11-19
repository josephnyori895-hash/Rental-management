"""
Rent reminders must fire without an owner pressing a button.

The sweep itself already existed and was already idempotent per tenant per day;
what was missing was anything to call it. The free deployment target has no
scheduler add-on, so the web process hosts the loop and the daily guard is what
makes a restart harmless.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.core.scheduler import (
    run_monthly_rent,
    run_reminder_sweep,
    seconds_until_next_month_run,
    seconds_until_next_run,
)
from tests.conftest import requires_db


def test_next_run_is_later_today_when_the_hour_is_ahead():
    now = datetime(2026, 11, 14, 3, 30, tzinfo=timezone.utc)
    assert seconds_until_next_run(now, hour=5) == 5400


def test_next_run_rolls_to_tomorrow_once_the_hour_has_passed():
    now = datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)
    assert seconds_until_next_run(now, hour=5) == 20 * 3600


def test_the_exact_hour_waits_for_tomorrow():
    now = datetime(2026, 11, 14, 5, 0, tzinfo=timezone.utc)
    assert seconds_until_next_run(now, hour=5) == 24 * 3600


def test_an_impossible_hour_is_clamped_instead_of_raising():
    """The hour comes from the environment; a typo must not crash startup."""
    now = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
    assert seconds_until_next_run(now, hour=99) == 20 * 3600


@requires_db
async def test_the_sweep_reminds_a_tenant_once_a_day(client, businesses, db_session):
    from app.notifications.models import NotificationLog

    first, _ = businesses

    # The fixture seeds a rent reminder for today — which is exactly the state
    # the daily guard exists to honour. Clear it to observe the sweep itself.
    await db_session.execute(
        delete(NotificationLog).where(NotificationLog.template_name == "rent_reminder")
    )
    await db_session.flush()

    assert await run_reminder_sweep(db_session) >= 1
    # Running again the same day must send nothing: a duplicate reminder is a
    # tenant complaint, not a stronger nudge.
    assert await run_reminder_sweep(db_session) == 0

    count = await db_session.scalar(
        select(func.count())
        .select_from(NotificationLog)
        .where(
            NotificationLog.tenant_id == first.tenant.id,
            NotificationLog.template_name == "rent_reminder",
        )
    )
    assert count == 1


# ── The monthly rent run ───────────────────────────────────────────


def test_the_monthly_run_waits_for_the_first_of_next_month():
    """Mid-month is not a rent-run date; the next one is the following 1st."""
    now = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
    expected = (
        datetime(2026, 12, 1, 6, 0, tzinfo=timezone.utc) - now
    ).total_seconds()
    assert seconds_until_next_month_run(now, hour=6) == expected


def test_the_monthly_run_fires_later_on_the_first():
    now = datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)
    assert seconds_until_next_month_run(now, hour=6) == 5.5 * 3600


def test_the_monthly_run_at_its_exact_hour_waits_a_month():
    now = datetime(2026, 12, 1, 6, 0, tzinfo=timezone.utc)
    assert seconds_until_next_month_run(now, hour=6) == 31 * 24 * 3600


def test_the_monthly_run_rolls_from_december_into_january():
    now = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)
    expected = (
        datetime(2027, 1, 1, 6, 0, tzinfo=timezone.utc) - now
    ).total_seconds()
    assert seconds_until_next_month_run(now, hour=6) == expected


def test_an_impossible_hour_is_clamped_for_the_monthly_run():
    now = datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)
    assert seconds_until_next_month_run(now, hour=99) == 20 * 3600


@requires_db
async def test_the_scheduled_run_bills_the_month_once(client, businesses, db_session):
    """The 1st raises the month's rent, and a restart cannot raise it again."""
    from app.models.billing import Invoice
    from app.models.lease import Lease
    from app.models.property import Unit, UnitStatus

    first, _ = businesses
    unit = Unit(
        business_id=first.business.id,
        property_id=first.property.id,
        unit_number="SCHED1",
        status=UnitStatus.OCCUPIED.value,
        monthly_rent=Decimal("15000"),
    )
    db_session.add(unit)
    await db_session.flush()
    lease = Lease(
        business_id=first.business.id,
        unit_id=unit.id,
        tenant_id=first.tenant.id,
        property_id=first.property.id,
        start_date=date.today() - timedelta(days=60),
        rent_amount=Decimal("15000"),
        deposit_amount=Decimal("0"),
        payment_day=5,
        status="active",
    )
    db_session.add(lease)
    await db_session.flush()

    sweep = await run_monthly_rent(db_session)

    assert sweep.failed == []
    assert sweep.period_start == date.today().replace(day=1)
    invoices = (
        await db_session.execute(select(Invoice).where(Invoice.lease_id == lease.id))
    ).scalars().all()
    assert len(invoices) == 1
    assert invoices[0].period_start == date.today().replace(day=1)

    # The startup catch-up runs the same sweep again on every restart.
    again = await run_monthly_rent(db_session)
    assert again.created == 0
    assert again.failed == []
    assert (
        await db_session.execute(select(func.count()).select_from(Invoice).where(
            Invoice.lease_id == lease.id
        ))
    ).scalar() == 1
