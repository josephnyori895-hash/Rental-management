"""
RENTAL OS — WhatsApp Inbound: Tenant Commands

Handles commands sent by registered tenants:
  BALANCE, PAY, RECEIPT, REPORT <msg>, RENEW, HELP, LATER

Dispatched from `app.notifications.inbound.parse_and_handle`.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Invoice, Payment
from app.models.business import Business
from app.models.lease import Lease, LeaseStatus
from app.models.property import Unit
from app.models.tenant import Tenant
from app.notifications.recipients import property_recipient_phones
from app.notifications.service import (
    _build_wa_balance,
    _build_wa_help,
    _build_wa_payment_receipt,
    _format_phone,
    send_notification,
    send_wa_balance,
    send_wa_help,
)
from app.payments.availability import (
    AIRTEL,
    BANK,
    CARD,
    MPESA,
    RAIL_LABELS,
    available_methods,
    enabled_methods,
    other_payment_hint,
)

logger = logging.getLogger(__name__)


async def _tenant_lease(session: AsyncSession, tenant: Tenant) -> Lease | None:
    """The tenant's current lease, including one still awaiting move-in money.

    WhatsApp enrollment reserves the unit with a pending lease and raises the
    deposit/first-rent invoices. PAY, BALANCE and RECEIPT used to look only at
    active leases, so a freshly enrolled tenant was told "no active lease" and
    could never pay the invoices the welcome message had just asked for.
    """
    return await session.scalar(
        select(Lease).where(
            Lease.tenant_id == tenant.id,
            Lease.status.in_([LeaseStatus.ACTIVE.value, LeaseStatus.PENDING.value]),
        ).order_by(Lease.created_at.desc()).limit(1)
    )


# ── Tenant commands ────────────────────────────────────────────────

async def _handle_tenant_command(
    session: AsyncSession, tenant: Tenant,
    text: str, text_lower: str, msg_id: str | None,
) -> dict | None:
    business_id = tenant.business_id

    if text == "BALANCE":
        return await _cmd_tenant_balance(session, tenant, business_id)

    elif text.startswith("PAY"):
        rail = text[3:].strip() or None
        return await _cmd_tenant_pay(session, tenant, business_id, rail)

    elif text == "RECEIPT":
        return await _cmd_tenant_receipt(session, tenant, business_id)

    elif text == "HELP":
        business = await session.get(Business, business_id)
        await send_wa_help(session, business_id, tenant)
        return {
            "to": tenant.whatsapp_phone,
            "message": _build_wa_help(set(enabled_methods(business))),
        }

    elif text == "RENEW":
        return await _cmd_tenant_renew(session, tenant, business_id)

    elif text == "CARD":
        return await _cmd_tenant_card(session, tenant, business_id)

    elif text == "AIRTEL":
        return await _cmd_tenant_airtel(session, tenant, business_id)

    elif text.startswith("DONE"):
        reference = text_lower[4:].strip()
        return await _cmd_tenant_done(session, tenant, business_id, reference)

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
    lease = await _tenant_lease(session, tenant)
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

    bus = await session.get(Business, business_id)
    bus_cfg = (bus.settings or {}).get("business", {}) if bus else {}
    payment_info = {
        "methods": enabled_methods(bus),
        "bank_name": bus_cfg.get("bank_name"),
        "bank_account": bus_cfg.get("bank_account"),
        "bank_account_name": bus_cfg.get("bank_account_name"),
    }
    await send_wa_balance(
        session, business_id, tenant, total_balance, due_date, payment_info
    )
    return {"to": tenant.whatsapp_phone, "message": _build_wa_balance(
        tenant.full_name, unit_number, total_balance, due_date, payment_info
    )}


_RAIL_ALIASES = {
    "mpesa": MPESA,
    "m-pesa": MPESA,
    "m pesa": MPESA,
    "airtel": AIRTEL,
    "airtel money": AIRTEL,
    "card": CARD,
    "flutterwave": CARD,
    "bank": BANK,
    "transfer": BANK,
}


def _pay_menu(options: list[str]) -> str:
    lines = ["💳 How would you like to pay?", ""]
    for method in options:
        lines.append(f"Reply PAY {method.upper()} — {RAIL_LABELS[method]}")
    return "\n".join(lines)


async def _cmd_tenant_pay(
    session: AsyncSession, tenant: Tenant, business_id: uuid.UUID,
    rail: str | None = None,
) -> dict:
    """Send an STK push for the oldest unpaid invoice, linked to that invoice.

    The push must be raised against an **invoice id** (`stk_push`), never as a
    bare phone + amount (`stk_push_direct`). Daraja echoes back only the
    CheckoutRequestID, and the callback finds the invoice through the id stored
    on it; a direct push left the payment unattributable, so the money moved at
    Safaricom and the ledger never heard about it.

    One invoice per PAY keeps the prompt readable and the callback unambiguous.
    Further invoices are paid with another PAY once the first clears.
    """
    lease = await _tenant_lease(session, tenant)
    if not lease:
        return {"to": tenant.whatsapp_phone, "message": "No active lease found. Contact your property manager."}

    invoices = (await session.scalars(
        select(Invoice).where(
            Invoice.lease_id == lease.id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
            Invoice.balance > 0,
        ).order_by(Invoice.due_date.asc(), Invoice.created_at.asc())
    )).all()
    total = sum(float(inv.balance) for inv in invoices)
    if total <= 0:
        return {"to": tenant.whatsapp_phone, "message": "You have no outstanding balance. You're all paid up! ✅"}

    target = invoices[0]
    amount = float(target.balance)

    bus = await session.get(Business, business_id)
    bus_cfg = (bus.settings or {}).get("business", {}) if bus else {}
    options = enabled_methods(bus)

    if rail:
        requested = _RAIL_ALIASES.get(rail.lower().strip())
        if requested not in options:
            if not options:
                return {"to": tenant.whatsapp_phone, "message": (
                    "No payment methods are enabled for this property yet. "
                    "Contact your property manager."
                )}
            return {"to": tenant.whatsapp_phone, "message": (
                "That payment option is not enabled for this property.\n\n"
                + _pay_menu(options)
            )}
        options = [requested]

    if not options:
        selected = bus_cfg.get("payment_methods") or [
            bus_cfg.get("payment_method", "mpesa")
        ]
        if len(selected) == 1:
            label = RAIL_LABELS.get(selected[0], selected[0])
            return {"to": tenant.whatsapp_phone, "message": (
                f"{label} is not enabled for this property yet. "
                "Contact your property manager."
            )}
        return {"to": tenant.whatsapp_phone, "message": (
            "None of the selected payment methods are available on this "
            "property yet. Contact your property manager."
        )}

    # Several rails enabled: let the tenant choose, then route by keyword.
    if len(options) > 1 and rail is None:
        return {"to": tenant.whatsapp_phone, "message": _pay_menu(options)}

    payment_method = options[0]

    # Delegate to that rail's command so the tenant gets the same message
    # whichever keyword they used.
    if payment_method == "card":
        return await _cmd_tenant_card(session, tenant, business_id)
    if payment_method == "airtel":
        return await _cmd_tenant_airtel(session, tenant, business_id)

    u = await session.get(Unit, lease.unit_id)
    unit_no = u.unit_number if u else "—"

    # ── Bank Payment Flow ─────────────────────────────────────────
    if payment_method == "bank":
        bank_name = bus_cfg.get("bank_name", "Equity Bank")
        bank_acc = bus_cfg.get("bank_account", "—")
        acc_name = bus_cfg.get("bank_account_name", bus.name if bus else "Hostel")
        msg = (
            f"🏦 BANK PAYMENT — KES {total:,.0f} for {unit_no}\n\n"
            f"Please transfer to our Bank Account:\n"
            f"  Bank: {bank_name}\n"
            f"  Account: {bank_acc}\n"
            f"  Name: {acc_name}\n\n"
            f"Reply DONE <transaction_reference> once complete."
        )
        return {"to": tenant.whatsapp_phone, "message": msg}

    # Never fall back to a made-up Paybill shortcode when the landlord has not
    # set M-Pesa up: point the tenant at the rails that do work.
    methods = available_methods(bus)
    if "mpesa" not in methods:
        return {"to": tenant.whatsapp_phone, "message": (
            "M-Pesa is not set up for this property yet.\n"
            + other_payment_hint(methods)
        )}

    # Determine M-Pesa number
    mpesa_phone = _format_phone(tenant.mpesa_phone or tenant.whatsapp_phone or tenant.phone or "")
    if not mpesa_phone:
        return {"to": tenant.whatsapp_phone, "message": "No M-Pesa number on file. Contact your property manager."}

    # ── Daraja STK push, raised against the invoice ───────────────
    if settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET:
        try:
            from app.payments import service as pay_svc
            await pay_svc.stk_push(session, str(target.id), mpesa_phone)
            remaining = total - amount
            msg = (
                f"💳 STK Push sent!\n"
                f"Invoice: {target.invoice_number or str(target.id)[:8]}\n"
                f"Amount: KES {amount:,.0f}\n"
                f"Phone: {mpesa_phone}\n"
                f"Enter your M-Pesa PIN to complete payment."
            )
            if remaining > 0:
                msg += (
                    f"\n\nKES {remaining:,.0f} remains on your other invoices — "
                    f"reply PAY again once this clears."
                )
            msg += "\n\nReply RECEIPT after paying to get your receipt."
            return {"to": tenant.whatsapp_phone, "message": msg}
        except Exception:
            # Fall through to Paybill instructions, but say why: a Daraja
            # outage and a missing credential look identical from the
            # tenant's side, and only the log can tell them apart.
            logger.warning(
                "STK push failed for invoice %s; falling back to Paybill instructions",
                target.id, exc_info=True,
            )

    # ── Fallback: Paybill instructions ───────────────────────────
    paybill = getattr(settings, "MPESA_SHORTCODE", "") or (
        bus.mpesa_shortcode if bus else ""
    )
    msg = (
        f"💰 PAY KES {amount:,.0f} for {unit_no}\n\n"
        f"Via M-Pesa Paybill:\n"
        f"  1. Go to M-Pesa → Paybill\n"
        f"  2. Business No: {paybill or '—'}\n"
        f"  3. Account: {target.invoice_number or unit_no}\n"
        f"  4. Amount: {amount:,.0f}\n"
        f"  5. Enter PIN & confirm\n\n"
        f"Reply RECEIPT after paying."
    )
    return {"to": tenant.whatsapp_phone, "message": msg}


async def _cmd_tenant_receipt(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID) -> dict:
    lease = await _tenant_lease(session, tenant)
    if not lease:
        return {"to": tenant.whatsapp_phone, "message": "No active lease found."}

    payment = await session.scalar(
        select(Payment).where(Payment.lease_id == lease.id)
        .order_by(Payment.paid_at.desc()).limit(1)
    )
    if not payment:
        return {"to": tenant.whatsapp_phone, "message": "No recent payments found."}

    u = await session.get(Unit, lease.unit_id)
    unit_no = u.unit_number if u else "—"
    # An Invoice is not a Payment: this used to read `reference` off an invoice
    # and pass `payment=None` to the WhatsApp sender, so RECEIPT errored
    # instead of replying. The webhook sends the returned message itself.
    body = _build_wa_payment_receipt(tenant.full_name, unit_no, float(payment.amount), payment.reference, None)
    return {"to": tenant.whatsapp_phone, "message": body}


async def _cmd_tenant_report(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID, issue: str) -> dict:
    """Create a maintenance ticket and notify caretaker."""
    from app.models.maintenance import MaintenanceTicket
    from app.models.property import Property as PropertyModel

    lease = await _tenant_lease(session, tenant)
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

    caretaker_phones = await property_recipient_phones(session, business_id, prop_id)
    if caretaker_phones:
        from app.notifications.service import notify_caretaker_ticket
        for phone in caretaker_phones:
            await notify_caretaker_ticket(session, business_id, phone, tenant.full_name, unit_no, issue, str(ticket.id)[:8])

    return {"to": tenant.whatsapp_phone, "message": f"✅ Ticket #{str(ticket.id)[:8]} created. We'll notify you when it's resolved."}


async def _cmd_tenant_renew(session: AsyncSession, tenant: Tenant, business_id: uuid.UUID) -> dict:
    lease = await _tenant_lease(session, tenant)
    if not lease:
        return {"to": tenant.whatsapp_phone, "message": "No active lease to renew."}

    u = await session.get(Unit, lease.unit_id)
    unit_no = u.unit_number if u else "—"

    # Notify whoever runs this property — a business can have many caretakers,
    # each on a different building.
    caretaker_phones = await property_recipient_phones(
        session, business_id, u.property_id if u else None
    )
    for caretaker_phone in caretaker_phones:
        await send_notification(
            session=session, business_id=business_id, tenant_id=tenant.id,
            channel="whatsapp", recipient=caretaker_phone,
            template_name="caretaker_renewal_request",
            body=f"📋 RENEWAL REQUEST — {tenant.full_name} ({unit_no})\nTenant wants to renew their lease.",
        )

    return {"to": tenant.whatsapp_phone, "message": f"Your renewal request for {unit_no} has been received. The property manager will follow up."}


# ── Other payment rails ─────────────────────────────────────────

async def _oldest_unpaid(session: AsyncSession, tenant: Tenant):
    """The tenant's lease and the oldest invoice still owing, if any."""
    lease = await _tenant_lease(session, tenant)
    if lease is None:
        return None, None
    invoice = await session.scalar(
        select(Invoice).where(
            Invoice.lease_id == lease.id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
            Invoice.balance > 0,
        ).order_by(Invoice.due_date.asc(), Invoice.created_at.asc()).limit(1)
    )
    return lease, invoice


async def _cmd_tenant_card(
    session: AsyncSession, tenant: Tenant, business_id: uuid.UUID
) -> dict:
    """Send a hosted checkout link (card, bank transfer or mobile money)."""
    from app.payments import flutterwave

    business = await session.get(Business, business_id)
    methods = set(enabled_methods(business))
    if "card" not in methods:
        return {"to": tenant.whatsapp_phone, "message": (
            "Card and online bank payments are not enabled for this property yet.\n"
            + other_payment_hint(methods)
        )}

    lease, invoice = await _oldest_unpaid(session, tenant)
    if lease is None:
        return {"to": tenant.whatsapp_phone, "message": "No lease found. Contact your property manager."}
    if invoice is None:
        return {"to": tenant.whatsapp_phone, "message": "You have no outstanding balance. ✅"}

    try:
        checkout = await flutterwave.create_checkout(session, str(invoice.id))
    except RuntimeError:
        logger.warning("Flutterwave checkout unavailable", exc_info=True)
        return {"to": tenant.whatsapp_phone, "message": (
            "Card/bank payment is not available right now. Reply PAY to use M-Pesa."
        )}
    except Exception:
        logger.warning("Flutterwave checkout failed", exc_info=True)
        return {"to": tenant.whatsapp_phone, "message": (
            "We couldn't create a card/bank link. Reply PAY to use M-Pesa."
        )}

    unit = await session.get(Unit, lease.unit_id)
    unit_no = unit.unit_number if unit else "—"
    return {"to": tenant.whatsapp_phone, "message": (
        f"💳 Pay KES {float(invoice.balance):,.0f} for {unit_no} by card or bank:\n"
        f"{checkout['checkout_url']}\n\n"
        "Reply RECEIPT once paid."
    )}


async def _cmd_tenant_airtel(
    session: AsyncSession, tenant: Tenant, business_id: uuid.UUID
) -> dict:
    """Prompt the tenant's Airtel Money wallet for the oldest unpaid invoice."""
    from app.payments import airtel

    business = await session.get(Business, business_id)
    methods = set(enabled_methods(business))
    if "airtel" not in methods:
        return {"to": tenant.whatsapp_phone, "message": (
            "Airtel Money is not enabled for this property yet.\n"
            + other_payment_hint(methods)
        )}

    lease, invoice = await _oldest_unpaid(session, tenant)
    if lease is None:
        return {"to": tenant.whatsapp_phone, "message": "No lease found. Contact your property manager."}
    if invoice is None:
        return {"to": tenant.whatsapp_phone, "message": "You have no outstanding balance. ✅"}

    phone = _format_phone(
        tenant.mpesa_phone or tenant.whatsapp_phone or tenant.phone or ""
    )
    try:
        await airtel.collect(session, str(invoice.id), phone)
    except RuntimeError:
        logger.warning("Airtel Money unavailable", exc_info=True)
        return {"to": tenant.whatsapp_phone, "message": (
            "Airtel Money is not available right now. Reply PAY to use M-Pesa."
        )}
    except Exception:
        logger.warning("Airtel collection failed", exc_info=True)
        return {"to": tenant.whatsapp_phone, "message": (
            "We couldn't reach Airtel Money. Reply PAY to use M-Pesa."
        )}

    return {"to": tenant.whatsapp_phone, "message": (
        f"📱 Airtel Money prompt sent for KES {float(invoice.balance):,.0f}.\n"
        "Enter your Airtel Money PIN to complete payment."
    )}


async def _cmd_tenant_done(
    session: AsyncSession, tenant: Tenant, business_id: uuid.UUID, reference: str
) -> dict:
    """Record a self-declared bank transfer for the owner to confirm.

    This must never mark an invoice paid: the money has not been verified. It
    becomes a pending payment in the reconciliation queue, and the caretaker /
    owner is notified to check the bank.
    """
    if not reference:
        return {"to": tenant.whatsapp_phone, "message": (
            "Send the bank reference: DONE <transaction_reference>"
        )}

    existing = await session.scalar(
        select(Payment).where(
            Payment.business_id == business_id,
            Payment.reference == reference,
        ).limit(1)
    )
    if existing is not None:
        return {"to": tenant.whatsapp_phone, "message": (
            f"Reference {reference} was already recorded. The office will confirm it."
        )}

    lease = await _tenant_lease(session, tenant)
    if lease is None:
        return {"to": tenant.whatsapp_phone, "message": "No lease found. Contact your property manager."}

    outstanding = await session.scalar(
        select(func.coalesce(func.sum(Invoice.balance), 0)).where(
            Invoice.lease_id == lease.id,
            Invoice.status.in_(["pending", "partial", "overdue"]),
        )
    )
    total = float(outstanding or 0)
    if total <= 0:
        return {"to": tenant.whatsapp_phone, "message": (
            "You have no outstanding balance — nothing to confirm. ✅"
        )}

    session.add(Payment(
        business_id=business_id,
        invoice_id=None,
        lease_id=lease.id,
        tenant_id=tenant.id,
        amount=Decimal(str(total)),
        method="bank",
        reference=reference,
        status="pending",
    ))
    await session.commit()

    unit = await session.get(Unit, lease.unit_id)
    unit_no = unit.unit_number if unit else "—"
    phones = await property_recipient_phones(
        session, business_id, unit.property_id if unit else None
    )
    for phone in phones:
        await send_notification(
            session=session, business_id=business_id, tenant_id=tenant.id,
            channel="whatsapp", recipient=phone,
            template_name="bank_transfer_claim",
            body=(
                f"🏦 BANK PAYMENT CLAIM — {tenant.full_name} ({unit_no})\n"
                f"Reference: {reference}\n"
                f"Amount: KES {total:,.0f}\n"
                "Confirm it in the reconciliation queue."
            ),
        )

    return {"to": tenant.whatsapp_phone, "message": (
        f"✅ Bank reference {reference} recorded for KES {total:,.0f}.\n"
        "The office will confirm and receipt it."
    )}
