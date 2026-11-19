"""
`scripts/backfill_accounting.py` resets a business's ledger before re-posting.

The reset used to be `DELETE FROM journal_entries` with no filter, which wiped
every operator's books on a shared database. These tests pin the scoping: one
business, chosen explicitly, and nothing else touched.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.backfill_accounting import clear_ledger, ledger_entries, resolve_business
from tests.conftest import requires_db


@requires_db
async def test_a_business_is_chosen_by_slug_or_id(businesses, db_session):
    first, second = businesses

    by_slug = await resolve_business(db_session, first.business.slug)
    assert by_slug.id == first.business.id

    by_id = await resolve_business(db_session, str(second.business.id))
    assert by_id.id == second.business.id


@requires_db
async def test_an_unknown_or_ambiguous_business_refuses_to_guess(businesses, db_session):
    with pytest.raises(SystemExit):
        await resolve_business(db_session, "no-such-business")

    # Two businesses exist, so the default ("the only one") cannot be used.
    with pytest.raises(SystemExit):
        await resolve_business(db_session, None)


@requires_db
async def test_clearing_the_ledger_only_touches_the_chosen_business(businesses, db_session):
    from app.models.accounting import JournalEntry

    first, second = businesses
    for seeded in (first, second):
        db_session.add(
            JournalEntry(
                business_id=seeded.business.id,
                account_id=seeded.accounts[0].id,
                debit=Decimal("100"),
                credit=Decimal("0"),
                description=f"{seeded.label} opening line",
            )
        )
    await db_session.flush()
    assert await ledger_entries(db_session, first.business.id) == 1
    assert await ledger_entries(db_session, second.business.id) == 1

    removed = await clear_ledger(db_session, first.business.id)

    assert removed == 1
    assert await ledger_entries(db_session, first.business.id) == 0
    assert await ledger_entries(db_session, second.business.id) == 1
