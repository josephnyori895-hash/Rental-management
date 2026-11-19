"""
RENTAL OS — Notification Message Templates

Pure string builders for every SMS / WhatsApp message the system sends.
No I/O and no database access — these are safe to unit-test directly.

  - SMS: rent_reminder, payment_receipt, lease_expiry
  - WhatsApp: welcome_enrollment, payment_prompt, rent_reminder,
              payment_receipt, maintenance_update, lease_expiry, balance, help
  - Caretaker: ticket_alert, payment_alert, move_in_alert, unpaid_alert

The senders that actually dispatch these live in
`app.notifications.service`.
"""

from __future__ import annotations


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
    pay_methods = (bank_info or {}).get("payment_methods") or [
        (bank_info or {}).get("payment_method", "mpesa")
    ]
    if pay_methods == ["bank"]:
        lines.append(f"Please deposit/transfer payment to:")
        lines.append(f"  Bank: {bank_info.get('bank_name', 'Equity Bank')}")
        lines.append(f"  Account: {bank_info.get('bank_account', '—')}")
        lines.append(f"  Name: {bank_info.get('bank_account_name', 'Hostel')}")
        lines.append(f"")
        lines.append(f"Reply DONE <reference> once paid.")
    else:
        labels = {
            "mpesa": "M-Pesa",
            "airtel": "Airtel Money",
            "card": "card or online bank transfer",
            "bank": "bank transfer",
        }
        if len(pay_methods) > 1:
            lines.append(
                "Reply PAY to choose how to pay: "
                + ", ".join(labels.get(m, m) for m in pay_methods)
            )
        else:
            lines.append(
                f"Reply PAY to pay now via {labels.get(pay_methods[0], 'M-Pesa')}"
            )
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


def _build_wa_balance(
    tenant_name: str, unit_number: str, balance: float,
    due_date: str | None, payment_info: dict | None = None,
) -> str:
    lines = [
        f"💰 Balance for {tenant_name}",
        unit_number,
        f"Outstanding: KES {balance:,.0f}",
    ]
    if due_date:
        lines.append(f"Due: {due_date}")

    if balance <= 0:
        lines.append("You're all clear! ✅")
        return "\n".join(lines)

    methods = (payment_info or {}).get("methods") or []
    if methods:
        labels = {
            "mpesa": "M-Pesa",
            "airtel": "Airtel Money",
            "card": "Card / online bank",
        }
        lines.append("")
        lines.append("Ways to pay:")
        for method in methods:
            if method == "bank":
                continue
            lines.append(f"  • {labels.get(method, method)} — reply PAY {method.upper()}")
        if "bank" in methods:
            info = payment_info or {}
            lines.append("  • Bank transfer:")
            lines.append(f"      Bank: {info.get('bank_name') or '—'}")
            lines.append(f"      Account: {info.get('bank_account') or '—'}")
            lines.append(
                f"      Name: {info.get('bank_account_name') or tenant_name}"
            )
            lines.append("      Reply DONE <reference> once paid")
        lines.append("")
        lines.append("Reply PAY to pay now")
    else:
        lines.append("Reply PAY to pay now")
    return "\n".join(lines)


def _build_wa_utility_bill(
    tenant_name: str, unit_number: str, utility_type: str,
    consumed: float, amount: float, due_date: str | None = None,
) -> str:
    label = utility_type.replace("_", " ").upper()
    msg = (
        f"🧾 {label} BILL — {tenant_name}\n"
        f"{unit_number}\n"
        f"Usage: {consumed:g}\n"
        f"Amount: KES {amount:,.2f}\n"
    )
    if due_date:
        msg += f"Due: {due_date}\n"
    msg += "Reply BALANCE for your total or PAY to pay now."
    return msg


def _build_wa_help(methods: set[str] | None = None) -> str:
    """Menu of what this property can actually accept.

    Advertising an unconfigured rail only sends tenants into a dead end.
    `None` keeps the full menu for callers that have no business context.
    """
    available = methods if methods is not None else {"mpesa", "airtel", "card", "bank"}
    lines = ["Reply with a keyword:", "BALANCE — Check your balance"]
    if "mpesa" in available:
        lines.append("PAY — Pay rent via M-Pesa")
    if "airtel" in available:
        lines.append("AIRTEL — Pay via Airtel Money")
    if "card" in available:
        lines.append("CARD — Pay by card or bank transfer")
    lines += [
        "DONE <ref> — Confirm a bank transfer",
        "RECEIPT — Get last receipt",
        "REPORT — Report maintenance issue",
        "RENEW — Request lease renewal",
        "HELP — Show this menu",
    ]
    return "\n".join(lines)


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


def _build_wa_caretaker_arrears(sections: list[dict]) -> str:
    """One digest per caretaker, grouped by the properties they run."""
    unpaid = sum(section["unpaid"] for section in sections)
    lines = [f"⚠️ ARREARS — {unpaid} unpaid"]
    for section in sections:
        lines.append(
            f"{section['property']}: {section['unpaid']} · "
            f"KES {section['total']:,.0f}"
        )

    details = [line for section in sections for line in section["units"]]
    if details:
        lines.append("")
        lines.extend(details[:8])
        if len(details) > 8:
            lines.append(f"…and {len(details) - 8} more on the dashboard.")
    return "\n".join(lines)


def _build_wa_caretaker_unpaid(tenant_name: str, unit_number: str, amount: float, days_overdue: int) -> str:
    return (
        f"⚠️ UNPAID — {tenant_name}\n"
        f"{unit_number}\n"
        f"KES {amount:,.0f} overdue by {days_overdue} days\n"
        f"Please follow up."
    )
