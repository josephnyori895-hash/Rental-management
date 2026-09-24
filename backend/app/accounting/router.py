"""
RENTAL OS — Accounting Router

Endpoints:
  GET  /accounts                  — Chart of Accounts
  GET  /accounts/trial-balance    — Trial Balance
  GET  /accounts/profit-loss      — Profit & Loss statement
  GET  /accounts/balance-sheet    — Balance Sheet
  POST /accounts/journal          — Manual journal entry
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.accounting import service
from app.accounting.models import ChartOfAccount
from app.api.deps import SessionDep, get_current_business
from app.models.business import Business, User
from sqlalchemy import select

router = APIRouter(prefix="/accounts", tags=["accounting"])


class JournalLine(BaseModel):
    account_id: str
    debit: float = 0
    credit: float = 0
    property_id: str | None = None


class JournalRequest(BaseModel):
    entries: list[JournalLine]
    entry_date: str | None = None
    description: str | None = None
    reference: str | None = None


@router.get("")
async def list_accounts(
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """List the Chart of Accounts for this business."""
    accounts = (
        await session.scalars(
            select(ChartOfAccount)
            .where(
                ChartOfAccount.business_id == business.id,
                ChartOfAccount.is_active.is_(True),
            )
            .order_by(ChartOfAccount.sort_order)
        )
    ).all()
    return {
        "accounts": [
            {
                "id": str(a.id),
                "code": a.code,
                "name": a.name,
                "account_type": a.account_type,
                "category": a.category,
                "is_system": a.is_system,
                "description": a.description,
                "sort_order": a.sort_order,
            }
            for a in accounts
        ],
        "total": len(accounts),
    }


@router.get("/trial-balance")
async def get_trial_balance(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    as_at: str | None = Query(None, description="YYYY-MM-DD"),
    property_id: str | None = Query(None),
):
    """Trial Balance — all accounts with debits, credits, and closing balance."""
    as_at_date = date.fromisoformat(as_at) if as_at else date.today()
    prop_uuid = None
    if property_id:
        from uuid import UUID
        prop_uuid = UUID(property_id)

    tb = await service.trial_balance(session, business.id, as_at=as_at_date, property_id=prop_uuid)
    total_debit = sum(a["debit"] for a in tb)
    total_credit = sum(a["credit"] for a in tb)
    return {
        "as_at": str(as_at_date),
        "accounts": tb,
        "totals": {"debit": total_debit, "credit": total_credit},
    }


@router.get("/profit-loss")
async def get_profit_loss(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    property_id: str | None = Query(None),
):
    """Profit & Loss statement for a period."""
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else date.today()
    prop_uuid = None
    if property_id:
        from uuid import UUID
        prop_uuid = UUID(property_id)

    pl = await service.profit_and_loss(session, business.id, from_date=fd, to_date=td, property_id=prop_uuid)
    return pl


@router.get("/balance-sheet")
async def get_balance_sheet(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    as_at: str | None = Query(None, description="YYYY-MM-DD"),
    property_id: str | None = Query(None),
):
    """Balance Sheet as at a given date."""
    as_at_date = date.fromisoformat(as_at) if as_at else date.today()
    prop_uuid = None
    if property_id:
        from uuid import UUID
        prop_uuid = UUID(property_id)

    bs = await service.balance_sheet(session, business.id, as_at=as_at_date, property_id=prop_uuid)
    return bs


@router.post("/journal", status_code=201)
async def post_journal(
    data: JournalRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Post a manual journal entry (double-entry)."""
    from uuid import UUID

    entry_date = date.fromisoformat(data.entry_date) if data.entry_date else date.today()
    entries = [
        {
            "account_id": UUID(e.account_id),
            "debit": e.debit,
            "credit": e.credit,
            "property_id": UUID(e.property_id) if e.property_id else None,
        }
        for e in data.entries
    ]

    try:
        await service.post_journal_entry(
            session, business.id, entries,
            entry_date=entry_date,
            description=data.description,
            reference=data.reference,
            source_type="manual",
        )
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "posted", "entries": len(entries)}
