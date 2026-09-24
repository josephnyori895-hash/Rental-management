"""
Backfill journal entries for existing invoices, payments, and expenses.
Run after wiring auto-post hooks to catch up historical data.
"""
from __future__ import annotations

import asyncio
from uuid import UUID
from sqlalchemy import select, text

from app.core.database import async_session_factory
from app.accounting.service import auto_post_invoice, auto_post_payment, auto_post_expense
from app.models.billing import Invoice, InvoiceType, Payment
from app.models.expense import Expense

counts_by_type = {"invoices": 0, "payments": 0, "expenses": 0}


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
    async with async_session_factory() as s:
        row = await s.execute(text("SELECT id FROM businesses LIMIT 1"))
        biz = row.scalar_one_or_none()
        if not biz:
            print("No business found")
            return

        # Clear existing journal entries
        await s.execute(text("DELETE FROM journal_entries"))
        await s.commit()
        print("Cleared existing journal entries")

    # Each backfill uses its own transaction lifecycle
    async with async_session_factory() as s:
        print(f"\nBackfilling invoices...")
        await backfill_invoices(s, biz)
    async with async_session_factory() as s:
        print(f"\nBackfilling payments...")
        await backfill_payments(s, biz)
    async with async_session_factory() as s:
        print(f"\nBackfilling expenses...")
        await backfill_expenses(s, biz)

    # Final count
    async with async_session_factory() as s:
        r = await s.execute(text("SELECT COUNT(*) FROM journal_entries"))
        count = r.scalar()
        total = sum(counts_by_type.values())
        print(f"\n{'='*40}")
        print(f"Invoices:  {counts_by_type['invoices']}")
        print(f"Payments:  {counts_by_type['payments']}")
        print(f"Expenses:  {counts_by_type['expenses']}")
        print(f"Total JE:  {count}")
        print(f"{'='*40}")


if __name__ == "__main__":
    asyncio.run(main())
