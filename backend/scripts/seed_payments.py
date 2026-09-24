"""
Backfill Payment records for existing paid invoices so the tenant detail
page shows real transaction history.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
import random

from sqlalchemy import text, select

from app.core.database import async_session_factory
from app.models.billing import Invoice, Payment

METHODS = ["mpesa", "mpesa", "mpesa", "bank", "cash", "airtel", "equity", "card"]
PREFIX = {
    "mpesa": "MP", "bank": "BNK", "cash": "CSH",
    "airtel": "ATL", "equity": "EQT", "card": "CRD",
}


async def main() -> None:
    async with async_session_factory() as s:
        row = await s.execute(text("SELECT id FROM businesses LIMIT 1"))
        biz_uuid = row.scalar_one_or_none()
        if not biz_uuid:
            print("No business found. Run seed.py first.")
            return

        invoices = (
            await s.scalars(
                select(Invoice).where(
                    Invoice.business_id == biz_uuid,
                    Invoice.paid_amount > 0,
                ).limit(200)
            )
        ).all()

        created = 0
        for inv in invoices:
            # Check if a payment already exists for this invoice
            existing = await s.scalar(
                select(Payment).where(Payment.invoice_id == inv.id).limit(1)
            )
            if existing:
                continue

            method = random.choice(METHODS)
            pay = Payment(
                business_id=inv.business_id,
                tenant_id=inv.tenant_id,
                invoice_id=inv.id,
                lease_id=inv.lease_id,
                amount=inv.paid_amount,
                method=method,
                reference=f"{PREFIX[method]}{inv.created_at.strftime('%y%m%d%H%M%S') if inv.created_at else '000000'}",
                status="completed",
                paid_at=(inv.created_at or datetime.combine(date.today(), datetime.min.time())),
            )
            s.add(pay)
            created += 1

        await s.commit()
        print(f"Created {created} Payment records from {len(invoices)} paid invoices.")


if __name__ == "__main__":
    asyncio.run(main())
