"""
RENTAL OS — Reconciliation Router

Endpoints for M-Pesa auto-reconciliation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_business
from app.models.business import Business
from app.reconciliation.service import (
    get_unmatched_payments,
    match_payment,
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
    """List mobile-money payments and bank claims not yet linked to an invoice."""
    payments = await get_unmatched_payments(session, business.id, limit)
    return {"total": len(payments), "payments": payments}


class MatchRequest(BaseModel):
    invoice_id: str


@router.post("/{payment_id}/match")
async def match_to_invoice(
    payment_id: str,
    data: MatchRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Confirm a bank transfer / unmatched payment against an invoice."""
    try:
        return await match_payment(
            session,
            business.id,
            uuid.UUID(payment_id),
            uuid.UUID(data.invoice_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
