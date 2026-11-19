"""
Backfill journal entries for one business's existing invoices, payments and
expenses. Run after wiring auto-post hooks, or after an intentional ledger reset.

The reset is scoped to the business being backfilled. An earlier version ran
`DELETE FROM journal_entries` with no filter, which silently wiped every
operator's books on a shared database.

Run:
    PYTHONPATH=. ./venv/bin/python scripts/backfill_accounting.py --business nyorii-hostels
    PYTHONPATH=. ./venv/bin/python scripts/backfill_accounting.py --business <uuid> --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_expense, auto_post_invoice, auto_post_payment
from app.core.database import async_session_factory
from app.models.accounting import JournalEntry
from app.models.billing import Invoice, InvoiceType, Payment
from app.models.business import Business
from app.models.expense import Expense

counts_by_type = {"invoices": 0, "payments": 0, "expenses": 0}


async def resolve_business(session: AsyncSession, identifier: str | None) -> Business:
    """Business by slug or id, or the only one there is when no id is given."""
    if identifier:
        business = None
        try:
            business = await session.get(Business, UUID(identifier))
        except ValueError:
            business = await session.scalar(
                select(Business).where(Business.slug == identifier)
            )
        if business is None:
            raise SystemExit(f"No business matches {identifier!r}")
        return business

    businesses = (await session.scalars(select(Business).order_by(Business.slug))).all()
    if len(businesses) != 1:
        names = ", ".join(b.slug for b in businesses) or "none"
        raise SystemExit(
            "Pass --business <slug|id>: this database holds "
            f"{len(businesses)} businesses ({names})."
        )
    return businesses[0]


async def ledger_entries(session: AsyncSession, business_id: UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.business_id == business_id)
        )
    ).scalar_one()


async def clear_ledger(session: AsyncSession, business_id: UUID) -> int:
    """Delete this business's journal lines only. Returns the rows removed."""
    result = await session.execute(
        delete(JournalEntry).where(JournalEntry.business_id == business_id)
    )
    await session.commit()
    return result.rowcount or 0


async def backfill_invoices(s, biz):
    invoices = (await s.scalars(
        select(Invoice).where(
            Invoice.business_id == biz,
            Invoice.invoice_type != InvoiceType.DEPOSIT.value,
        ).order_by(Invoice.created_at)
    )).all()
    posted = 0
    for inv in invoices:
        try:
            await auto_post_invoice(s, inv)
            await s.commit()
            posted += 1
        except Exception as e:
            await s.rollback()
            print(f"  SKIP invoice {inv.id}: {e}")
    counts_by_type["invoices"] = posted
    print(f"  Posted {posted}/{len(invoices)} invoices")
    return posted


async def backfill_payments(s, biz):
    payments = (await s.scalars(
        select(Payment).where(Payment.business_id == biz).order_by(Payment.paid_at)
    )).all()
    posted = 0
    for pay in payments:
        try:
            await auto_post_payment(s, pay)
            await s.commit()
            posted += 1
        except Exception as e:
            await s.rollback()
            print(f"  SKIP payment {pay.id}: {e}")
    counts_by_type["payments"] = posted
    print(f"  Posted {posted}/{len(payments)} payments")
    return posted


async def backfill_expenses(s, biz):
    expenses = (await s.scalars(
        select(Expense).where(Expense.business_id == biz).order_by(Expense.paid_at)
    )).all()
    posted = 0
    for exp in expenses:
        try:
            await auto_post_expense(s, exp)
            await s.commit()
            posted += 1
        except Exception as e:
            await s.rollback()
            print(f"  SKIP expense {exp.id}: {e}")
    counts_by_type["expenses"] = posted
    print(f"  Posted {posted}/{len(expenses)} expenses")
    return posted


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--business",
        help="Business slug or id. Required unless the database holds exactly one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be cleared; change nothing.",
    )
    args = parser.parse_args()

    async with async_session_factory() as s:
        biz = await resolve_business(s, args.business)
        print(f"Business: {biz.name} ({biz.slug}, {biz.id})")
        existing = await ledger_entries(s, biz.id)
        print(f"Journal lines for this business: {existing}")
        if args.dry_run:
            print("Dry run: nothing cleared, nothing posted.")
            return
        removed = await clear_ledger(s, biz.id)
        print(f"Cleared {removed} journal lines for {biz.slug}")

    biz_id = biz.id
    async with async_session_factory() as s:
        print("\nBackfilling invoices...")
        await backfill_invoices(s, biz_id)
    async with async_session_factory() as s:
        print("\nBackfilling payments...")
        await backfill_payments(s, biz_id)
    async with async_session_factory() as s:
        print("\nBackfilling expenses...")
        await backfill_expenses(s, biz_id)

    async with async_session_factory() as s:
        count = await ledger_entries(s, biz_id)
        print(f"\n{'=' * 40}")
        print(f"Invoices:  {counts_by_type['invoices']}")
        print(f"Payments:  {counts_by_type['payments']}")
        print(f"Expenses:  {counts_by_type['expenses']}")
        print(f"Total JE:  {count}")
        print(f"{'=' * 40}")


if __name__ == "__main__":
    asyncio.run(main())
