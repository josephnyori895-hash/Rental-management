"""
RENTAL OS — Monthly Rent Run

Module:
    Raises one rent invoice per active lease for a calendar month and posts
    each to the ledger.

Purpose:
    Enrollment raises a tenancy's first rent invoice and nothing raises
    another, so every tenancy's rent roll stops after its first month —
    arrears, aged receivables and the rent roll all see only month one.

    The run is idempotent by overlap, not by exact period match, because the
    enrollment invoice covers `start_date .. start_date + 30 days` and need not
    line up with a calendar month. Running it twice, or running it while an
    enrollment invoice already covers the month, therefore cannot double-bill.

Money is `Decimal` throughout; a lease is billed at its own `rent_amount`
rather than the unit's current asking rent, so a rent review is a lease
change, not a silent migration of historical amounts.
"""

from __future__ import annotations

import calendar
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_invoice
from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.lease import Lease, LeaseStatus

logger = logging.getLogger(__name__)


class RentRunError(ValueError):
    """A period the run will not bill, e.g. one that has not started yet."""


def month_period(year: int, month: int) -> tuple[date, date]:
    """First and last day of a calendar month."""
    if not 1 <= int(month) <= 12:
        raise RentRunError(f"month must be 1..12, got {month!r}")
    first = date(int(year), int(month), 1)
    return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])


def due_date_for(period_start: date, payment_day: int | None) -> date:
    """The lease's payment day inside the billed month.

    Clamped to the month's length so a lease paid on the 31st is due on the
    28th in February (and the 29th in a leap year) rather than spilling into
    the next month.
    """
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    day = min(max(int(payment_day or 1), 1), last_day)
    return period_start.replace(day=day)


def period_is_billed(
    existing: Iterable[tuple[date | None, date | None]],
    period_start: date,
    period_end: date,
) -> bool:
    """Whether any rent invoice overlaps the month being billed.

    Overlap rather than equality: an invoice raised at enrollment runs from
    the tenancy's start date, which is rarely the 1st of a month.
    """
    for start, end in existing:
        if start is None:
            continue
        stop = end or start
        if start <= period_end and stop >= period_start:
            return True
    return False


@dataclass
class RentRunResult:
    period_start: date
    period_end: date
    dry_run: bool = False
    created: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    @property
    def total_billed(self) -> Decimal:
        return sum(
            (Decimal(str(row["amount"])) for row in self.created), Decimal("0")
        )

    def as_dict(self) -> dict:
        return {
            "period_start": str(self.period_start),
            "period_end": str(self.period_end),
            "dry_run": self.dry_run,
            "created_count": len(self.created),
            "skipped_count": len(self.skipped),
            "total_billed": float(self.total_billed),
            "created": self.created,
            "skipped": self.skipped,
        }


async def run_rent_for_period(
    session: AsyncSession,
    business_id: UUID,
    period_start: date,
    period_end: date,
    *,
    dry_run: bool = False,
) -> RentRunResult:
    """Raise rent invoices for every active lease covering the period.

    A lease already invoiced for any part of the month is skipped, so the run
    can be repeated or retried after a partial failure without creating a
    second invoice for the same rent (which would double the tenant's arrears).
    """
    if period_end < period_start:
        raise RentRunError("period_end must not precede period_start")
    if period_start > date.today():
        raise RentRunError(
            "refusing to bill a period that has not started "
            f"({period_start}); rent is invoiced when it falls due"
        )

    result = RentRunResult(period_start=period_start, period_end=period_end, dry_run=dry_run)

    leases = (
        await session.execute(
            select(Lease)
            .where(
                Lease.business_id == business_id,
                Lease.status == LeaseStatus.ACTIVE.value,
                Lease.start_date <= period_end,
                (Lease.end_date.is_(None)) | (Lease.end_date >= period_start),
            )
            .order_by(Lease.start_date)
        )
    ).scalars().all()

    if not leases:
        return result

    existing_rows = (
        await session.execute(
            select(Invoice.lease_id, Invoice.period_start, Invoice.period_end).where(
                Invoice.business_id == business_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.status != InvoiceStatus.CANCELLED.value,
                Invoice.lease_id.in_([lease.id for lease in leases]),
            )
        )
    ).all()

    by_lease: dict[UUID, list[tuple[date | None, date | None]]] = {}
    for lease_id, start, end in existing_rows:
        by_lease.setdefault(lease_id, []).append((start, end))

    # Each invoice is paired with the report row describing it, because a
    # `UUIDMixin` id is assigned by the database default on flush — reading
    # `invoice.id` before then yields None, and a preview would report
    # "None" as the id of a row it just said it created.
    pending: list[tuple[Invoice, dict]] = []
    for lease in leases:
        if period_is_billed(by_lease.get(lease.id, []), period_start, period_end):
            result.skipped.append(
                {
                    "lease_id": str(lease.id),
                    "tenant_id": str(lease.tenant_id),
                    "unit_id": str(lease.unit_id),
                    "reason": "already_invoiced",
                    "amount": float(lease.rent_amount),
                }
            )
            continue

        # A tenancy that began mid-month starts being billed from its start
        # date; the enrollment invoice normally covers that anyway, so this
        # only matters for historic leases whose first invoice is missing.
        billed_from = max(period_start, lease.start_date)
        due_date = max(due_date_for(period_start, lease.payment_day), billed_from)
        invoice = Invoice(
            business_id=business_id,
            lease_id=lease.id,
            tenant_id=lease.tenant_id,
            unit_id=lease.unit_id,
            property_id=lease.property_id,
            invoice_type=InvoiceType.RENT.value,
            period_start=billed_from,
            period_end=period_end,
            due_date=due_date,
            amount=lease.rent_amount,
            paid_amount=Decimal("0"),
            balance=lease.rent_amount,
            status=InvoiceStatus.PENDING.value,
            description=f"Rent {billed_from:%Y-%m}",
        )

        row = {
            "invoice_id": None,
            "lease_id": str(lease.id),
            "tenant_id": str(lease.tenant_id),
            "unit_id": str(lease.unit_id),
            "amount": float(lease.rent_amount),
            "period_start": str(billed_from),
            "period_end": str(period_end),
            "due_date": str(due_date),
        }
        result.created.append(row)
        if dry_run:
            continue

        session.add(invoice)
        pending.append((invoice, row))

    if dry_run:
        return result

    await session.flush()
    for invoice, row in pending:
        row["invoice_id"] = str(invoice.id)

    # Best-effort, but never silent: an invoice without a journal entry makes
    # the rent roll and the balance sheet disagree, and a rent run is what
    # makes that gap recurring rather than one-off.
    for invoice, _row in pending:
        try:
            await auto_post_invoice(session, invoice)
        except Exception:
            logger.warning(
                "Ledger posting failed for rent invoice %s (lease %s)",
                invoice.id, invoice.lease_id, exc_info=True,
            )

    await session.commit()
    return result
