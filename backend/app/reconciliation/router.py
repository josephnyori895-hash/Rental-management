"""
RENTAL OS — Reconciliation Router

Endpoints for M-Pesa auto-reconciliation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_business
from app.models.business import Business
from app.reconciliation.service import (
    get_unmatched_payments,
    reconcile_pending,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post("/run")
async def run_reconciliation(
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Run auto-reconciliation: match unmatched M-Pesa payments to invoices."""
    result = await reconcile_pending(session, business.id)
    return result


@router.get("/unmatched")
async def list_unmatched(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    limit: int = Query(50, le=200),
):
    """List M-Pesa payments not yet linked to any invoice."""
    payments = await get_unmatched_payments(session, business.id, limit)
    return {"total": len(payments), "payments": payments}
