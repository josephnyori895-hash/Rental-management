"""
Enrollment raises invoices, so enrollment must post them.

`enroll_tenant` is the only path in the application that creates a rent invoice
or a deposit invoice. It created both, flushed, committed — and called no
posting hook at all. Every tenancy therefore began with invoices the ledger had
never heard of: the rent roll and the balance sheet disagreed from day one, for
every tenant, and nothing anywhere said so.

These tests go through `POST /tenants/enroll` rather than inserting invoices
directly, because the thing that was broken is the *endpoint's* posting, not the
posting function. Inserting an invoice would pass even with the bug present.

Rent credits rental income. The deposit credits Security Deposits Payable —
it is a liability, not revenue (see `tests/test_deposits.py`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from tests.conftest import enroll_tenant, requires_db

RENT_INCOME_CODE = "4000"
DEPOSIT_LIABILITY_CODE = "2100"
RECEIVABLE_CODE = "1100"


async def _invoices_for(session, tenant_id):
    from app.models.billing import Invoice

    return (
        await session.execute(select(Invoice).where(Invoice.tenant_id == tenant_id))
    ).scalars().all()


async def _ledger_for_business(session, business_id):
    from app.accounting.models import ChartOfAccount, JournalEntry

    accounts = {
        account.id: account
        for account in (
            await session.execute(
                select(ChartOfAccount).where(ChartOfAccount.business_id == business_id)
            )
        ).scalars().all()
    }
    entries = (
        await session.execute(
            select(JournalEntry).where(JournalEntry.business_id == business_id)
        )
    ).scalars().all()
    return accounts, entries


def _codes_for(entries, accounts):
    """The account codes an invoice's entries touch, keyed by source id."""
    by_source: dict = {}
    for entry in entries:
        by_source.setdefault(str(entry.source_id), []).append(entry)
    return by_source


@requires_db
async def test_enrollment_posts_both_invoices_it_raises(client, businesses, db_session):
    """The core defect: two invoices created, two journal entries posted."""
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000", deposit="15000")
    tenant_id = enrolled["body"]["tenant_id"]

    invoices = await _invoices_for(db_session, tenant_id)
    assert len(invoices) == 2, "enrollment raises a rent and a deposit invoice"

    accounts, entries = await _ledger_for_business(db_session, first.business.id)

    for invoice in invoices:
        invoice_entries = [e for e in entries if str(e.source_id) == str(invoice.id)]
        assert len(invoice_entries) == 2, (
            f"{invoice.invoice_type} invoice {invoice.id} has no journal entry"
        )

        debit, credit = (
            [e for e in invoice_entries if e.debit > 0],
            [e for e in invoice_entries if e.credit > 0],
        )
        assert len(debit) == 1 and len(credit) == 1

        assert accounts[debit[0].account_id].code == RECEIVABLE_CODE
        assert debit[0].debit == invoice.amount
        assert credit[0].credit == invoice.amount, "each entry must balance"
        assert accounts[credit[0].account_id].code != RECEIVABLE_CODE


@requires_db
async def test_the_rent_invoice_credits_rental_income(client, businesses, db_session):
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000")
    tenant_id = enrolled["body"]["tenant_id"]

    invoices = await _invoices_for(db_session, tenant_id)
    rent_invoice = next(i for i in invoices if i.invoice_type == "rent")

    accounts, entries = await _ledger_for_business(db_session, first.business.id)
    invoice_entries = [e for e in entries if str(e.source_id) == str(rent_invoice.id)]
    credited = [e for e in invoice_entries if e.credit > 0]

    assert len(credited) == 1
    assert accounts[credited[0].account_id].code == RENT_INCOME_CODE
    assert credited[0].credit == Decimal("12000.00")


@requires_db
async def test_the_deposit_invoice_credits_the_liability(client, businesses, db_session):
    """A deposit is money owed back, so it must not inflate income."""
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, deposit="15000")
    tenant_id = enrolled["body"]["tenant_id"]

    invoices = await _invoices_for(db_session, tenant_id)
    deposit_invoice = next(i for i in invoices if i.invoice_type == "deposit")

    accounts, entries = await _ledger_for_business(db_session, first.business.id)
    invoice_entries = [e for e in entries if str(e.source_id) == str(deposit_invoice.id)]
    credited = [e for e in invoice_entries if e.credit > 0]

    assert len(credited) == 1
    assert accounts[credited[0].account_id].code == DEPOSIT_LIABILITY_CODE
    assert credited[0].credit == Decimal("15000.00")
    assert all(
        accounts[e.account_id].code != RENT_INCOME_CODE for e in invoice_entries
    )


@requires_db
async def test_no_deposit_invoice_when_the_deposit_is_zero(
    client, businesses, db_session
):
    """No deposit invoice, and therefore no deposit posting either."""
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, deposit="0")
    tenant_id = enrolled["body"]["tenant_id"]

    invoices = await _invoices_for(db_session, tenant_id)
    assert [i.invoice_type for i in invoices] == ["rent"]

    accounts, entries = await _ledger_for_business(db_session, first.business.id)
    deposit_account = next(a for a in accounts.values() if a.code == DEPOSIT_LIABILITY_CODE)
    assert all(
        entry.account_id != deposit_account.id for entry in entries
    ), "no deposit was raised, so nothing may touch Deposits Payable"


@requires_db
async def test_the_ledger_balances_after_enrollment(client, businesses, db_session):
    """Every journal entry posted must balance — the property that was absent.

    Asserted globally rather than per invoice, so an unbalanced entry from
    anywhere in enrollment fails here.
    """
    first, _ = businesses
    await enroll_tenant(db_session, client, first, rent="12000", deposit="15000")

    accounts, entries = await _ledger_for_business(db_session, first.business.id)
    by_source: dict[str, list] = {}
    for entry in entries:
        by_source.setdefault(str(entry.source_id), []).append(entry)

    assert by_source, "enrollment must have posted something"
    for source, group in by_source.items():
        debits = sum(e.debit for e in group)
        credits = sum(e.credit for e in group)
        assert debits == credits, f"entry for {source} does not balance"
    assert all(entry.debit >= 0 and entry.credit >= 0 for entry in entries)
