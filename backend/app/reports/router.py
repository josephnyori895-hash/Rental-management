"""
RENTAL OS — Reports Router

Comprehensive analytics & PDF-ready owner statements.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.accounting import service as acct_service
from app.api.deps import SessionDep, get_current_user
from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.business import User
from app.models.expense import Expense
from app.models.lease import Lease, LeaseStatus
from app.models.maintenance import MaintenanceTicket
from app.models.property import Property, Unit, UnitStatus
from app.models.tenant import Tenant
from app.reports.pdf_service import build_owner_statement, build_payment_receipt
from app.reports.etims import etims_invoice_data, export_etims_json
from app.reports.monthly_scheduler import generate_and_dispatch_monthly_report

router = APIRouter(prefix="/reports", tags=["reports"])


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


async def _books_data(session, user, from_date: date | None, to_date: date | None, property_id: str | None):
    """Collect full books of accounts bundle for export."""
    biz_id = user.business_id
    from uuid import UUID
    prop_uuid = UUID(property_id) if property_id else None
    fd = from_date or date.today().replace(day=1)
    td = to_date or date.today()

    trial = await acct_service.trial_balance(session, biz_id, as_at=td, property_id=prop_uuid)
    pl = await acct_service.profit_and_loss(session, biz_id, from_date=fd, to_date=td, property_id=prop_uuid)
    bs = await acct_service.balance_sheet(session, biz_id, as_at=td, property_id=prop_uuid)

    inv_q = (
        select(Invoice, Unit.unit_number, Tenant.full_name)
        .join(Unit, Invoice.unit_id == Unit.id)
        .join(Tenant, Invoice.tenant_id == Tenant.id)
        .where(Invoice.business_id == biz_id)
        .order_by(Invoice.created_at.desc())
    )
    if prop_uuid:
        inv_q = inv_q.where(Invoice.property_id == prop_uuid)
    invoices = (await session.execute(inv_q)).all()

    pay_q = (
        select(Payment, Tenant.full_name, Unit.unit_number, Invoice.invoice_type)
        .join(Tenant, Payment.tenant_id == Tenant.id, isouter=True)
        .join(Invoice, Payment.invoice_id == Invoice.id, isouter=True)
        .join(Unit, Invoice.unit_id == Unit.id, isouter=True)
        .where(Payment.business_id == biz_id)
        .order_by(Payment.paid_at.desc())
    )
    if prop_uuid:
        pay_q = pay_q.where(Invoice.property_id == prop_uuid)
    payments = (await session.execute(pay_q)).all()

    exp_q = select(Expense).where(Expense.business_id == biz_id).order_by(Expense.paid_at.desc())
    if prop_uuid:
        exp_q = exp_q.where(Expense.property_id == prop_uuid)
    expenses = (await session.scalars(exp_q)).all()

    return {
        "business": {"name": "Rental OS Owner", "period": {"from": str(fd), "to": str(td)}},
        "trial_balance": trial,
        "profit_loss": pl,
        "balance_sheet": bs,
        "invoices": [
            {
                "invoice_number": inv.invoice_number or str(inv.id),
                "date": str(inv.created_at.date()) if hasattr(inv.created_at, "date") else str(inv.created_at or ""),
                "tenant": tname,
                "unit": unum,
                "type": inv.invoice_type,
                "amount": float(inv.amount),
                "paid": float(inv.paid_amount or 0),
                "balance": float(inv.balance or 0),
                "status": inv.status,
                "due_date": str(inv.due_date) if inv.due_date else "",
            }
            for inv, unum, tname in invoices
        ],
        "payments": [
            {
                "date": str(p.paid_at.date()) if hasattr(p.paid_at, "date") else str(p.paid_at or ""),
                "tenant": tname,
                "unit": unum,
                "amount": float(p.amount),
                "method": p.method,
                "reference": p.reference or "",
                "status": p.status,
            }
            for p, tname, unum, _itype in payments
        ],
        "expenses": [
            {
                "date": str(e.paid_at) if e.paid_at else "",
                "category": e.category,
                "description": e.description or "",
                "amount": float(e.amount),
                "vendor": e.vendor or "",
            }
            for e in expenses
        ],
    }


@router.get("/books-bundle")
async def books_bundle(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    property_id: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    return await _books_data(session, user, fd, td, property_id)


@router.get("/export-books")
async def export_books(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    property_id: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Export full books of accounts as a multi-sheet CSV file."""
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    data = await _books_data(session, user, fd, td, property_id)

    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["RENTAL OS — BOOKS OF ACCOUNTS"])
    w.writerow([f"Period: {data['business']['period']['from']} to {data['business']['period']['to']}"])
    w.writerow([])

    w.writerow(["=== PROFIT & LOSS ==="])
    w.writerow([])
    w.writerow(["INCOME"])
    w.writerow(["Code", "Account", "Amount"])
    for a in data["profit_loss"]["income"]:
        w.writerow([a["code"], a["name"], f"{a['balance']:,.2f}"])
    w.writerow(["", "Total Income", f"{data['profit_loss']['total_income']:,.2f}"])
    w.writerow([])
    w.writerow(["EXPENSES"])
    w.writerow(["Code", "Account", "Amount"])
    for a in data["profit_loss"]["expenses"]:
        w.writerow([a["code"], a["name"], f"{a['balance']:,.2f}"])
    w.writerow(["", "Total Expenses", f"{data['profit_loss']['total_expenses']:,.2f}"])
    w.writerow([])
    w.writerow(["", "NET PROFIT", f"{data['profit_loss']['net_profit']:,.2f}"])
    w.writerow([])

    w.writerow(["=== BALANCE SHEET ==="])
    w.writerow([])
    w.writerow(["ASSETS"])
    w.writerow(["Code", "Account", "Amount"])
    for a in data["balance_sheet"]["assets"]:
        w.writerow([a["code"], a["name"], f"{a['balance']:,.2f}"])
    w.writerow(["", "Total Assets", f"{data['balance_sheet']['total_assets']:,.2f}"])
    w.writerow([])
    w.writerow(["LIABILITIES"])
    w.writerow(["Code", "Account", "Amount"])
    for a in data["balance_sheet"]["liabilities"]:
        w.writerow([a["code"], a["name"], f"{a['balance']:,.2f}"])
    w.writerow(["", "Total Liabilities", f"{data['balance_sheet']['total_liabilities']:,.2f}"])
    w.writerow([])
    w.writerow(["EQUITY"])
    w.writerow(["Code", "Account", "Amount"])
    for a in data["balance_sheet"]["equity"]:
        w.writerow([a["code"], a["name"], f"{a['balance']:,.2f}"])
    w.writerow(["", "Total Equity", f"{data['balance_sheet']['total_equity']:,.2f}"])
    w.writerow(["", "Net Assets", f"{data['balance_sheet']['net_assets']:,.2f}"])
    w.writerow([])

    w.writerow(["=== TRIAL BALANCE ==="])
    w.writerow([])
    w.writerow(["Code", "Account", "Type", "Debit", "Credit", "Balance"])
    for a in data["trial_balance"]:
        w.writerow([a["code"], a["name"], a["type"], f"{a['debit']:,.2f}", f"{a['credit']:,.2f}", f"{a['balance']:,.2f}"])
    td_total = sum(a["debit"] for a in data["trial_balance"])
    tc_total = sum(a["credit"] for a in data["trial_balance"])
    w.writerow(["", "TOTALS", "", f"{td_total:,.2f}", f"{tc_total:,.2f}", ""])
    w.writerow([])

    w.writerow(["=== INVOICES ==="])
    w.writerow([])
    w.writerow(["Invoice #", "Date", "Tenant", "Unit", "Type", "Amount", "Paid", "Balance", "Status", "Due Date"])
    for inv in data["invoices"]:
        w.writerow([inv["invoice_number"], inv["date"], inv["tenant"], inv["unit"], inv["type"],
                     f"{inv['amount']:,.2f}", f"{inv['paid']:,.2f}", f"{inv['balance']:,.2f}", inv["status"], inv["due_date"]])
    w.writerow([])

    w.writerow(["=== PAYMENTS ==="])
    w.writerow([])
    w.writerow(["Date", "Tenant", "Unit", "Amount", "Method", "Reference", "Status"])
    for p in data["payments"]:
        w.writerow([p["date"], p["tenant"], p["unit"], f"{p['amount']:,.2f}", p["method"], p["reference"], p["status"]])
    w.writerow([])

    w.writerow(["=== EXPENSES ==="])
    w.writerow([])
    w.writerow(["Date", "Category", "Description", "Amount", "Vendor"])
    for e in data["expenses"]:
        w.writerow([e["date"], e["category"], e["description"], f"{e['amount']:,.2f}", e["vendor"]])

    content = buf.getvalue()
    filename = f"books_of_accounts_{fd or 'all'}_to_{td or 'now'}.csv"

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
