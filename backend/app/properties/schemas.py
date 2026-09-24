"""
RENTAL OS — Property Schemas
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PropertyOut(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None
    property_type: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class UnitRoomOut(BaseModel):
    id: str
    unit_number: str
    unit_type: str
    status: str
    monthly_rent: float
    max_occupants: int
    tenant_name: str | None = None
    tenant_phone: str | None = None
    tenant_id: str | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    duration_months: int | None = None
    condition_notes: str | None = None
    invoice_status: str | None = None
    invoice_balance: float = 0.0
    total_paid: float = 0.0
    rent_light: str = "vacant"  # vacant|unpaid|partial|paid|overpaid

    model_config = {"from_attributes": True}


class UnitOut(BaseModel):
    id: UUID
    unit_number: str
    unit_type: str
    status: str
    monthly_rent: float
    max_occupants: int

    model_config = {"from_attributes": True}
