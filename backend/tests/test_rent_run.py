"""
The monthly rent run: one rent invoice per active lease per month.

Rent was invoiced once, at enrollment, and never again — so the rent roll, the
aged-receivables buckets and the arrears on every lease only ever reflected a
tenancy's first month. The reports were right about the data they had; the data
was the gap.

Two properties matter more than the happy path:

* **Idempotence.** A second run must not raise a second invoice. A duplicated
  rent invoice is not a cosmetic bug — it doubles the tenant's arrears and
  would be collected.
* **Posting.** An invoice the ledger has never heard of makes the rent roll and
  the balance sheet disagree, and a recurring run makes that disagreement
  recur.

The overlap tests are pure because `enroll_tenant` bills `start_date ..
start_date + 30 days`, a window that need not line up with a calendar month.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.billing.rent_run import (
    RentRunError,
    due_date_for,
    month_period,
    period_is_billed,
    run_rent_for_period,
)
from tests.conftest import enroll_tenant, requires_db

# ── Calendar arithmetic (no database) ──────────────────────────────


def test_month_period_spans_the_calendar_month():
    start, end = month_period(2026, 2)
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_month_period_handles_a_leap_february():
    _, end = month_period(2028, 2)
    assert end == date(2028, 2, 29)


def test_month_period_rejects_a_thirteenth_month():
    with pytest.raises(RentRunError):
        month_period(2026, 13)


def test_the_payment_day_is_clamped_to_a_short_month():
    """Day 31 must not spill into March."""
    assert due_date_for(date(2026, 2, 1), 31) == date(2026, 2, 28)
    assert due_date_for(date(2028, 2, 1), 31) == date(2028, 2, 29)
    assert due_date_for(date(2026, 4, 1), 31) == date(2026, 4, 30)
    assert due_date_for(date(2026, 11, 1), 5) == date(2026, 11, 5)


def test_an_enrollment_style_invoice_bills_the_month_exactly_once():
    """14 Nov .. 14 Dec covers November, so November must not be billed again."""
    assert period_is_billed(
        [(date(2026, 11, 14), date(2026, 12, 14))],
        date(2026, 11, 1),
        date(2026, 11, 30),
    )


def test_an_invoice_from_another_month_does_not_cover_this_one():
    assert not period_is_billed(
        [(date(2026, 10, 1), date(2026, 10, 31))],
        date(2026, 11, 1),
        date(2026, 11, 30),
    )


def test_a_missing_period_end_is_treated_as_a_single_day():
    assert period_is_billed(
        [(date(2026, 11, 1), None)], date(2026, 11, 1), date(2026, 11, 30)
    )
    assert not period_is_billed(
        [(date(2026, 11, 1), None)], date(2026, 12, 1), date(2026, 12, 31)
    )


async def test_a_period_that_has_not_started_is_refused():
    """The guard runs before the session is touched, so no database is needed."""
    start = date.today().replace(day=1)
    next_start = (start + timedelta(days=32)).replace(day=1)
    _, next_end = month_period(next_start.year, next_start.month)

    with pytest.raises(RentRunError):
        await run_rent_for_period(None, uuid.uuid4(), next_start, next_end)


# ── Database-backed behaviour ──────────────────────────────────────


async def _add_lease(
    session,
    business,
    *,
    unit_number: str,
    start_date: date,
    end_date: date | None = None,
    rent: str = "18000",
    payment_day: int = 5,
    status: str = "active",
):
    """An occupied unit with an active lease and no invoices of its own.

    Inserted directly rather than enrolled, because enrollment deliberately
    raises the month's rent invoice — which is the thing this run must not
    duplicate, not the thing it is being tested for.
    """
    from app.models.lease import Lease
    from app.models.property import Unit, UnitStatus

    unit = Unit(
        business_id=business.business.id,
        property_id=business.property.id,
        unit_number=unit_number,
        status=UnitStatus.OCCUPIED.value,
        monthly_rent=Decimal(rent),
    )
    session.add(unit)
    await session.flush()

    lease = Lease(
        business_id=business.business.id,
        unit_id=unit.id,
        tenant_id=business.tenant.id,
        property_id=business.property.id,
        start_date=start_date,
        end_date=end_date,
        rent_amount=Decimal(rent),
        deposit_amount=Decimal("0"),
        payment_day=payment_day,
        status=status,
    )
    session.add(lease)
    await session.flush()
    return lease


async def _rent_invoices(session, lease_id):
    from app.models.billing import Invoice

    return (
        await session.execute(
            select(Invoice).where(
                Invoice.lease_id == lease_id, Invoice.invoice_type == "rent"
            )
        )
    ).scalars().all()


def _current_period() -> tuple[date, date]:
    return month_period(date.today().year, date.today().month)


@requires_db
async def test_the_run_raises_one_invoice_per_active_lease(
    client, businesses, db_session
):
    first, _ = businesses
    lease = await _add_lease(
        db_session, first, unit_number="RUN1", start_date=date.today() - timedelta(days=60)
    )

    result = await run_rent_for_period(db_session, first.business.id, *_current_period())

    invoices = await _rent_invoices(db_session, lease.id)
    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice.amount == Decimal("18000.00")
    assert invoice.balance == invoice.amount
    assert invoice.status == "pending"
    assert invoice.period_start == date.today().replace(day=1)
    assert invoice.due_date.day == 5
    assert [r["lease_id"] for r in result.created] == [str(lease.id)]


@requires_db
async def test_the_raised_invoice_is_posted_to_the_ledger(client, businesses, db_session):
    """Dr Tenant Receivables / Cr Rental Income — the whole point of the run."""
    from app.accounting.models import ChartOfAccount, JournalEntry

    first, _ = businesses
    lease = await _add_lease(
        db_session, first, unit_number="RUN2", start_date=date.today() - timedelta(days=60)
    )

    result = await run_rent_for_period(db_session, first.business.id, *_current_period())
    invoice_id = next(
        r["invoice_id"] for r in result.created if r["lease_id"] == str(lease.id)
    )

    accounts = {
        account.id: account
        for account in (
            await db_session.execute(
                select(ChartOfAccount).where(
                    ChartOfAccount.business_id == first.business.id
                )
            )
        ).scalars().all()
    }
    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.source_id == uuid.UUID(invoice_id)
            )
        )
    ).scalars().all()

    assert len(entries) == 2, "a rent invoice posts a debit and a credit"
    debit = [e for e in entries if e.debit > 0]
    credit = [e for e in entries if e.credit > 0]
    assert len(debit) == 1 and len(credit) == 1
    assert accounts[debit[0].account_id].code == "1100"
    assert accounts[credit[0].account_id].code == "4000"
    assert credit[0].credit == Decimal("18000.00")


@requires_db
async def test_running_twice_does_not_double_bill(client, businesses, db_session):
    """A retried run must be safe: arrears are money a tenant will be asked for."""
    first, _ = businesses
    lease = await _add_lease(
        db_session, first, unit_number="RUN3", start_date=date.today() - timedelta(days=60)
    )

    first_run = await run_rent_for_period(db_session, first.business.id, *_current_period())
    second_run = await run_rent_for_period(db_session, first.business.id, *_current_period())

    assert [r["lease_id"] for r in first_run.created] == [str(lease.id)]
    assert second_run.created == []
    assert len(await _rent_invoices(db_session, lease.id)) == 1


@requires_db
async def test_the_enrollment_month_is_not_billed_twice(client, businesses, db_session):
    """Enrollment already raised this month's rent for a new tenancy."""
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000")
    lease_id = uuid.UUID(enrolled["body"]["lease_id"])

    result = await run_rent_for_period(db_session, first.business.id, *_current_period())

    assert all(r["lease_id"] != str(lease_id) for r in result.created)
    assert len(await _rent_invoices(db_session, lease_id)) == 1


@requires_db
async def test_leases_that_have_ended_are_not_billed(client, businesses, db_session):
    first, _ = businesses
    period_start, _ = _current_period()
    ended = await _add_lease(
        db_session,
        first,
        unit_number="RUN4",
        start_date=date.today() - timedelta(days=120),
        end_date=period_start - timedelta(days=1),
    )
    # A terminated lease often has no end_date at all, so status is the only
    # thing standing between it and another invoice.
    terminated = await _add_lease(
        db_session,
        first,
        unit_number="RUN5",
        start_date=date.today() - timedelta(days=120),
        status="terminated",
    )

    result = await run_rent_for_period(db_session, first.business.id, *_current_period())

    billed = {r["lease_id"] for r in result.created}
    assert str(ended.id) not in billed
    assert str(terminated.id) not in billed
    assert await _rent_invoices(db_session, ended.id) == []
    assert await _rent_invoices(db_session, terminated.id) == []


@requires_db
async def test_a_dry_run_reports_without_writing(client, businesses, db_session):
    first, _ = businesses
    lease = await _add_lease(
        db_session, first, unit_number="RUN6", start_date=date.today() - timedelta(days=60)
    )

    result = await run_rent_for_period(
        db_session, first.business.id, *_current_period(), dry_run=True
    )

    assert [r["lease_id"] for r in result.created] == [str(lease.id)]
    assert result.total_billed == Decimal("18000")
    assert await _rent_invoices(db_session, lease.id) == []


@requires_db
async def test_the_endpoint_defaults_to_the_current_month(client, businesses, db_session):
    first, _ = businesses
    lease = await _add_lease(
        db_session, first, unit_number="RUN7", start_date=date.today() - timedelta(days=60)
    )

    response = await client.post(
        "/api/v1/billing/rent-run", headers=first.bearer, json={"dry_run": True}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_start"] == str(date.today().replace(day=1))
    assert body["dry_run"] is True
    assert [r["lease_id"] for r in body["created"]] == [str(lease.id)]
    assert await _rent_invoices(db_session, lease.id) == []


@requires_db
async def test_the_endpoint_refuses_a_future_month(client, businesses):
    first, _ = businesses
    start = date.today().replace(day=1)
    next_start = (start + timedelta(days=32)).replace(day=1)

    response = await client.post(
        "/api/v1/billing/rent-run",
        headers=first.bearer,
        json={"year": next_start.year, "month": next_start.month},
    )

    assert response.status_code == 400
