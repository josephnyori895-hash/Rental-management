"""
RENTAL OS — Monthly rent run (CLI)

Raises one rent invoice per active lease for a calendar month and posts each
to the ledger. Idempotent: a lease already invoiced for any part of the month
is skipped, so running it twice — or running it next to the scheduler — cannot
double-bill a tenant.

This is the command a cron/scheduled job should run on the 1st of each month:

    0 6 1 * *  cd /srv/rental/backend && PYTHONPATH=. ./venv/bin/python scripts/run_rent.py

Run by hand:
    PYTHONPATH=. ./venv/bin/python scripts/run_rent.py [--period 2026-11] \
        [--business-id UUID] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import date

from sqlalchemy import select

from app.billing.rent_run import RentRunError, month_period, run_rent_for_period
from app.core.database import async_session_factory
from app.models.business import Business


def _parse_period(value: str | None) -> tuple[int, int]:
    if not value:
        today = date.today()
        return today.year, today.month
    try:
        year_text, month_text = value.split("-", 1)
        return int(year_text), int(month_text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected YYYY-MM, got {value!r}"
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description="Raise monthly rent invoices")
    parser.add_argument("--period", help="YYYY-MM (default: current month)")
    parser.add_argument("--business-id", help="bill one business only")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    try:
        period_start, period_end = month_period(*_parse_period(args.period))
    except RentRunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    async with async_session_factory() as session:
        if args.business_id:
            business = await session.get(Business, uuid.UUID(args.business_id))
            if not business:
                print(f"error: no business {args.business_id}", file=sys.stderr)
                return 2
            businesses = [business]
        else:
            businesses = (
                await session.execute(select(Business).order_by(Business.name))
            ).scalars().all()

        failed = 0
        for business in businesses:
            try:
                result = await run_rent_for_period(
                    session, business.id, period_start, period_end,
                    dry_run=args.dry_run,
                )
            except RentRunError as exc:
                print(f"{business.name}: error: {exc}", file=sys.stderr)
                failed += 1
                continue

            print(
                f"{business.name}: {result.period_start:%Y-%m} "
                f"created={len(result.created)} skipped={len(result.skipped)} "
                f"total={result.total_billed}"
                + (" (dry run)" if result.dry_run else "")
            )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
