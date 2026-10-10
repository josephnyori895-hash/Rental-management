"""
RENTAL OS — WhatsApp Inbound: Tenant Commands

Handles commands sent by registered tenants:
  BALANCE, PAY, RECEIPT, REPORT <msg>, RENEW, HELP, LATER

Dispatched from `app.notifications.inbound.parse_and_handle`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Invoice
from app.models.business import Business, User, UserRole
from app.models.lease import Lease
from app.models.property import Unit
from app.models.tenant import Tenant
from app.notifications.service import (
    _build_wa_balance,
    _build_wa_help,
    _build_wa_payment_receipt,
    _format_phone,
    send_notification,
    send_wa_balance,
    send_wa_help,
    send_wa_payment_receipt,
)


async def _find_caretaker_phone(session: AsyncSession, business_id: uuid.UUID) -> str | None:
    """Find the first active caretaker's WhatsApp phone for this business."""
    q = select(User).where(
        User.business_id == business_id,
        User.role == UserRole.AGENT.value,
        User.is_active.is_(True),
    ).limit(1)
    user = await session.scalar(q)
    if user:
        return user.phone
    # Fallback: owner's phone
    q2 = select(User).where(
        User.business_id == business_id,
        User.role == UserRole.OWNER.value,
        User.is_active.is_(True),
    ).limit(1)
    user2 = await session.scalar(q2)
    return user2.phone if user2 else None


# ── Tenant commands ────────────────────────────────────────────────

async def _handle_tenant_command(
    session: AsyncSession, tenant: Tenant,
    text: str, text_lower: str, msg_id: str | None,
) -> dict | None:
    business_id = tenant.business_id

    if text == "BALANCE":
        return await _cmd_tenant_balance(session, tenant, business_id)

    elif text == "PAY":
        return await _cmd_tenant_pay(session, tenant, business_id)

    elif text == "RECEIPT":
        return await _cmd_tenant_receipt(session, tenant, business_id)

    elif text == "HELP":
        await send_wa_help(session, business_id, tenant)
        return {"to": tenant.whatsapp_phone, "message": _build_wa_help()}

    elif text == "RENEW":
        return await _cmd_tenant_renew(session, tenant, business_id)

    elif text.startswith("REPORT"):
        issue = text_lower[6:].strip() if len(text_lower) > 6 else ""
        if not issue:
            return {"to": tenant.whatsapp_phone, "message": "Please describe the issue after REPORT. Example: REPORT leaking tap in kitchen."}
        return await _cmd_tenant_report(session, tenant, business_id, issue)

    elif text == "LATER":
        return {"to": tenant.whatsapp_phone, "message": "You have 24 hours to complete payment. We'll remind you."}

    else:
        return {"to": tenant.whatsapp_phone, "message": f"Unknown command. Reply HELP for available options."}


async def _cmd_tenant_balance(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID) -> dict:
    lease = await session.scalar(
        select(Lease).where(Lease.tenant_id == tenant.id, Lease.status == "active").limit(1)
    )
    total_balance = 0.0
    due_date = None

    if lease:
        result = await session.execute(
            select(func.coalesce(func.sum(Invoice.balance), 0)).where(
                Invoice.lease_id == lease.id,
                Invoice.status.in_(["pending", "partial", "overdue"]),
            )
        )
        total_balance = float(result.scalar() or 0)
        inv = await session.scalar(
            select(Invoice).where(
                Invoice.lease_id == lease.id,
                Invoice.status.in_(["pending", "partial", "overdue"]),
                Invoice.balance > 0,
            ).order_by(Invoice.due_date.asc()).limit(1)
        )
        if inv and inv.due_date:
            due_date = str(inv.due_date)

    unit_number = "—"
    if lease:
        u = await session.get(Unit, lease.unit_id)
        if u:
            unit_number = u.unit_number

    await send_wa_balance(session, business_id, tenant, total_balance, due_date)
    return {"to": tenant.whatsapp_phone, "message": _build_wa_balance(tenant.full_name, unit_number, total_balance, due_date)}


async def _cmd_tenant_pay(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID) -> dict:
    """Initiate payment details or STK Push for the outstanding balance (rent + deposit)."""
    lease = await session.scalar(
        select(Lease).where(Lease.tenant_id == tenant.id, Lease.status == "active").limit(1)
    )
    if not lease:
        return {"to": tenant.whatsapp_phone, "message": "No active lease found. Contact your property manager."}

    # Sum ALL pending/partial/overdue balances (rent + deposit)
    result = await session.execute(
        select(func.coalesce(func.sum(Invoice.balance), 0)).where(
            Invoice.lease_id == lease.id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
        )
    )
    amount = float(result.scalar() or 0)
    if amount <= 0:
        return {"to": tenant.whatsapp_phone, "message": "You have no outstanding balance. You're all paid up! ✅"}

    # Determine M-Pesa number
    mpesa_phone = _format_phone(tenant.mpesa_phone or tenant.whatsapp_phone or tenant.phone or "")
    if not mpesa_phone:
        return {"to": tenant.whatsapp_phone, "message": "No M-Pesa number on file. Contact your property manager."}

    u = await session.get(Unit, lease.unit_id)
    unit_no = u.unit_number if u else "—"

    # Check business payment method configuration (M-Pesa vs Bank)
    bus = await session.get(Business, business_id)
    bus_cfg = (bus.settings or {}).get("business", {}) if bus else {}
    payment_method = bus_cfg.get("payment_method", "mpesa")

    # ── Bank Payment Flow ─────────────────────────────────────────
    if payment_method == "bank":
        bank_name = bus_cfg.get("bank_name", "Equity Bank")
        bank_acc = bus_cfg.get("bank_account", "—")
        acc_name = bus_cfg.get("bank_account_name", bus.name if bus else "Hostel")
        msg = (
            f"🏦 BANK PAYMENT — KES {amount:,.0f} for {unit_no}\n\n"
            f"Please transfer to our Bank Account:\n"
            f"  Bank: {bank_name}\n"
            f"  Account: {bank_acc}\n"
            f"  Name: {acc_name}\n\n"
            f"Reply DONE <transaction_reference> once complete."
        )
        return {"to": tenant.whatsapp_phone, "message": msg}

    # ── Try real Daraja STK push ──────────────────────────────────
    if settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET:
        try:
            from app.payments import service as pay_svc
            desc = f"Move-in {unit_no}" if amount > float(lease.rent_amount or 0) else f"Rent {unit_no}"
            await pay_svc.stk_push_direct(session, mpesa_phone, amount, desc)
            return {
                "to": tenant.whatsapp_phone,
                "message": (
                    f"💳 STK Push sent!\n"
                    f"Amount: KES {amount:,.0f}\n"
                    f"Phone: {mpesa_phone}\n"
                    f"Enter your M-Pesa PIN to complete payment.\n\n"
                    f"Reply RECEIPT after paying to get your receipt."
                ),
            }
        except Exception:
            # Fall through to Paybill instructions
            pass

    # ── Fallback: Paybill instructions ───────────────────────────
    msg = (
        f"💰 PAY KES {amount:,.0f} for {unit_no}\n\n"
        f"Via M-Pesa Paybill:\n"
        f"  1. Go to M-Pesa → Paybill\n"
        f"  2. Business No: {getattr(settings, 'MPESA_SHORTCODE', '247247')}\n"
        f"  3. Account: {unit_no}\n"
        f"  4. Amount: {amount:,.0f}\n"
        f"  5. Enter PIN & confirm\n\n"
        f"Reply RECEIPT after paying."
    )
    return {"to": tenant.whatsapp_phone, "message": msg}


async def _cmd_tenant_receipt(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID) -> dict:
    lease = await session.scalar(
        select(Lease).where(Lease.tenant_id == tenant.id, Lease.status == "active").limit(1)
    )
    if not lease:
        return {"to": tenant.whatsapp_phone, "message": "No active lease found."}

    payment = await session.scalar(
        select(Invoice).where(
            Invoice.lease_id == lease.id,
            Invoice.status == "paid",
        ).order_by(Invoice.updated_at.desc()).limit(1)
    )
    if not payment:
        return {"to": tenant.whatsapp_phone, "message": "No recent payments found."}

    u = await session.get(Unit, lease.unit_id)
    unit_no = u.unit_number if u else "—"
    body = _build_wa_payment_receipt(tenant.full_name, unit_no, float(payment.paid_amount or 0), payment.reference, "paid")
    await send_wa_payment_receipt(session, None, tenant, unit_no, "paid")  # uses payment=None to just send
    return {"to": tenant.whatsapp_phone, "message": body}


async def _cmd_tenant_report(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID, issue: str) -> dict:
    """Create a maintenance ticket and notify caretaker."""
    from app.models.maintenance import MaintenanceTicket
    from app.models.property import Property as PropertyModel

    lease = await session.scalar(
        select(Lease).where(Lease.tenant_id == tenant.id, Lease.status == "active").limit(1)
    )
    unit_id = lease.unit_id if lease else None

    prop_id = None
    if unit_id:
        u2 = await session.get(Unit, unit_id)
        if u2:
            prop_id = u2.property_id
    if not prop_id:
        prop = await session.scalar(
            select(PropertyModel).where(PropertyModel.business_id == business_id).limit(1)
        )
        prop_id = prop.id if prop else uuid.uuid4()

    ticket = MaintenanceTicket(
        business_id=business_id,
        property_id=prop_id,
        unit_id=unit_id,
        tenant_id=tenant.id,
        title=issue[:100],
        description=issue,
        status="open",
        priority="medium",
    )
    session.add(ticket)
    await session.commit()

    # Notify caretaker
    u = await session.get(Unit, unit_id) if unit_id else None
    unit_no = u.unit_number if u else "—"

    caretaker_phone = await _find_caretaker_phone(session, business_id)
    if caretaker_phone:
        from app.notifications.service import notify_caretaker_ticket
        await notify_caretaker_ticket(session, business_id, caretaker_phone, tenant.full_name, unit_no, issue, str(ticket.id)[:8])

    return {"to": tenant.whatsapp_phone, "message": f"✅ Ticket #{str(ticket.id)[:8]} created. We'll notify you when it's resolved."}


async def _cmd_tenant_renew(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID) -> dict:
    lease = await session.scalar(
        select(Lease).where(Lease.tenant_id == tenant.id, Lease.status == "active").limit(1)
    )
    if not lease:
        return {"to": tenant.whatsapp_phone, "message": "No active lease to renew."}

    u = await session.get(Unit, lease.unit_id)
    unit_no = u.unit_number if u else "—"

    # Notify owner/caretaker about renewal request
    caretaker_phone = await _find_caretaker_phone(session, business_id)
    if caretaker_phone:
        await send_notification(
            session=session, business_id=business_id, tenant_id=tenant.id,
            channel="whatsapp", recipient=caretaker_phone,
            template_name="caretaker_renewal_request",
            body=f"📋 RENEWAL REQUEST — {tenant.full_name} ({unit_no})\nTenant wants to renew their lease.",
        )

    return {"to": tenant.whatsapp_phone, "message": f"Your renewal request for {unit_no} has been received. The property manager will follow up."}
