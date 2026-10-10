"""
RENTAL OS — Reports: Exports & Scheduled Dispatch

PDF owner statement, KRA eTIMS invoice export, and the monthly report
dispatcher. Mounted under `/reports` by `app.reports.router`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import SessionDep, get_current_user
from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.business import User
from app.models.expense import Expense
from app.models.lease import Lease, LeaseStatus
from app.models.property import Unit, UnitStatus
from app.models.tenant import Tenant
from app.reports.etims import etims_invoice_data, export_etims_json
from app.reports.monthly_scheduler import generate_and_dispatch_monthly_report
from app.reports.pdf_service import build_owner_statement

router = APIRouter()


@router.get("/export-statement-pdf")
async def export_statement_pdf(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Export owner P&L statement as a professional PDF."""
    today = date.today()
    fd = date.fromisoformat(from_date) if from_date else today.replace(day=1)
    td = date.fromisoformat(to_date) if to_date else today
    biz_id = user.business_id

    income = await session.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
            Invoice.business_id == biz_id,
            Invoice.invoice_type == InvoiceType.RENT.value,
            Invoice.period_start >= fd, Invoice.period_start <= td,
            Invoice.status == InvoiceStatus.PAID.value,
        )
    ) or Decimal("0")

    outstanding = await session.scalar(
        select(func.coalesce(func.sum(Invoice.balance), 0)).where(
            Invoice.business_id == biz_id, Invoice.invoice_type == InvoiceType.RENT.value,
            Invoice.status != InvoiceStatus.PAID.value, Invoice.balance > 0,
        )
    ) or Decimal("0")

    exp_total = await session.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.business_id == biz_id, Expense.paid_at >= fd, Expense.paid_at <= td,
        )
    ) or Decimal("0")

    expenses_by_cat = dict(
        (await session.execute(
            select(Expense.category, func.coalesce(func.sum(Expense.amount), 0))
            .where(Expense.business_id == biz_id, Expense.paid_at >= fd, Expense.paid_at <= td)
            .group_by(Expense.category)
        )).all()
    )

    total_units = await session.scalar(
        select(func.count()).select_from(Unit).where(Unit.business_id == biz_id, Unit.is_deleted.is_(False))
    ) or 0
    occupied = await session.scalar(
        select(func.count()).select_from(Unit).where(
            Unit.business_id == biz_id, Unit.is_deleted.is_(False), Unit.status == UnitStatus.OCCUPIED.value,
        )
    ) or 0
    active_leases = await session.scalar(
        select(func.count()).select_from(Lease).where(Lease.business_id == biz_id, Lease.status == LeaseStatus.ACTIVE.value)
    ) or 0
    payment_count = await session.scalar(
        select(func.count()).select_from(Payment).where(Payment.business_id == biz_id, Payment.paid_at >= fd, Payment.paid_at <= td)
    ) or 0

    inc = float(income)
    exp = float(exp_total)
    net = inc - exp

    pdf = build_owner_statement(
        business_name="Rental OS",
        period_from=fd, period_to=td,
        income=inc, outstanding=float(outstanding),
        expenses=exp, expenses_by_cat={str(k): float(v) for k, v in expenses_by_cat.items()},
        net_profit=net, margin=round((net / inc) * 100, 1) if inc > 0 else 0,
        total_units=total_units, occupied=occupied, vacancy=total_units - occupied,
        occupancy_rate=round((occupied / total_units) * 100, 1) if total_units > 0 else 0,
        active_leases=active_leases, payment_count=payment_count,
    )

    filename = f"owner_statement_{fd.isoformat()}_to_{td.isoformat()}.pdf"
    return StreamingResponse(
        iter([pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-etims")
async def export_etims(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Export KRA eTIMS compliant invoices as JSON."""
    today = date.today()
    fd = date.fromisoformat(from_date) if from_date else today.replace(day=1)
    td = date.fromisoformat(to_date) if to_date else today
    biz_id = user.business_id

    inv_q = (
        select(Invoice, Tenant.full_name, Tenant.id_number, Unit.unit_number)
        .join(Tenant, Invoice.tenant_id == Tenant.id)
        .join(Unit, Invoice.unit_id == Unit.id)
        .where(
            Invoice.business_id == biz_id,
            Invoice.created_at >= fd,
            Invoice.created_at <= td,
        )
        .order_by(Invoice.created_at.desc())
    )
    rows = (await session.execute(inv_q)).all()

    invoices = [
        etims_invoice_data(
            invoice_number=inv.invoice_number or str(inv.id)[:8],
            invoice_type=inv.invoice_type,
            amount=float(inv.amount),
            paid_amount=float(inv.paid_amount or 0),
            tenant_name=tname,
            tenant_pin=tpin,
            seller_pin="",
            invoice_date=str(inv.created_at.date()) if hasattr(inv.created_at, "date") else str(inv.created_at),
        )
        for inv, tname, tpin, unum in rows
    ]

    content = export_etims_json(invoices)
    filename = f"etims_export_{fd.isoformat()}_to_{td.isoformat()}.json"

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/dispatch-monthly")
async def dispatch_monthly_report(
    target_month: str | None = Query(None, description="YYYY-MM, defaults to last month"),
    send_whatsapp: bool = Query(True),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """
    Generate & dispatch the monthly owner financial report.
    Sends a WhatsApp summary + saves PDF statement.
    """
    month_date: date | None = None
    if target_month:
        month_date = date.fromisoformat(f"{target_month}-01")

    result = await generate_and_dispatch_monthly_report(
        session=session,
        business_id=str(user.business_id),
        target_month=month_date,
        send_whatsapp=send_whatsapp,
        send_email=False,
    )
    return result
