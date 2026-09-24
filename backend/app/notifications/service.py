"""
RENTAL OS — Notifications Service

Core engine: sends SMS/WhatsApp via configured provider, logs every message,
provides builder methods for templates:
  - SMS: rent_reminder, payment_receipt, lease_expiry
  - WhatsApp: welcome_enrollment, payment_prompt, rent_reminder,
              payment_receipt, maintenance_update, lease_expiry
  - Caretaker: ticket_alert, payment_alert, move_in_alert, unpaid_alert
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Payment
from app.models.lease import Lease
from app.models.tenant import Tenant
from app.notifications.models import NotificationLog
from app.notifications.providers import (
    AfricaStalkingProvider,
    AfricaStalkingWhatsAppProvider,
    ConsoleProvider,
    ConsoleWhatsAppProvider,
    NotificationProvider,
)


# ── Provider selection ─────────────────────────────────────────────

def _get_sms_provider() -> NotificationProvider:
    if settings.AT_API_KEY and settings.AT_USERNAME:
        return AfricaStalkingProvider()
    return ConsoleProvider()


def _get_whatsapp_provider() -> NotificationProvider:
    if settings.AT_API_KEY and settings.AT_USERNAME:
        return AfricaStalkingWhatsAppProvider()
    return ConsoleWhatsAppProvider()


def _format_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("0"):
        cleaned = "254" + cleaned[1:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned


# ── SMS template builders ─────────────────────────────────────────

def _build_rent_reminder_sms(
    tenant_name: str, unit_number: str, amount_due: float,
    due_date: str, balance: float | None = None,
) -> str:
    msg = (
        f"RENT REMINDER — {tenant_name}\n"
        f"House {unit_number}\n"
        f"Amount Due: KES {amount_due:,.0f}\n"
        f"Due: {due_date}\n"
    )
    if balance:
        msg += f"Outstanding Balance: KES {balance:,.0f}\n"
    msg += "Pay via M-Pesa Paybill 247247 (Account: Your Unit No.) or contact your caretaker."
    return msg


def _build_payment_receipt_sms(
    tenant_name: str, unit_number: str, amount: float,
    method: str, receipt: str | None = None,
    invoice_status: str | None = None,
) -> str:
    method_labels = {
        "mpesa": "M-Pesa", "airtel": "Airtel Money", "cash": "Cash",
        "bank": "Bank Transfer", "equity": "Equity Bank", "card": "Card",
    }
    label = method_labels.get(method, method or "—")
    msg = (
        f"PAYMENT RECEIVED ✅ — {tenant_name}\n"
        f"House {unit_number}\n"
        f"Amount: KES {amount:,.0f}\n"
        f"Method: {label}\n"
    )
    if receipt:
        msg += f"Receipt: {receipt}\n"
    if invoice_status:
        status_label = "FULLY PAID 🟢" if invoice_status == "paid" else "PARTIAL — Balance remaining"
        msg += f"Status: {status_label}\n"
    msg += "Thank you for your payment."
    return msg


def _build_lease_expiry_sms(tenant_name: str, unit_number: str, end_date: str, days_left: int) -> str:
    return (
        f"LEASE EXPIRY NOTICE — {tenant_name}\n"
        f"House {unit_number}\n"
        f"Your lease ends on {end_date} ({days_left} days remaining).\n"
        f"Please contact your landlord to renew."
    )


# ── WhatsApp template builders ────────────────────────────────────

def _build_wa_welcome_enrollment(
    tenant_name: str, property_name: str, unit_number: str,
    rent_amount: float, deposit_amount: float | None, total: float,
    rent_only: bool = False,
    bank_info: dict | None = None,
) -> str:
    lines = [f"🏠 Welcome to {property_name}, {tenant_name}!"]
    lines.append(f"")
    lines.append(f"To complete move-in to {unit_number}:")
    lines.append(f"  Rent: KES {rent_amount:,.0f}")
    if deposit_amount and not rent_only:
        lines.append(f"  Deposit: KES {deposit_amount:,.0f}")
    lines.append(f"  ─────────────────")
    lines.append(f"  Total: KES {total:,.0f}")
    lines.append(f"")
    if bank_info and bank_info.get("payment_method") == "bank":
        lines.append(f"Please deposit/transfer payment to:")
        lines.append(f"  Bank: {bank_info.get('bank_name', 'Equity Bank')}")
        lines.append(f"  Account: {bank_info.get('bank_account', '—')}")
        lines.append(f"  Name: {bank_info.get('bank_account_name', 'Hostel')}")
        lines.append(f"")
        lines.append(f"Reply DONE <reference> once paid.")
    else:
        lines.append(f"Reply PAY to pay now via M-Pesa")
        lines.append(f"Reply LATER to pay within 24h")
    return "\n".join(lines)


def _build_wa_payment_prompt(amount: float, unit_number: str) -> str:
    return (
        f"💰 Payment of KES {amount:,.0f} for {unit_number} is ready.\n"
        f"A prompt will be sent to your phone.\n"
        f"Reply PAY to proceed or CANCEL to stop."
    )


def _build_wa_rent_reminder(
    tenant_name: str, unit_number: str, amount_due: float,
    due_date: str, balance: float | None = None,
) -> str:
    msg = (
        f"🔔 RENT REMINDER — {tenant_name}\n"
        f"House {unit_number}\n"
        f"Due: KES {amount_due:,.0f}\n"
        f"Date: {due_date}\n"
    )
    if balance:
        msg += f"Balance: KES {balance:,.0f}\n"
    msg += "\nReply PAY to pay now"
    return msg


def _build_wa_payment_receipt(
    tenant_name: str, unit_number: str, amount: float,
    receipt: str | None = None, status: str | None = None,
) -> str:
    msg = (
        f"✅ PAID — {tenant_name}\n"
        f"{unit_number}\n"
        f"Amount: KES {amount:,.0f}\n"
    )
    if receipt:
        msg += f"Ref: {receipt}\n"
    if status:
        msg += f"Status: {'FULLY PAID' if status == 'paid' else 'PARTIAL'}\n"
    msg += "Reply BALANCE to check or REPORT for issues."
    return msg


def _build_wa_maintenance_update(tenant_name: str, unit_number: str, ticket_id: str, status: str) -> str:
    status_icon = "🔧" if status == "open" else "✅" if status == "completed" else "⏳"
    return (
        f"{status_icon} MAINTENANCE #{ticket_id}\n"
        f"{tenant_name} — {unit_number}\n"
        f"Status: {status.upper()}\n"
        + ("Reply REPORT for new issues." if status == "completed" else "We'll update you when done.")
    )


def _build_wa_lease_expiry(tenant_name: str, unit_number: str, end_date: str, days_left: int) -> str:
    return (
        f"📋 LEASE EXPIRY\n"
        f"{tenant_name} — {unit_number}\n"
        f"Ends: {end_date} ({days_left} days)\n"
        f"Reply RENEW to extend."
    )


def _build_wa_balance(tenant_name: str, unit_number: str, balance: float, due_date: str | None) -> str:
    msg = (
        f"💰 Balance for {tenant_name}\n"
        f"{unit_number}\n"
        f"Outstanding: KES {balance:,.0f}\n"
    )
    if due_date:
        msg += f"Due: {due_date}\n"
    if balance > 0:
        msg += "Reply PAY to pay now"
    else:
        msg += "You're all clear! ✅"
    return msg


def _build_wa_help() -> str:
    return (
        "Reply with a keyword:\n"
        "BALANCE — Check your balance\n"
        "PAY — Pay rent via M-Pesa\n"
        "RECEIPT — Get last receipt\n"
        "REPORT — Report maintenance issue\n"
        "RENEW — Request lease renewal\n"
        "HELP — Show this menu"
    )


# ── Caretaker WhatsApp template builders ─────────────────────────

def _build_wa_caretaker_ticket(tenant_name: str, unit_number: str, issue: str, ticket_id: str) -> str:
    return (
        f"🔧 MAINTENANCE — #{ticket_id}\n"
        f"{tenant_name} ({unit_number}):\n"
        f'"{issue}"\n'
        f"Reply FIXED with photo when done."
    )


def _build_wa_caretaker_payment(tenant_name: str, unit_number: str, amount: float, method: str) -> str:
    return (
        f"💰 PAYMENT RECEIVED\n"
        f"{tenant_name} — {unit_number}\n"
        f"KES {amount:,.0f} via {method.upper()}"
    )


def _build_wa_caretaker_move_in(tenant_name: str, unit_number: str, date: str) -> str:
    return (
        f"📋 MOVE-IN\n"
        f"{tenant_name} — {unit_number}\n"
        f"Date: {date}\n"
        f"Prepare unit for occupancy."
    )


def _build_wa_caretaker_unpaid(tenant_name: str, unit_number: str, amount: float, days_overdue: int) -> str:
    return (
        f"⚠️ UNPAID — {tenant_name}\n"
        f"{unit_number}\n"
        f"KES {amount:,.0f} overdue by {days_overdue} days\n"
        f"Please follow up."
    )


# ── Core send functions ───────────────────────────────────────────

async def send_notification(
    session: AsyncSession,
    business_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    channel: str,
    recipient: str,
    template_name: str | None,
    body: str,
    sender_id: str | None = None,
) -> NotificationLog:
    """Send via the right provider and log the result."""
    if channel == "whatsapp":
        provider = _get_whatsapp_provider()
    else:
        provider = _get_sms_provider()

    provider_name = provider.__class__.__name__.replace("Provider", "").lower()

    result = await provider.send(recipient, body, sender_id)

    log = NotificationLog(
        business_id=business_id,
        tenant_id=tenant_id,
        channel=channel,
        recipient=recipient,
        template_name=template_name,
        body=body,
        status="sent" if result["success"] else "failed",
        provider=provider_name,
        provider_message_id=result.get("provider_message_id"),
        error=result.get("error"),
        sent_at=datetime.now(timezone.utc) if result["success"] else None,
    )
    session.add(log)
    await session.commit()
    return log


# ── SMS senders ────────────────────────────────────────────────────

async def send_rent_reminder_sms(
    session: AsyncSession,
    business_id: uuid.UUID,
    tenant: Tenant,
    lease: Lease,
    amount_due: float,
    due_date: str,
    balance: float | None = None,
) -> NotificationLog | None:
    phone = tenant.mpesa_phone or tenant.phone
    if not phone:
        return None
    body = _build_rent_reminder_sms(tenant.full_name, lease.unit_number if hasattr(lease, "unit_number") else "—", amount_due, due_date, balance)
    return await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel="sms", recipient=phone, template_name="rent_reminder", body=body)


async def send_payment_receipt_sms(
    session: AsyncSession, payment: Payment,
    tenant: Tenant | None = None, unit_number: str | None = None,
    invoice_status: str | None = None,
) -> NotificationLog | None:
    if not tenant:
        tenant = await session.get(Tenant, payment.tenant_id)
    if not tenant:
        return None
    phone = tenant.mpesa_phone or tenant.phone
    if not phone:
        return None
    body = _build_payment_receipt_sms(tenant.full_name, unit_number or "—", float(payment.amount), payment.method, payment.reference, invoice_status)
    return await send_notification(session=session, business_id=payment.business_id, tenant_id=tenant.id, channel="sms", recipient=phone, template_name="payment_receipt", body=body)


async def process_due_reminders(session: AsyncSession, business_id: uuid.UUID) -> int:
    from datetime import date, timedelta
    from datetime import datetime as dt
    from sqlalchemy import func as sa_func
    from app.models.billing import Invoice
    from app.models.property import Unit

    today = date.today()
    leases_q = select(Lease).where(Lease.business_id == business_id, Lease.status == "active")
    leases = (await session.scalars(leases_q)).all()
    sent = 0

    for lease in leases:
        tenant = await session.get(Tenant, lease.tenant_id)
        if not tenant:
            continue
        unit = await session.get(Unit, lease.unit_id)
        due_soon = today + timedelta(days=3)
        inv_q = select(Invoice).where(
            Invoice.lease_id == lease.id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
            Invoice.balance > 0,
            Invoice.due_date <= due_soon,
        ).order_by(Invoice.due_date.asc()).limit(1)
        invoice = (await session.scalars(inv_q)).first()
        if not invoice:
            continue

        today_start = dt.combine(today, dt.min.time()).replace(tzinfo=timezone.utc)
        already_sent = await session.scalar(
            select(sa_func.count(NotificationLog.id)).where(
                NotificationLog.tenant_id == tenant.id,
                NotificationLog.template_name == "rent_reminder",
                NotificationLog.created_at >= today_start,
                NotificationLog.status == "sent",
            )
        )
        if already_sent and already_sent > 0:
            continue

        phone = tenant.mpesa_phone or tenant.phone
        if not phone:
            continue

        target_channel = "whatsapp" if tenant.whatsapp_phone else "sms"
        target_phone = tenant.whatsapp_phone or phone

        if target_channel == "whatsapp":
            body = _build_wa_rent_reminder(tenant.full_name, unit.unit_number if unit else "—", float(invoice.balance), str(invoice.due_date) if invoice.due_date else "—")
        else:
            body = _build_rent_reminder_sms(tenant.full_name, unit.unit_number if unit else "—", float(invoice.balance), str(invoice.due_date) if invoice.due_date else "—")

        log = await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel=target_channel, recipient=target_phone, template_name="rent_reminder", body=body)
        if log.status == "sent":
            sent += 1
    return sent


# ── WhatsApp senders ───────────────────────────────────────────────

async def send_wa_enrollment_prompt(
    session: AsyncSession,
    business_id: uuid.UUID,
    tenant: Tenant,
    property_name: str,
    unit_number: str,
    rent_amount: float,
    deposit_amount: float | None,
    rent_only: bool = False,
) -> NotificationLog | None:
    """Send WhatsApp welcome + payment prompt to newly registered tenant."""
    phone = tenant.whatsapp_phone
    if not phone:
        return None
    total = rent_amount + (deposit_amount or 0) if not rent_only else rent_amount
    
    # Load business settings to check for Bank configuration
    from app.models.business import Business
    bus = await session.get(Business, business_id)
    bank_info = (bus.settings or {}).get("business", {}) if bus else None

    body = _build_wa_welcome_enrollment(
        tenant.full_name, property_name, unit_number, rent_amount, deposit_amount, total, rent_only, bank_info
    )
    return await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel="whatsapp", recipient=phone, template_name="wa_welcome_enrollment", body=body)


async def send_wa_balance(
    session: AsyncSession, business_id: uuid.UUID, tenant: Tenant,
    balance: float, due_date: str | None = None,
) -> NotificationLog | None:
    phone = tenant.whatsapp_phone
    if not phone:
        return None
    unit = "—"
    # Try to find active lease for unit number
    from app.models.lease import Lease as LeaseModel
    lease = await session.scalar(select(LeaseModel).where(LeaseModel.tenant_id == tenant.id, LeaseModel.status == "active").limit(1))
    if lease:
        from app.models.property import Unit
        u = await session.get(Unit, lease.unit_id)
        if u:
            unit = u.unit_number
    body = _build_wa_balance(tenant.full_name, unit, balance, due_date)
    return await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel="whatsapp", recipient=phone, template_name="wa_balance", body=body)


async def send_wa_payment_receipt(
    session: AsyncSession, payment: Payment,
    tenant: Tenant | None = None, unit_number: str | None = None,
    invoice_status: str | None = None,
) -> NotificationLog | None:
    if not tenant:
        tenant = await session.get(Tenant, payment.tenant_id)
    if not tenant:
        return None
    phone = tenant.whatsapp_phone
    if not phone:
        # Fallback to SMS
        return await send_payment_receipt_sms(session, payment, tenant, unit_number, invoice_status)
    body = _build_wa_payment_receipt(tenant.full_name, unit_number or "—", float(payment.amount), payment.reference, invoice_status)
    return await send_notification(session=session, business_id=payment.business_id, tenant_id=tenant.id, channel="whatsapp", recipient=phone, template_name="wa_payment_receipt", body=body)


async def send_wa_maintenance_update(
    session: AsyncSession, business_id: uuid.UUID,
    tenant: Tenant, ticket_id: str, status: str,
) -> NotificationLog | None:
    phone = tenant.whatsapp_phone
    if not phone:
        return None
    unit = "—"
    from app.models.property import Unit
    lease = await session.scalar(select(Lease).where(Lease.tenant_id == tenant.id, Lease.status == "active").limit(1))
    if lease:
        u = await session.get(Unit, lease.unit_id)
        if u:
            unit = u.unit_number
    body = _build_wa_maintenance_update(tenant.full_name, unit, ticket_id, status)
    return await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel="whatsapp", recipient=phone, template_name="wa_maintenance_update", body=body)


async def send_wa_lease_expiry(
    session: AsyncSession, business_id: uuid.UUID,
    tenant: Tenant, unit_number: str, end_date: str, days_left: int,
) -> NotificationLog | None:
    phone = tenant.whatsapp_phone
    if not phone:
        return None
    body = _build_wa_lease_expiry(tenant.full_name, unit_number, end_date, days_left)
    return await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel="whatsapp", recipient=phone, template_name="wa_lease_expiry", body=body)


async def send_wa_help(
    session: AsyncSession, business_id: uuid.UUID,
    tenant: Tenant,
) -> NotificationLog | None:
    phone = tenant.whatsapp_phone
    if not phone:
        return None
    body = _build_wa_help()
    return await send_notification(session=session, business_id=business_id, tenant_id=tenant.id, channel="whatsapp", recipient=phone, template_name="wa_help", body=body)


# ── Caretaker WhatsApp senders ─────────────────────────────────────

async def send_wa_to_caretaker(
    session: AsyncSession, business_id: uuid.UUID,
    phone: str, body: str, template_name: str,
) -> NotificationLog:
    """Send a WhatsApp message to a caretaker/owner."""
    return await send_notification(
        session=session, business_id=business_id, tenant_id=None,
        channel="whatsapp", recipient=phone,
        template_name=template_name, body=body,
    )


async def notify_caretaker_ticket(
    session: AsyncSession, business_id: uuid.UUID,
    caretaker_phone: str, tenant_name: str, unit_number: str,
    issue: str, ticket_id: str,
) -> NotificationLog | None:
    if not caretaker_phone:
        return None
    body = _build_wa_caretaker_ticket(tenant_name, unit_number, issue, ticket_id)
    return await send_wa_to_caretaker(session, business_id, caretaker_phone, body, "caretaker_ticket")


async def notify_caretaker_payment(
    session: AsyncSession, business_id: uuid.UUID,
    caretaker_phone: str, tenant_name: str, unit_number: str,
    amount: float, method: str,
) -> NotificationLog | None:
    if not caretaker_phone:
        return None
    body = _build_wa_caretaker_payment(tenant_name, unit_number, amount, method)
    return await send_wa_to_caretaker(session, business_id, caretaker_phone, body, "caretaker_payment")


async def notify_caretaker_move_in(
    session: AsyncSession, business_id: uuid.UUID,
    caretaker_phone: str, tenant_name: str, unit_number: str,
    date: str,
) -> NotificationLog | None:
    if not caretaker_phone:
        return None
    body = _build_wa_caretaker_move_in(tenant_name, unit_number, date)
    return await send_wa_to_caretaker(session, business_id, caretaker_phone, body, "caretaker_move_in")


async def notify_caretaker_unpaid(
    session: AsyncSession, business_id: uuid.UUID,
    caretaker_phone: str, tenant_name: str, unit_number: str,
    amount: float, days_overdue: int,
) -> NotificationLog | None:
    if not caretaker_phone:
        return None
    body = _build_wa_caretaker_unpaid(tenant_name, unit_number, amount, days_overdue)
    return await send_wa_to_caretaker(session, business_id, caretaker_phone, body, "caretaker_unpaid")
