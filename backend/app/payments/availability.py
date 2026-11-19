"""
Which payment rails this landlord/deployment can actually accept.

The app must never advertise a method it cannot process. M-Pesa needs Daraja
credentials (or a registered Paybill shortcode on the business); Airtel and
card/bank need platform credentials. A bank-transfer claim is always possible,
because the tenant moves the money themselves and the owner confirms it.
"""

from __future__ import annotations

from app.core.config import settings
from app.models.business import Business

MPESA = "mpesa"
AIRTEL = "airtel"
CARD = "card"
BANK = "bank"

RAIL_LABELS = {
    MPESA: "M-Pesa",
    AIRTEL: "Airtel Money",
    CARD: "Card or online bank",
    BANK: "Bank transfer",
}

# What an owner/operator must configure for each rail to actually work.
RAIL_REQUIREMENTS = {
    MPESA: "add Daraja credentials or a Paybill number",
    AIRTEL: "set AIRTEL_CLIENT_ID and AIRTEL_CLIENT_SECRET",
    CARD: "set FLUTTERWAVE_SECRET_KEY",
    BANK: "no setup needed",
}


def available_methods(
    business: Business | None = None, paybill: str | None = None
) -> set[str]:
    """Rails this deployment can process, optionally counting an unsaved Paybill.

    The `paybill` argument lets settings validation accept a number the owner is
    entering in the same request, before it has been written to the business.
    """
    methods = {BANK}

    # STK needs Daraja credentials; a Paybill only needs its shortcode to be
    # registered. Either is enough to accept M-Pesa.
    can_stk = bool(settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET)
    can_paybill = bool(
        settings.MPESA_SHORTCODE
        or (business is not None and business.mpesa_shortcode)
        or (paybill and paybill.strip())
    )
    if can_stk or can_paybill:
        methods.add(MPESA)

    if settings.AIRTEL_CLIENT_ID and settings.AIRTEL_CLIENT_SECRET:
        methods.add(AIRTEL)

    if settings.FLUTTERWAVE_SECRET_KEY:
        methods.add(CARD)

    return methods


def enabled_methods(business: Business | None = None) -> list[str]:
    """The rails this landlord offers *and* this deployment can process.

    `payment_methods` is the multi-rail setting; `payment_method` is the older
    single-choice value and remains the fallback for businesses that predate it.
    """
    cfg = (business.settings or {}).get("business", {}) if business else {}
    selected = cfg.get("payment_methods") or [cfg.get("payment_method", MPESA)]
    if isinstance(selected, str):
        selected = [selected]
    configured = available_methods(business)
    return [m for m in (MPESA, AIRTEL, CARD, BANK) if m in selected and m in configured]


def other_payment_hint(methods: set[str]) -> str:
    """One line telling a tenant which of *their* rails to use instead."""
    commands = []
    if MPESA in methods:
        commands.append("PAY")
    if AIRTEL in methods:
        commands.append("AIRTEL")
    if CARD in methods:
        commands.append("CARD")
    commands.append("DONE <reference>")
    if len(commands) == 1:
        return f"Reply {commands[0]} to pay."
    return "Reply " + ", ".join(commands[:-1]) + f" or {commands[-1]} to pay another way."
