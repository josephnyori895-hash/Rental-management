"""
RENTAL OS — WhatsApp Inbound: Owner / Caretaker Commands

Handles commands sent by registered users (owners and caretakers):
  STATUS, COLLECTIONS, ADD <phone> <unit> <name>, ADD CARETAKER,
  FIXED, METER <unit> <reading>, HELP

A caretaker's meter reading is real: it is priced against the property
tariff and, where the unit is occupied, the tenant is invoiced.

Dispatched from `app.notifications.inbound.parse_and_handle`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.service import auto_post_invoice
from app.billing.utilities import (
    DEFAULT_UTILITY_DUE_DAYS,
    income_code_for,
    MeterCommand,
    ReadingError,
    compute_amount,
    compute_consumption,
    parse_meter_command,
    resolve_rate,
)
from app.models.billing import Invoice, InvoiceStatus
from app.models.business import Business, User, UserRole
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, UnitStatus
from app.models.tenant import Tenant
from app.models.utilities import MeterReading, MeterSource, UtilityRate
from app.notifications.service import _format_phone

logger = logging.getLogger(__name__)


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
            msg = "Commands:\nADD 2547XXXXXX UNIT# Name — add tenant\nADD CARETAKER 2547XXXXXX Name — add caretaker\nSTATUS — portfolio overview\nCOLLECTIONS — collection rate\nWATER <unit> <reading> — log a meter reading\nHELP"
        else:
            msg = "Commands:\nADD 2547XXXXXX UNIT# Name — add tenant\nFIXED — mark task done\nWATER <unit> <reading> — log a meter reading\nHELP"
        return {"to": sender, "message": msg}

    # Meter readings from the floor: "1204", "WATER 1204", "METER A1 348"
    reading_cmd = parse_meter_command(text_lower)
    if reading_cmd is not None:
        return await _cmd_record_meter_reading(session, user, reading_cmd, sender)

    return {"to": sender, "message": "Unknown command. Reply HELP."}


# ── Meter readings ────────────────────────────────────────────────

async def _cmd_record_meter_reading(
    session: AsyncSession, user: User, cmd: MeterCommand, sender: str,
) -> dict:
    """Record a meter reading and bill it when the unit has an active lease."""
    business_id = user.business_id

    properties = (await session.execute(
        select(Property).where(
            Property.business_id == business_id,
            Property.is_deleted.is_(False),
        )
    )).scalars().all()
    if not properties:
        return {"to": sender, "message": "No property set up for this business yet."}

    # A caretaker only reads meters on the properties they manage; an owner
    # reads across the whole portfolio.
    scope = [p for p in properties if p.manager_id == user.id] or list(properties)

    unit: Unit | None = None
    if cmd.unit_ref:
        unit = await session.scalar(
            select(Unit).where(
                Unit.business_id == business_id,
                Unit.property_id.in_([p.id for p in scope]),
                Unit.is_deleted.is_(False),
                Unit.unit_number.ilike(cmd.unit_ref),
            ).limit(1)
        )
        if unit is None:
            return {"to": sender, "message": (
                f"Unit '{cmd.unit_ref}' not found. Check the unit number and try again, "
                f"or reply HELP."
            )}
        prop = next(p for p in scope if p.id == unit.property_id)
    elif len(scope) == 1:
        prop = scope[0]
    else:
        return {"to": sender, "message": "Which unit is this reading for? Reply: METER <unit> <reading>"}

    rates = (await session.execute(
        select(UtilityRate).where(
            UtilityRate.business_id == business_id,
            UtilityRate.property_id == prop.id,
            UtilityRate.is_active.is_(True),
        )
    )).scalars().all()

    # A bare number is ambiguous once more than one utility is configured, so
    # ask rather than guess which tariff to apply.
    utility_type = cmd.utility_type
    if utility_type is None:
        configured = sorted({r.utility_type for r in rates})
        if len(configured) == 1:
            utility_type = configured[0]
        else:
            options = ", ".join(t.upper() for t in configured) or "WATER, ELEC"
            prefix = f"{cmd.unit_ref} " if cmd.unit_ref else ""
            return {"to": sender, "message": (
                f"Which utility is this reading for?\n"
                f"Reply e.g. WATER {prefix}{cmd.reading:g}\n"
                f"Configured: {options}"
            )}

    q = select(MeterReading).where(
        MeterReading.business_id == business_id,
        MeterReading.property_id == prop.id,
        MeterReading.utility_type == utility_type,
    )
    q = q.where(MeterReading.unit_id == unit.id) if unit else q.where(MeterReading.unit_id.is_(None))
    last = await session.scalar(
        q.order_by(MeterReading.reading_date.desc(), MeterReading.created_at.desc()).limit(1)
    )
    previous = last.current_reading if last else None

    try:
        consumed = compute_consumption(previous, cmd.reading)
    except ReadingError:
        return {"to": sender, "message": (
            f"⚠️ {cmd.reading:g} is lower than the last reading "
            f"({previous:g} on {last.reading_date}).\n"
            "If the meter was replaced or reset, ask the owner to correct it on the dashboard."
        )}

    rate = resolve_rate(rates, utility_type, unit.id if unit else None)
    rate_per_unit = rate.rate_per_unit if rate else Decimal("0")
    fixed_charge = rate.fixed_charge if rate else Decimal("0")
    amount = compute_amount(consumed, rate_per_unit, fixed_charge)

    where = f"Unit {unit.unit_number}" if unit else f"{prop.name} (shared meter)"
    label = utility_type.replace("_", " ").title()

    reading = MeterReading(
        business_id=business_id,
        property_id=prop.id,
        unit_id=unit.id if unit else None,
        utility_type=utility_type,
        reading_date=date.today(),
        previous_reading=previous,
        current_reading=cmd.reading,
        units_consumed=consumed,
        rate_per_unit=rate_per_unit,
        fixed_charge=fixed_charge,
        amount=amount if previous is not None else Decimal("0"),
        source=MeterSource.WHATSAPP.value,
        recorded_by=user.id,
    )
    session.add(reading)
    await session.flush()

    if previous is None:
        await session.commit()
        return {"to": sender, "message": (
            f"✅ Baseline for {where} — {label} recorded at {cmd.reading:g}.\n"
            "The next reading will compute usage."
        )}

    if amount <= 0:
        await session.commit()
        return {"to": sender, "message": (
            f"✅ {where} — {label}: {consumed:g} units consumed.\n"
            "No tariff is set for this property, so nothing was billed."
        )}

    if unit is None:
        await session.commit()
        return {"to": sender, "message": (
            f"✅ {where} — {label}: {consumed:g} units, KES {float(amount):,.2f}.\n"
            "Shared reading saved — the owner splits it across units from the dashboard."
        )}

    lease = await session.scalar(
        select(Lease).where(
            Lease.unit_id == unit.id,
            Lease.status == LeaseStatus.ACTIVE.value,
        ).limit(1)
    )

    invoice: Invoice | None = None
    if lease is not None:
        due_date = date.today() + timedelta(days=DEFAULT_UTILITY_DUE_DAYS)
        invoice = Invoice(
            business_id=business_id,
            lease_id=lease.id,
            tenant_id=lease.tenant_id,
            unit_id=unit.id,
            property_id=prop.id,
            invoice_type=utility_type,
            amount=amount,
            paid_amount=Decimal("0"),
            balance=amount,
            status=InvoiceStatus.PENDING.value,
            due_date=due_date,
            description=f"{label} — {date.today().isoformat()}",
        )
        session.add(invoice)
        await session.flush()
        reading.invoice_id = invoice.id
        try:
            await auto_post_invoice(
                session, invoice, income_code=income_code_for(utility_type)
            )
        except Exception:
            # Never fail a reading because the ledger posting did — but the
            # caretaker's reading and the ledger must not silently diverge.
            logger.warning(
                "Ledger posting failed for utility invoice %s (reading %s)",
                invoice.id, reading.id, exc_info=True,
            )

    await session.commit()

    lines = [
        f"✅ {where} — {label}",
        f"Reading {cmd.reading:g} (was {previous:g})",
        f"Consumed {consumed:g}",
        f"Charge KES {float(amount):,.2f}",
    ]
    if invoice is not None:
        lines.append("Tenant invoiced.")
        tenant = await session.get(Tenant, invoice.tenant_id)
        if tenant is not None:
            from app.notifications.service import send_wa_utility_bill
            try:
                await send_wa_utility_bill(
                    session, business_id, tenant, unit.unit_number,
                    utility_type, float(consumed), float(amount), str(invoice.due_date),
                )
            except Exception:
                pass  # The reading is already saved; a failed notice is not fatal
    lines.append("Reply HELP for commands.")
    return {"to": sender, "message": "\n".join(lines)}


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
