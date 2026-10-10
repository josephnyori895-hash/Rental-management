"""
RENTAL OS — Reports: Books of Accounts

The aggregated books bundle (JSON) and its multi-sheet CSV export.
Mounted under `/reports` by `app.reports.router`.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.accounting import service as acct_service
from app.api.deps import SessionDep, get_current_user
from app.models.billing import Invoice, Payment
from app.models.business import User
from app.models.expense import Expense
from app.models.property import Unit
from app.models.tenant import Tenant

router = APIRouter()


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
