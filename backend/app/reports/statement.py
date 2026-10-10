"""
RENTAL OS — Reports: Owner Statement & Collection Trend

Mounted under `/reports` by `app.reports.router`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep, get_current_user
from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.business import User
from app.models.expense import Expense
from app.models.lease import Lease, LeaseStatus
from app.models.maintenance import MaintenanceTicket
from app.models.property import Unit, UnitStatus

router = APIRouter()


@router.get("/owner-statement")
async def owner_statement(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Full owner P&L statement: income, expenses, occupancy, collections."""
    today = date.today()
    fd = date.fromisoformat(from_date) if from_date else today.replace(day=1)
    td = date.fromisoformat(to_date) if to_date else today
    biz_id = user.business_id

    # Rental income for period
    income = await session.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
            Invoice.business_id == biz_id,
            Invoice.invoice_type == InvoiceType.RENT.value,
            Invoice.period_start >= fd,
            Invoice.period_start <= td,
            Invoice.status == InvoiceStatus.PAID.value,
        )
    ) or Decimal("0")

    # Outstanding
    outstanding = await session.scalar(
        select(func.coalesce(func.sum(Invoice.balance), 0)).where(
            Invoice.business_id == biz_id,
            Invoice.invoice_type == InvoiceType.RENT.value,
            Invoice.status != InvoiceStatus.PAID.value,
            Invoice.balance > 0,
        )
    ) or Decimal("0")

    # Expenses
    exp_total = await session.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.business_id == biz_id,
            Expense.paid_at >= fd,
            Expense.paid_at <= td,
        )
    ) or Decimal("0")

    expenses_by_cat = (
        await session.execute(
            select(Expense.category, func.coalesce(func.sum(Expense.amount), 0))
            .where(Expense.business_id == biz_id, Expense.paid_at >= fd, Expense.paid_at <= td)
            .group_by(Expense.category)
            .order_by(func.sum(Expense.amount).desc())
        )
    ).all()

    # Occupancy
    total_units = await session.scalar(
        select(func.count()).select_from(Unit).where(
            Unit.business_id == biz_id, Unit.is_deleted.is_(False),
        )
    ) or 0
    occupied = await session.scalar(
        select(func.count()).select_from(Unit).where(
            Unit.business_id == biz_id,
            Unit.is_deleted.is_(False),
            Unit.status == UnitStatus.OCCUPIED.value,
        )
    ) or 0

    # Active leases count
    active_leases = await session.scalar(
        select(func.count()).select_from(Lease).where(
            Lease.business_id == biz_id,
            Lease.status == LeaseStatus.ACTIVE.value,
        )
    ) or 0

    # Open maintenance
    open_maint = await session.scalar(
        select(func.count()).select_from(MaintenanceTicket).where(
            MaintenanceTicket.business_id == biz_id,
            MaintenanceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    ) or 0

    # Payment count for period
    payment_count = await session.scalar(
        select(func.count()).select_from(Payment).where(
            Payment.business_id == biz_id,
            Payment.paid_at >= fd,
            Payment.paid_at <= td,
        )
    ) or 0

    return {
        "period": {"from": str(fd), "to": str(td)},
        "income": {
            "rental_income": float(income),
            "outstanding": float(outstanding),
            "total_expected": float(income) + float(outstanding),
        },
        "expenses": {
            "total": float(exp_total),
            "by_category": {row[0]: float(row[1]) for row in expenses_by_cat},
        },
        "profit_loss": {
            "gross_profit": float(income) - float(exp_total),
            "margin_percent": round(((float(income) - float(exp_total)) / float(income)) * 100, 1) if float(income) > 0 else 0,
        },
        "operations": {
            "total_units": total_units,
            "occupied": occupied,
            "vacant": total_units - occupied,
            "occupancy_rate": round((occupied / total_units) * 100, 1) if total_units > 0 else 0,
            "active_leases": active_leases,
            "payment_count": payment_count,
            "open_maintenance_tickets": open_maint,
        },
    }


@router.get("/collection-trend")
async def collection_trend(
    months: int = Query(6, ge=1, le=24),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Monthly collection trend with on-time vs late breakdown."""
    today = date.today()
    points = []
    biz_id = user.business_id

    for back in range(months - 1, -1, -1):
        y, mo = today.year, today.month - back
        while mo <= 0:
            mo += 12
            y -= 1
        ms = date(y, mo, 1)
        if mo == 12:
            nm = date(y + 1, 1, 1)
        else:
            nm = date(y, mo + 1, 1)

        collected = await session.scalar(
            select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                Invoice.business_id == biz_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.period_start >= ms,
                Invoice.period_start < nm,
            )
        ) or Decimal("0")

        expected = await session.scalar(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(
                Invoice.business_id == biz_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.period_start >= ms,
                Invoice.period_start < nm,
            )
        ) or Decimal("0")

        paid_count = await session.scalar(
            select(func.count()).where(
                Invoice.business_id == biz_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.period_start >= ms,
                Invoice.period_start < nm,
                Invoice.status == InvoiceStatus.PAID.value,
            )
        ) or 0

        total_inv = await session.scalar(
            select(func.count()).where(
                Invoice.business_id == biz_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.period_start >= ms,
                Invoice.period_start < nm,
            )
        ) or 0

        points.append({
            "month": ms.strftime("%Y-%m"),
            "label": ms.strftime("%b %Y"),
            "expected": float(expected),
            "collected": float(collected),
            "collection_rate": round(float(collected) / float(expected) * 100, 1) if float(expected) > 0 else 0,
            "paid_count": paid_count,
            "total_invoices": total_inv,
        })

    return points
