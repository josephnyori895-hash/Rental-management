"""
RENTAL OS — Tenant Schemas
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class EnrollRequest(BaseModel):
    """Caretaker enrollment payload: tenant + house number + M-Pesa phone."""

    full_name: str
    id_number: Optional[str] = None
    phone: Optional[str] = None
    mpesa_phone: Optional[str] = None
    whatsapp_phone: Optional[str] = None  # defaults to mpesa_phone if omitted
    email: Optional[str] = None
    unit_id: str
    start_date: date
    rent_amount: Optional[float] = None
    deposit_amount: float = 0.0
    payment_day: int = 1


class EnrollResponse(BaseModel):
    tenant_id: str
    lease_id: str
    invoice_id: str
    unit_number: str
    rent_amount: float
    message: str
    whatsapp_sent: bool = False
