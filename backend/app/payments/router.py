"""
RENTAL OS — Payments Router

- POST /payments/mpesa/stk  : caretaker triggers STK push to tenant phone
- POST /payments/simulate    : dev path to mark an invoice paid (no Daraja creds)
- POST /payments/mpesa/callback : Safaricom callback (no auth) -> marks paid
- GET  /payments/history     : payment transaction history for the business
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_business, get_current_user
from app.models.billing import Invoice, InvoiceStatus, Payment
from app.models.business import Business, User
from app.models.tenant import Tenant
from app.models.property import Unit
from app.payments import service
from sqlalchemy import select

router = APIRouter(prefix="/payments", tags=["payments"])
callback_router = APIRouter(prefix="/payments", tags=["mpesa-callback"])


class STKRequest(BaseModel):
    invoice_id: str
    phone: str


class RecordPaymentRequest(BaseModel):
    invoice_id: str
    amount: float
    method: str = "cash"

class SimulateRequest(BaseModel):
    invoice_id: str
    amount: float | None = None
    method: str = "mpesa"


@router.post("/mpesa/stk")
async def mpesa_stk(
    data: STKRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    try:
        cid = await service.stk_push(session, data.invoice_id, data.phone)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"checkout_request_id": cid, "status": "STK_PUSH_SENT"}


class STKDirectRequest(BaseModel):
    phone: str
    amount: float
    description: str = "Expense Payment"


@router.post("/mpesa/stk-direct")
async def mpesa_stk_direct(
    data: STKDirectRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    """Trigger an STK push to any phone/amount without an invoice (e.g. expense vendor payment)."""
    try:
        cid = await service.stk_push_direct(session, data.phone, data.amount, data.description)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"checkout_request_id": cid, "status": "STK_PUSH_SENT"}


@router.post("/record")
async def record_payment(
    data: RecordPaymentRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    """Record a cash/on-ground payment collected by a caretaker."""
    inv = await service.apply_payment(
        session, data.invoice_id, data.amount, data.method,
        reference=f"caretaker-{str(user.id)[:8]}",
    )
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    light = "green" if inv.status == InvoiceStatus.PAID.value else "red"
    return {
        "invoice_id": str(inv.id),
        "status": inv.status,
        "balance": float(inv.balance),
        "light": light,
    }


@router.post("/simulate")
async def simulate(
    data: SimulateRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    inv = await service.apply_payment(
        session, data.invoice_id, data.amount or 0, data.method
    )
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    light = "green" if inv.status == InvoiceStatus.PAID.value else "red"
    return {
        "invoice_id": str(inv.id),
        "status": inv.status,
        "balance": float(inv.balance),
        "light": light,
    }


@router.get("/history")
async def payment_history(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Transaction history — all payments for this business."""
    q = (
        select(
            Payment.id,
            Payment.amount,
            Payment.method,
            Payment.reference,
            Payment.status,
            Payment.paid_at,
            Tenant.full_name,
            Tenant.mpesa_phone,
            Unit.unit_number,
            Invoice.invoice_type,
            Invoice.status.label("invoice_status"),
        )
        .select_from(Payment)
        .join(Tenant, Payment.tenant_id == Tenant.id)
        .join(Unit, Payment.lease_id == Unit.current_lease_id, isouter=True)
        .join(Invoice, Payment.invoice_id == Invoice.id, isouter=True)
        .where(Payment.business_id == business.id)
        .order_by(Payment.paid_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(q)).all()
    return {
        "total": len(rows),
        "payments": [
            {
                "id": str(r.id),
                "amount": float(r.amount),
                "method": r.method,
                "reference": r.reference,
                "status": r.status,
                "paid_at": str(r.paid_at),
                "tenant_name": r.full_name,
                "tenant_phone": r.mpesa_phone,
                "unit_number": r.unit_number,
                "invoice_type": r.invoice_type,
                "invoice_status": r.invoice_status,
            }
            for r in rows
        ],
    }


@router.get("/notifications")
async def get_notifications(
    since: str | None = Query(None),
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """Return payments made since timestamp for real-time notifications.

    Owner sees: "House 109 · Moses Karumba paid KES 4,500 via M-Pesa · Full payment"
    Clicking opens tenant detail modal.
    """
    from datetime import datetime, timedelta, timezone

    METHOD_LABELS = {
        "mpesa": "M-Pesa", "airtel": "Airtel Money", "cash": "Cash",
        "bank": "Bank Transfer", "equity": "Equity Bank", "card": "Card",
    }

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = datetime.now(timezone.utc) - timedelta(seconds=60)
    else:
        since_dt = datetime.now(timezone.utc) - timedelta(seconds=60)

    q = (
        select(
            Payment.id,
            Payment.amount,
            Payment.method,
            Payment.reference,
            Payment.status,
            Payment.paid_at,
            Payment.tenant_id,
            Payment.invoice_id,
            Tenant.full_name,
            Tenant.mpesa_phone,
            Unit.unit_number,
            Unit.property_id,
            Invoice.amount.label("invoice_amount"),
            Invoice.paid_amount.label("invoice_paid"),
            Invoice.balance.label("invoice_balance"),
            Invoice.status.label("invoice_status"),
            Invoice.invoice_type,
        )
        .select_from(Payment)
        .join(Tenant, Payment.tenant_id == Tenant.id)
        .join(Invoice, Payment.invoice_id == Invoice.id, isouter=True)
        .join(Unit, Invoice.unit_id == Unit.id, isouter=True)
        .where(
            Payment.business_id == user.business_id,
            Payment.paid_at >= since_dt,
            Payment.status == "completed",
        )
        .order_by(Payment.paid_at.desc())
        .limit(20)
    )
    rows = (await session.execute(q)).all()

    return {
        "notifications": [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "tenant_name": r.full_name,
                "unit_number": r.unit_number or "—",
                "amount": float(r.amount),
                "method": r.method,
                "reference": r.reference,
                "paid_at": str(r.paid_at),
                "invoice_status": r.invoice_status,
                "invoice_balance": float(r.invoice_balance or 0),
                "payment_method_label": {
                    "mpesa": "📱 M-Pesa",
                    "airtel": "📱 Airtel Money",
                    "cash": "💵 Cash",
                    "bank": "🏦 Bank Transfer",
                    "equity": "🏦 Equity Bank",
                    "card": "💳 Card",
                }.get(r.method, r.method or "—"),
                "message": (
                    f"House {r.unit_number or '—'} · {r.full_name} "
                    f"paid KES {float(r.amount):,.0f} via {METHOD_LABELS.get(r.method, r.method or '—')} · "
                    f"{'Full payment' if (r.invoice_balance or 0) <= 0 else f'Remaining KES {float(r.invoice_balance or 0):,.0f}'}"
                ),
            }
            for r in rows
        ],
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


def _construct_mpesa_message(p: Payment) -> dict | None:
    """Reconstruct the full M-Pesa transaction message from stored raw data."""
    raw = p.mpesa_raw
    if not raw:
        return None

    customer_name = (
        raw.get("CustomerName")
        or f"{raw.get('FirstName', '')} {raw.get('LastName', '')}".strip()
        or "—"
    )
    phone = raw.get("PhoneNumber") or raw.get("MSISDN") or ""
    phone_str = f"0{str(phone)[-9:]}" if phone else "—"
    txn_date = raw.get("TransactionDate") or ""
    formatted_date = (
        f"{txn_date[6:8]}/{txn_date[4:6]}/{txn_date[0:4]} at "
        f"{txn_date[8:10]}:{txn_date[10:12]}:{txn_date[12:14]}"
        if len(txn_date) >= 14 else txn_date
    )

    # Build the human-readable message exactly as M-Pesa would show it
    lines = []
    lines.append(f"You have received KES {float(raw.get('Amount', 0)):,.0f} from {customer_name} ({phone_str})")
    lines.append(f"on {formatted_date}")
    lines.append(f"Receipt No: {raw.get('ReceiptNumber', '—')}")
    lines.append(f"Transaction Type: {raw.get('TransactionType', '—')}")
    lines.append(f"Business ShortCode: {raw.get('BusinessShortCode', '—')}")
    lines.append(f"Account Reference: {raw.get('BillRefNumber', '—')}")
    lines.append(f"ThirdParty ID: {raw.get('ThirdPartyTransID', '—')}")

    return {
        "full_message": "\n".join(lines),
        "raw": raw,
        "customer_name": customer_name,
        "phone": phone_str,
        "amount": float(raw.get("Amount", 0)),
        "receipt": raw.get("ReceiptNumber", ""),
        "transaction_date": formatted_date,
    }


@router.get("/{payment_id}/message")
async def get_payment_message(
    payment_id: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Return reconstructed M-Pesa transaction message for a payment."""
    import uuid
    pay = await session.get(Payment, uuid.UUID(payment_id))
    if not pay or pay.business_id != business.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    msg = _construct_mpesa_message(pay)
    if not msg:
        raise HTTPException(status_code=404, detail="No M-Pesa transaction data for this payment")
    return msg


@callback_router.post("/mpesa/callback")
async def mpesa_callback(payload: dict, session: SessionDep):
    try:
        body = (payload.get("Body") or {}).get("stkCallback") or {}
        cid = body.get("CheckoutRequestID")
        result_code = body.get("ResultCode")
        if result_code == 0 and cid:
            items = (body.get("CallbackMetadata") or {}).get("Item") or []
            meta = {item["Name"]: item.get("Value") for item in items if "Name" in item}
            amount = meta.get("Amount")
            receipt = meta.get("ReceiptNumber")

            # Build full M-Pesa metadata record
            mpesa_raw = {
                "CheckoutRequestID": cid,
                "ResultCode": result_code,
                "ResultDesc": body.get("ResultDesc", ""),
                **meta,
            }

            await service.mark_paid_by_checkout(session, cid, amount, receipt, mpesa_raw=mpesa_raw)
    except Exception:
        # Always acknowledge Safaricom so it stops retrying.
        pass
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
