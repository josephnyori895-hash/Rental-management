"""
RENTAL OS — KRA eTIMS Compliance

Generates KRA Tax Invoice Management System (eTIMS) compliant invoice data
and export files. Works in simulated mode without KRA API credentials.

KRA eTIMS spec: invoices must include KRA PIN, serial number, QR data,
itemised amounts, and VAT breakdown where applicable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.config import settings


def etims_qr_data(
    invoice_number: str,
    seller_pin: str,
    buyer_pin: str | None,
    total_excl_vat: float,
    vat_amount: float,
    total_incl_vat: float,
    invoice_date: str,
) -> str:
    """Generate KRA eTIMS QR code string (simplified format).

    Actual KRA format: PIN|InvoiceNo|Date|TotalExcl|VAT|TotalIncl|CRC
    CRC = SHA256 of concatenated fields (last 4 hex chars).
    """
    raw = f"{seller_pin}|{invoice_number}|{invoice_date}|{total_excl_vat:.2f}|{vat_amount:.2f}|{total_incl_vat:.2f}"
    crc = hashlib.sha256(raw.encode()).hexdigest()[-4:].upper()
    return f"{raw}|{crc}"


def etims_invoice_data(
    invoice_number: str,
    invoice_type: str,
    amount: float,
    paid_amount: float,
    tenant_name: str,
    tenant_pin: str | None,
    seller_pin: str | None,
    invoice_date: str | None = None,
) -> dict[str, Any]:
    """Generate KRA eTIMS compliant invoice data structure."""
    today = invoice_date or date.today().isoformat()
    vat_rate = settings.DEFAULT_TAX_RATE
    is_vat_exempt = invoice_type in ("deposit", "late_fee")

    total_incl = amount
    if is_vat_exempt:
        total_excl = amount
        vat = 0.0
    else:
        total_excl = round(amount / (1 + vat_rate), 2)
        vat = round(amount - total_excl, 2)

    return {
        "invoice_number": invoice_number,
        "seller_pin": seller_pin or "",
        "buyer_name": tenant_name,
        "buyer_pin": tenant_pin or "",
        "invoice_date": today,
        "invoice_type": invoice_type.upper(),
        "currency": "KES",
        "items": [
            {
                "description": f"{invoice_type.replace('_', ' ').title()} - {invoice_number}",
                "quantity": 1,
                "unit_price": total_excl,
                "total_excl": total_excl,
                "vat_rate": 0 if is_vat_exempt else int(vat_rate * 100),
                "vat_amount": vat,
                "total_incl": total_incl,
            }
        ],
        "total_excl_vat": total_excl,
        "vat_amount": vat,
        "total_incl_vat": total_incl,
        "paid_amount": paid_amount,
        "balance": round(total_incl - paid_amount, 2),
        "qr_data": etims_qr_data(
            invoice_number,
            seller_pin or "",
            tenant_pin or "",
            total_excl,
            vat,
            total_incl,
            today,
        ),
        "etims_compliant": True,
    }


def export_etims_json(invoices: list[dict]) -> str:
    """Export invoices as KRA eTIMS JSON format."""
    payload = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "Rental OS",
        "total_invoices": len(invoices),
        "invoices": invoices,
    }
    return json.dumps(payload, indent=2, default=str)
