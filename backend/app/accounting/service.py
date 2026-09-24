"""
RENTAL OS — Accounting Service
Chart of Accounts provisioning, journal posting, trial balance, P&L, balance sheet.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.accounting.models import AccountType, ChartOfAccount, JournalEntry

# ── Default Kenyan COA ──────────────────────────────────────────────────
# Each tuple: (code, name, type, category, is_system, sort_order, description)
DEFAULT_COA: list[tuple[str, str, str, str | None, bool, int, str]] = [
    # ── Assets (1000–1999) ──
    ("1000", "Cash & M-Pesa Float",              AccountType.ASSET.value,  "current_asset",     True, 10, "Cash on hand and M-Pesa float"),
    ("1010", "Bank Account (Operating)",          AccountType.ASSET.value,  "current_asset",     True, 11, "Operating bank account"),
    ("1020", "Bank Account (Security Deposits)",  AccountType.ASSET.value,  "current_asset",     True, 12, "Tenant security deposits held in bank"),
    ("1100", "Tenant Receivables (Rent Arrears)", AccountType.ASSET.value,  "current_asset",     True, 20, "Outstanding rent from tenants"),
    ("1110", "Other Receivables",                 AccountType.ASSET.value,  "current_asset",     True, 21, "Other amounts owed to the business"),
    ("1200", "Fixed Assets (Buildings)",          AccountType.ASSET.value,  "fixed_asset",       True, 30, "Property buildings"),
    ("1210", "Fixed Assets (Furniture & Fittings)",AccountType.ASSET.value, "fixed_asset",       True, 31, "Furniture, fittings, equipment"),
    ("1250", "Accumulated Depreciation",          AccountType.CONTRA_ASSET.value, "fixed_asset", True, 35, "Total depreciation taken"),
    # ── Liabilities (2000–2999) ──
    ("2100", "Security Deposits Payable",         AccountType.LIABILITY.value, "current_liability", True, 40, "Deposits held on behalf of tenants"),
    ("2110", "Prepaid Rent",                      AccountType.LIABILITY.value, "current_liability", True, 41, "Rent paid in advance by tenants"),
    ("2200", "Owner Payable",                     AccountType.LIABILITY.value, "current_liability", True, 50, "Amounts owed to property owner"),
    ("2210", "Vendor Payables",                   AccountType.LIABILITY.value, "current_liability", True, 51, "Outstanding vendor bills"),
    # ── Equity (3000–3999) ──
    ("3000", "Owner's Capital",                   AccountType.EQUITY.value,  "reserve",           True, 60, "Owner's initial capital contribution"),
    ("3100", "Retained Earnings",                 AccountType.EQUITY.value,  "reserve",           True, 61, "Accumulated retained earnings"),
    # ── Income (4000–4499) ──
    ("4000", "Rental Income",                     AccountType.INCOME.value,  "operating_income",  True, 70, "Monthly rent from tenants"),
    ("4010", "Service Charge Income",             AccountType.INCOME.value,  "operating_income",  True, 71, "Service fees charged to tenants"),
    ("4020", "Late Fee Income",                   AccountType.INCOME.value,  "operating_income",  True, 72, "Penalties for late rent payment"),
    ("4030", "Water Bill Income",                 AccountType.INCOME.value,  "operating_income",  True, 73, "Water bill recharges to tenants"),
    ("4040", "Electricity Income",                AccountType.INCOME.value,  "operating_income",  True, 74, "Electricity recharges to tenants"),
    ("4050", "Other Income",                      AccountType.INCOME.value,  "other_income",      True, 79, "Miscellaneous income"),
    # ── Expenses (5000–5999) ──
    ("5000", "Repairs & Maintenance",             AccountType.EXPENSE.value, "operating_expense", True, 80, "Building and unit repairs"),
    ("5010", "Utilities (Water)",                 AccountType.EXPENSE.value, "operating_expense", True, 81, "Water bills paid"),
    ("5020", "Utilities (Electricity)",           AccountType.EXPENSE.value, "operating_expense", True, 82, "Electricity bills paid"),
    ("5030", "Caretaker Wages",                   AccountType.EXPENSE.value, "operating_expense", True, 83, "Caretaker and staff salaries"),
    ("5040", "Security Services",                 AccountType.EXPENSE.value, "operating_expense", True, 84, "Security guard services"),
    ("5050", "Cleaning & Garbage Collection",     AccountType.EXPENSE.value, "operating_expense", True, 85, "Common area cleaning and waste"),
    ("5060", "Insurance",                         AccountType.EXPENSE.value, "operating_expense", True, 86, "Property insurance premiums"),
    ("5070", "County Rates & Land Rent",          AccountType.EXPENSE.value, "operating_expense", True, 87, "County government rates and land rent"),
    ("5080", "Internet & WiFi",                   AccountType.EXPENSE.value, "operating_expense", True, 88, "Internet and WiFi subscriptions"),
    ("5090", "Supplies & Sundry",                 AccountType.EXPENSE.value, "operating_expense", True, 89, "Cleaning supplies, bulbs, small items"),
    ("5100", "Marketing & Advertising",           AccountType.EXPENSE.value, "operating_expense", True, 90, "Listing fees, adverts, signage"),
    ("5110", "Legal & Professional Fees",         AccountType.EXPENSE.value, "admin_expense",     True, 91, "Lawyer, accountant, consultant fees"),
    # ── Management Company Overhead (6000+) ──
    ("6000", "Management Fees",                   AccountType.EXPENSE.value, "admin_expense",     True, 100, "Property management commission/ fees"),
    ("6010", "Software & Subscriptions",          AccountType.EXPENSE.value, "admin_expense",     True, 101, "Software, SaaS, and subscription costs"),
    # ── Capital Expenditure (7000+) ──
    ("7000", "Capital Improvements",              AccountType.EXPENSE.value, "capital_expenditure", True, 110, "Major improvements (roof, plumbing, renovation)"),
    ("7010", "Asset Purchases",                   AccountType.EXPENSE.value, "capital_expenditure", True, 111, "Purchase of fixed assets"),
]


async def ensure_system_accounts(session: AsyncSession, business_id: UUID) -> None:
    """Provision the default Kenyan chart of accounts for a newly registered business."""
    existing = await session.scalar(
        select(func.count()).select_from(ChartOfAccount).where(
            ChartOfAccount.business_id == business_id,
        )
    )
    if existing and existing > 0:
        return  # Already provisioned

    for code, name, atype, cat, sys, sort, desc in DEFAULT_COA:
        session.add(ChartOfAccount(
            business_id=business_id,
            code=code,
            name=name,
            account_type=atype,
            category=cat,
            is_system=sys,
            is_active=True,
            description=desc,
            sort_order=sort,
        ))
    await session.commit()


async def get_account_id_by_code(session: AsyncSession, business_id: UUID, code: str) -> UUID | None:
    """Quick lookup: get account UUID from its code."""
    acct = await session.scalar(
        select(ChartOfAccount).where(
            ChartOfAccount.business_id == business_id,
            ChartOfAccount.code == code,
        )
    )
    return acct.id if acct else None


async def post_journal_entry(
    session: AsyncSession,
    business_id: UUID,
    entries: list[dict[str, Any]],
    entry_date: date | None = None,
    description: str | None = None,
    reference: str | None = None,
    source_type: str | None = None,
    source_id: UUID | None = None,
) -> None:
    """
    Post a double-entry journal entry.
    `entries` format: [{"account_id": UUID, "debit": Decimal, "credit": Decimal, "property_id": UUID | None}, ...]
    Debits and credits must balance.
    """
    total_debit = sum(e.get("debit", 0) or 0 for e in entries)
    total_credit = sum(e.get("credit", 0) or 0 for e in entries)
    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise ValueError(f"Journal entry does not balance: debit={total_debit}, credit={total_credit}")

    _date = entry_date or date.today()
    for e in entries:
        session.add(JournalEntry(
            business_id=business_id,
            property_id=e.get("property_id"),
            account_id=e["account_id"],
            entry_date=_date,
            debit=Decimal(str(e.get("debit", 0) or 0)),
            credit=Decimal(str(e.get("credit", 0) or 0)),
            description=description,
            reference=reference,
            source_type=source_type,
            source_id=source_id,
        ))
    await session.commit()


async def trial_balance(
    session: AsyncSession, business_id: UUID,
    as_at: date | None = None, property_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """
    Compute trial balance — all accounts with total debits, credits, and closing balance.
    Sources: journal_entries + current invoice/payment/expense data.
    """
    _date = as_at or date.today()

    accounts = (
        await session.scalars(
            select(ChartOfAccount).where(
                ChartOfAccount.business_id == business_id,
                ChartOfAccount.is_active.is_(True),
            ).order_by(ChartOfAccount.sort_order)
        )
    ).all()

    # Sum journal entries per account
    q = (
        select(
            JournalEntry.account_id,
            func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
        )
        .where(
            JournalEntry.business_id == business_id,
            JournalEntry.entry_date <= _date,
        )
    )
    if property_id:
        q = q.where(JournalEntry.property_id == property_id)
    q = q.group_by(JournalEntry.account_id)
    rows = (await session.execute(q)).all()
    ledgers = {r.account_id: {"debit": float(r.total_debit), "credit": float(r.total_credit)} for r in rows}

    result = []
    for acct in accounts:
        dr = Decimal(str(ledgers.get(acct.id, {}).get("debit", 0)))
        cr = Decimal(str(ledgers.get(acct.id, {}).get("credit", 0)))
        # Normal balance: assets/expenses = debit normal; liability/income/equity = credit normal
        if acct.account_type in (AccountType.ASSET.value, AccountType.EXPENSE.value, AccountType.CONTRA_ASSET.value):
            balance = dr - cr
        else:
            balance = cr - dr

        result.append({
            "account_id": str(acct.id),
            "code": acct.code,
            "name": acct.name,
            "type": acct.account_type,
            "category": acct.category,
            "debit": float(dr),
            "credit": float(cr),
            "balance": float(balance),
            "is_system": acct.is_system,
        })

    return result


async def profit_and_loss(
    session: AsyncSession, business_id: UUID,
    from_date: date | None = None, to_date: date | None = None,
    property_id: UUID | None = None,
) -> dict[str, Any]:
    """Generate a Profit & Loss statement for the period."""
    tb = await trial_balance(session, business_id, as_at=to_date or date.today(), property_id=property_id)

    income = [a for a in tb if a["type"] == AccountType.INCOME.value and a["balance"] != 0]
    expenses = [a for a in tb if a["type"] == AccountType.EXPENSE.value and a["balance"] != 0]

    total_income = sum(a["balance"] for a in income if a["balance"] > 0)
    total_expenses = sum(a["balance"] for a in expenses if a["balance"] > 0)
    net_profit = total_income - total_expenses

    return {
        "period": {"from": str(from_date) if from_date else "all", "to": str(to_date) if to_date else str(date.today())},
        "income": income,
        "expenses": expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "total_income": total_income,
    }


async def balance_sheet(
    session: AsyncSession, business_id: UUID,
    as_at: date | None = None, property_id: UUID | None = None,
) -> dict[str, Any]:
    """Generate a Balance Sheet as at a given date."""
    tb = await trial_balance(session, business_id, as_at=as_at or date.today(), property_id=property_id)

    assets = [a for a in tb if a["type"] in (AccountType.ASSET.value, AccountType.CONTRA_ASSET.value)]
    liabilities = [a for a in tb if a["type"] == AccountType.LIABILITY.value]
    equity = [a for a in tb if a["type"] == AccountType.EQUITY.value]

    total_assets = sum(a["balance"] for a in assets if a["balance"] > 0) - sum(abs(a["balance"]) for a in assets if a["balance"] < 0)
    total_liabilities = sum(a["balance"] for a in liabilities if a["balance"] > 0)
    total_equity = sum(a["balance"] for a in equity if a["balance"] > 0)

    return {
        "as_at": str(as_at or date.today()),
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "net_assets": total_assets - total_liabilities,
    }


# ── Auto-posting hooks ──────────────────────────────────────────────

async def auto_post_invoice(session: AsyncSession, invoice: Any) -> None:
    """When an invoice is created: Dr Tenant Receivables / Cr Rental Income."""
    biz_id = invoice.business_id
    prop_id = invoice.property_id
    recv_id = await get_account_id_by_code(session, biz_id, "1100")
    income_id = await get_account_id_by_code(session, biz_id, "4000")
    if not recv_id or not income_id:
        return

    await post_journal_entry(
        session, biz_id,
        entries=[
            {"account_id": recv_id, "debit": float(invoice.amount), "credit": 0, "property_id": prop_id},
            {"account_id": income_id, "debit": 0, "credit": float(invoice.amount), "property_id": prop_id},
        ],
        entry_date=invoice.created_at.date() if hasattr(invoice.created_at, "date") else date.today(),
        description=f"Invoice {invoice.invoice_number or ''} — {invoice.tenant_id}",
        reference=str(invoice.invoice_number) if invoice.invoice_number else str(invoice.id),
        source_type="invoice",
        source_id=invoice.id,
    )


async def auto_post_payment(session: AsyncSession, payment: Any) -> None:
    """When a payment is received: Dr Cash/Bank / Cr Tenant Receivables."""
    biz_id = payment.business_id
    cash_id = await get_account_id_by_code(session, biz_id, "1000")
    recv_id = await get_account_id_by_code(session, biz_id, "1100")
    if not cash_id or not recv_id:
        return

    await post_journal_entry(
        session, biz_id,
        entries=[
            {"account_id": cash_id, "debit": float(payment.amount), "credit": 0},
            {"account_id": recv_id, "debit": 0, "credit": float(payment.amount)},
        ],
        entry_date=payment.paid_at.date() if hasattr(payment.paid_at, "date") else date.today(),
        description=f"Payment {payment.reference or ''} — {payment.tenant_id}",
        reference=payment.reference or str(payment.id),
        source_type="payment",
        source_id=payment.id,
    )


async def auto_post_expense(session: AsyncSession, expense: Any) -> None:
    """When an expense is recorded: Dr Expense category / Cr Cash/Bank."""
    biz_id = expense.business_id
    cash_id = await get_account_id_by_code(session, biz_id, "1000")
    # Map expense category to COA code
    code_map = {
        "repairs": "5000", "utilities": "5010", "water": "5010", "electricity": "5020",
        "wifi": "5080", "internet": "5080", "cleaning": "5050", "security": "5040",
        "garbage": "5050", "supplies": "5090", "salary": "5030", "wages": "5030",
        "tax": "5070", "insurance": "5060", "marketing": "5100", "advertising": "5100",
        "legal": "5110", "professional": "5110",
    }
    expense_code = code_map.get(expense.category, "5090")  # default to supplies
    expense_acct_id = await get_account_id_by_code(session, biz_id, expense_code)
    if not cash_id or not expense_acct_id:
        return

    await post_journal_entry(
        session, biz_id,
        entries=[
            {"account_id": expense_acct_id, "debit": float(expense.amount), "credit": 0, "property_id": expense.property_id},
            {"account_id": cash_id, "debit": 0, "credit": float(expense.amount)},
        ],
        entry_date=expense.paid_at.date() if hasattr(expense.paid_at, "date") else date.today(),
        description=f"Expense {expense.description or expense.category}",
        reference=str(expense.id),
        source_type="expense",
        source_id=expense.id,
    )
