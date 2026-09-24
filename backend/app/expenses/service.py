"""
RENTAL OS — Expenses Service
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_expense
from app.models.expense import Expense


async def create_expense(session: AsyncSession, business_id: UUID, data: dict) -> dict:
    exp = Expense(
        business_id=business_id,
        property_id=UUID(data["property_id"]) if data.get("property_id") else None,
        category=data.get("category", "misc"),
        amount=data["amount"],
        description=data.get("description"),
        vendor=data.get("vendor"),
        paid_at=data.get("paid_at", date.today()),
        recurring=data.get("recurring", False),
        notes=data.get("notes"),
    )
    session.add(exp)
    await session.flush()
    # Auto-post to general ledger
    try:
        await auto_post_expense(session, exp)
    except Exception:
        pass
    return _expense_to_dict(exp)


async def get_expenses(
    session: AsyncSession,
    business_id: UUID,
    category: str | None = None,
    property_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    q = select(Expense).where(Expense.business_id == business_id)
    if category:
        q = q.where(Expense.category == category)
    if property_id:
        q = q.where(Expense.property_id == property_id)
    if from_date:
        q = q.where(Expense.paid_at >= from_date)
    if to_date:
        q = q.where(Expense.paid_at <= to_date)
    
    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.scalar(count_q)) or 0
    
    q = q.order_by(Expense.paid_at.desc()).offset(offset).limit(limit)
    rows = (await session.scalars(q)).all()
    return [_expense_to_dict(e) for e in rows], total


async def get_expense_summary(
    session: AsyncSession,
    business_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    q = select(Expense).where(Expense.business_id == business_id)
    if from_date:
        q = q.where(Expense.paid_at >= from_date)
    if to_date:
        q = q.where(Expense.paid_at <= to_date)
    
    rows = (await session.scalars(q)).all()
    
    total = sum(float(e.amount) for e in rows)
    by_category: dict[str, float] = {}
    for e in rows:
        cat = e.category
        by_category[cat] = by_category.get(cat, 0) + float(e.amount)
    
    return {
        "total": round(total, 2),
        "count": len(rows),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
    }


def _expense_to_dict(e: Expense) -> dict:
    return {
        "id": str(e.id),
        "property_id": str(e.property_id) if e.property_id else None,
        "category": e.category,
        "amount": float(e.amount),
        "description": e.description,
        "vendor": e.vendor,
        "paid_at": str(e.paid_at),
        "recurring": e.recurring,
        "notes": e.notes,
        "created_at": str(e.created_at),
    }
