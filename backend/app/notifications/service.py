"""
RENTAL OS — Notifications Service

Core engine: sends SMS/WhatsApp via the configured provider and logs every
message. Message text is built by the pure builders in
`app.notifications.templates`, which are re-exported here for backwards
compatibility with existing importers.
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
from app.notifications.templates import (
    _build_lease_expiry_sms,
    _build_payment_receipt_sms,
    _build_rent_reminder_sms,
    _build_wa_balance,
    _build_wa_caretaker_move_in,
    _build_wa_caretaker_payment,
    _build_wa_caretaker_ticket,
    _build_wa_caretaker_unpaid,
    _build_wa_help,
    _build_wa_lease_expiry,
    _build_wa_maintenance_update,
    _build_wa_payment_prompt,
    _build_wa_payment_receipt,
    _build_wa_rent_reminder,
    _build_wa_utility_bill,
    _build_wa_welcome_enrollment,
    _format_phone,
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


async def send_wa_utility_bill(
    session: AsyncSession, business_id: uuid.UUID, tenant: Tenant,
    unit_number: str, utility_type: str, consumed: float, amount: float,
    due_date: str | None = None,
) -> NotificationLog | None:
    """Tell a tenant about a utility invoice raised against their unit."""
    phone = tenant.whatsapp_phone
    if not phone:
        return None
    body = _build_wa_utility_bill(
        tenant.full_name, unit_number, utility_type, consumed, amount, due_date
    )
    return await send_notification(
        session=session, business_id=business_id, tenant_id=tenant.id,
        channel="whatsapp", recipient=phone,
        template_name="wa_utility_bill", body=body,
    )


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
