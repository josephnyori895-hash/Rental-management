"""
RENTAL OS — WhatsApp Inbound Command Handler

Receives messages from Africa's Talking webhook, parses them as commands,
and routes to the right handler.

Commands:
  Tenant:   BALANCE, PAY, RECEIPT, REPORT <msg>, RENEW, HELP
  Owner:    STATUS, COLLECTIONS, ADD <phone> <unit> <name>
  Caretaker: ADD <phone> <unit> <name>, FIXED, DONE, <meter reading>

Architecture:
  Inbound webhook → identify sender → parse command → execute → reply
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Invoice, InvoiceStatus
from app.models.business import Business, User, UserRole
from app.models.lease import Lease, LeaseStatus
from app.models.property import Unit, UnitStatus
from app.models.tenant import Tenant
from app.notifications.service import (
    _build_wa_balance,
    _build_wa_help,
    _build_wa_payment_receipt,
    _build_wa_rent_reminder,
    _build_wa_welcome_enrollment,
    _format_phone,
    notify_caretaker_move_in,
    notify_caretaker_payment,
    send_notification,
    send_wa_balance,
    send_wa_help,
    send_wa_payment_receipt,
)


async def _find_caretaker_phone(session: AsyncSession, business_id: uuid.UUID) -> str | None:
    """Find the first active caretaker's WhatsApp phone for this business."""
    from sqlalchemy import select
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


async def parse_and_handle(
    session: AsyncSession,
    from_number: str,
    message_text: str,
    message_id: str | None = None,
) -> dict:
    """
    Entry point for incoming WhatsApp messages.
    
    Returns reply payload: {'to': ..., 'message': ...} or None.
    """
    # Normalize sender phone
    sender = _format_phone(from_number)
    text = message_text.strip().upper()
    text_lower = message_text.strip()

    # ── Identify sender ──────────────────────────────────────────
    # Check if sender is a tenant
    tenant = await session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == sender, Tenant.is_deleted.is_(False)).limit(1)
    )

    # Check if sender is a user (owner/caretaker)
    user = await session.scalar(
        select(User).where(User.phone == sender, User.is_active.is_(True)).limit(1)
    )

    if tenant:
        return await _handle_tenant_command(session, tenant, text, text_lower, message_id)
    elif user:
        return await _handle_user_command(session, user, text, text_lower, sender, message_id)
    else:
        # Unknown sender — reply with info
        return {
            "to": sender,
            "message": "Welcome to Rental OS. This number is not registered. Please contact your property manager.",
        }


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
        from app.models.property import Unit
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

    from app.models.property import Unit as UnitModel
    u = await session.get(UnitModel, lease.unit_id)
    unit_no = u.unit_number if u else "—"

    # Check business payment method configuration (M-Pesa vs Bank)
    from app.models.business import Business
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
    from app.core.config import settings
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
        except Exception as e:
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

    from app.models.property import Unit
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

    # Extend by 1 year from end date
    from datetime import timedelta
    from app.models.property import Unit
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


# ── User (owner/caretaker) commands ────────────────────────────────

async def _handle_user_command(
    session: AsyncSession, user: User,
    text: str, text_lower: str, sender: str, msg_id: str | None,
) -> dict | None:
    business_id = user.business_id

    if text.startswith("ADD ") and text_lower.startswith("add caretaker"):
        if user.role != UserRole.OWNER.value:
            return {"to": sender, "message": "Only the owner can add caretakers."}
        return await _cmd_owner_add_caretaker(session, user, business_id, text_lower, sender)

    elif text.startswith("ADD "):
        return await _cmd_user_add(session, user, business_id, text_lower, sender)

    elif text == "STATUS":
        if user.role != UserRole.OWNER.value:
            return {"to": sender, "message": "Only the owner can view portfolio status."}
        return await _cmd_user_status(session, user, business_id)

    elif text == "COLLECTIONS":
        if user.role != UserRole.OWNER.value:
            return {"to": sender, "message": "Only the owner can view collections."}
        return await _cmd_user_collections(session, user, business_id)

    elif text == "FIXED":
        return {"to": sender, "message": "Marked as resolved. Photo updates coming in v2."}

    elif text.upper() == "HELP":
        if user.role == UserRole.OWNER.value:
            msg = "Commands:\nADD 2547XXXXXX UNIT# Name — add tenant\nADD CARETAKER 2547XXXXXX Name — add caretaker\nSTATUS — portfolio overview\nCOLLECTIONS — collection rate\nHELP"
        else:
            msg = "Commands:\nADD 2547XXXXXX UNIT# Name — add tenant\nFIXED — mark task done\nHELP"
        return {"to": sender, "message": msg}

    # Check if this is a meter reading (simple 3-4 digit number)
    if re.match(r"^\d{3,6}$", text) and user.role == UserRole.AGENT.value:
        return {"to": sender, "message": f"Meter reading {text} logged. (Full integration in v2)"}

    return {"to": sender, "message": f"Unknown command. Reply HELP."}


async def _cmd_owner_add_caretaker(
    session: AsyncSession, user: User, business_id: uuid.UUID,
    text_lower: str, sender: str,
) -> dict:
    """ADD CARETAKER 2547XXXXXX John Kamau"""
    parts = text_lower.split()
    if len(parts) < 4:
        return {"to": sender, "message": "Usage: ADD CARETAKER 2547XXXXXXXX Full Name"}

    phone = _format_phone(parts[2])
    name = " ".join(parts[3:])

    if not phone.startswith("254") or len(phone) < 12:
        return {"to": sender, "message": "Invalid phone. Use 2547XXXXXXXX format."}

    # Check if already exists
    existing = await session.scalar(
        select(User).where(User.business_id == business_id, User.phone == phone).limit(1)
    )
    if existing:
        return {"to": sender, "message": f"Caretaker with phone {phone} already exists."}

    # Create user with AGENT role — bcrypt hash, same as auth system
    from app.core.security import hash_password
    from secrets import randbelow
    temp_pin = f"{randbelow(10000):04d}"
    caretaker = User(
        business_id=business_id,
        email=f"caretaker_{phone}@rentalos.local",
        password_hash=hash_password(temp_pin),  # bcrypt, not SHA256
        full_name=name.title(),
        phone=phone,
        role=UserRole.AGENT.value,
        is_active=True,
    )
    session.add(caretaker)
    await session.commit()

    # Welcome the caretaker on WhatsApp
    from app.notifications.service import send_wa_to_caretaker
    await send_wa_to_caretaker(
        session, business_id, phone,
        f"👋 Hi {name.title()}, you're now a caretaker for {user.full_name}'s property.\n\n"
        f"To add a tenant, text:\nADD 2547XXXXXX UNIT# Tenant Name\n\n"
        f"Reply HELP for all commands.",
        "caretaker_welcome",
    )

    return {"to": sender, "message": f"✅ Caretaker {name.title()} ({phone}) added and sent welcome."}


async def _cmd_user_add(
    session: AsyncSession, user: User, business_id: uuid.UUID,
    text_lower: str, sender: str,
) -> dict:
    """ADD 2547XXXXXX UNIT4 James Kariuki"""
    parts = text_lower.split()
    if len(parts) < 4:
        return {"to": sender, "message": "Usage: ADD 2547XXXXXXXX UNIT# Full Name"}

    phone = _format_phone(parts[1])
    unit_ref = parts[2].upper()
    name = " ".join(parts[3:])

    # Validate phone
    if not phone.startswith("254") or len(phone) < 12:
        return {"to": sender, "message": "Invalid phone. Use 2547XXXXXXXX format."}

    # Check if tenant already exists
    existing = await session.scalar(
        select(Tenant).where(Tenant.business_id == business_id, Tenant.whatsapp_phone == phone, Tenant.is_deleted.is_(False)).limit(1)
    )
    if existing:
        return {"to": sender, "message": f"Tenant with phone {phone} is already registered."}

    # Find unit
    from app.models.property import Property
    unit = await session.scalar(
        select(Unit).join(Property, Unit.property_id == Property.id).where(
            Property.business_id == business_id,
            Unit.unit_number.ilike(unit_ref),
            Unit.is_deleted.is_(False),
        ).limit(1)
    )
    if not unit:
        return {"to": sender, "message": f"Unit '{unit_ref}' not found."}

    if unit.status == UnitStatus.OCCUPIED.value:
        return {"to": sender, "message": f"Unit {unit_ref} is already occupied."}

    # Check enrollment settings
    business = await session.get(Business, business_id)
    enroll = (business.settings or {}).get("enrollment", {})
    require_deposit = enroll.get("require_deposit", True)
    deposit_type = enroll.get("deposit_type", "one_month")
    require_first_rent = enroll.get("require_first_rent", True)
    grace_hours = enroll.get("grace_hours", 24)

    # Create tenant record (pending enrollment)
    tenant = Tenant(
        business_id=business_id,
        full_name=name.title(),
        phone=phone,
        whatsapp_phone=phone,  # Same number for WhatsApp
        mpesa_phone=phone,
        notes=f"Enrolled via WhatsApp by {user.full_name} ({user.role})",
    )
    session.add(tenant)
    await session.flush()

    # Mark unit as reserved
    unit.status = UnitStatus.RESERVED.value

    # Create lease in pending state
    lease = Lease(
        business_id=business_id,
        tenant_id=tenant.id,
        unit_id=unit.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        monthly_rent=unit.monthly_rent,
        deposit_amount=unit.monthly_rent if require_deposit else 0,
        deposit_paid=False,
        status=LeaseStatus.PENDING.value,
    )
    session.add(lease)

    # Determine deposit amount
    deposit_amount = None
    if require_deposit:
        if deposit_type == "one_month":
            deposit_amount = float(unit.monthly_rent)
        elif deposit_type == "two_months":
            deposit_amount = float(unit.monthly_rent) * 2
        elif deposit_type == "fixed":
            deposit_amount = enroll.get("deposit_fixed_amount", float(unit.monthly_rent))
        else:
            deposit_amount = float(unit.monthly_rent)

    rent_only = not require_deposit or not require_first_rent
    total = float(unit.monthly_rent) + (deposit_amount or 0) if not rent_only else float(unit.monthly_rent)

    await session.commit()

    # Send WhatsApp welcome + payment prompt
    from app.models.property import Property as PropertyModel
    prop = await session.get(PropertyModel, unit.property_id)
    prop_name = prop.name if prop else "Property"

    from app.notifications.service import send_wa_enrollment_prompt
    await send_wa_enrollment_prompt(
        session, business_id, tenant, prop_name, unit.unit_number,
        float(unit.monthly_rent), deposit_amount, rent_only,
    )

    return {"to": sender, "message": f"✅ {name} added to {unit_ref}. Welcome sent. Awaiting payment."}


async def _cmd_user_status(session: AsyncSession, user: User, business_id: uuid.UUID) -> dict:
    """Owner-only: portfolio overview."""
    from app.models.property import Property

    total_units = await session.scalar(
        select(func.count(Unit.id)).where(
            Unit.is_deleted.is_(False),
            Unit.property_id.in_(
                select(Property.id).where(Property.business_id == business_id, Property.is_deleted.is_(False))
            ),
        )
    ) or 0

    occupied = await session.scalar(
        select(func.count(Unit.id)).where(
            Unit.status == UnitStatus.OCCUPIED.value,
            Unit.is_deleted.is_(False),
            Unit.property_id.in_(
                select(Property.id).where(Property.business_id == business_id, Property.is_deleted.is_(False))
            ),
        )
    ) or 0

    vacant = total_units - occupied

    # Outstanding invoices
    outstanding = await session.scalar(
        select(func.coalesce(func.sum(Invoice.balance), 0)).where(
            Invoice.business_id == business_id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
        )
    ) or 0

    msg = (
        f"📊 PORTFOLIO STATUS\n"
        f"Units: {occupied} occupied / {vacant} vacant / {total_units} total\n"
        f"Occupancy: {round(occupied / total_units * 100) if total_units else 0}%\n"
        f"Outstanding: KES {float(outstanding):,.0f}\n"
        f"Reply COLLECTIONS for collection rate."
    )
    return {"to": user.phone, "message": msg}


async def _cmd_user_collections(session: AsyncSession, user: User, business_id: uuid.UUID) -> dict:
    """Owner-only: collection rate for current month."""
    today = date.today()
    month_start = today.replace(day=1)

    collected = await session.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
            Invoice.business_id == business_id,
            Invoice.period_start >= month_start,
            Invoice.status == InvoiceStatus.PAID.value,
        )
    ) or 0

    expected = await session.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.business_id == business_id,
            Invoice.period_start >= month_start,
        )
    ) or 0

    rate = round(float(collected) / float(expected) * 100, 1) if float(expected) > 0 else 0

    msg = (
        f"💰 COLLECTIONS — {today.strftime('%B %Y')}\n"
        f"Collected: KES {float(collected):,.0f}\n"
        f"Expected: KES {float(expected):,.0f}\n"
        f"Rate: {rate}%\n"
    )
    if rate < 60:
        msg += "⚠️ Below target. Consider reminders."
    elif rate > 90:
        msg += "✅ Great month!"
    return {"to": user.phone, "message": msg}
