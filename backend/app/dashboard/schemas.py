"""
RENTAL OS — Dashboard Schemas

Owner board payload:
  - per hostel: every room as a light (green=paid / red=unpaid / empty=vacant)
  - paid tenants: full name, amount, house number, duration stayed (months)
  - vacant rooms list
  - defaulters: tenants who still owe the current month (the red lights, flattened)
  - totals: occupied, vacant, expected (= sum of occupied rents),
    collected, outstanding

Plus the metrics + performance-history shapes used by the Business Console.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class UnitLight(BaseModel):
    unit_id: str
    unit_number: str
    status: str
    light: str  # "green" | "red" | "empty"
    tenant_name: Optional[str] = None
    tenant_id: Optional[str] = None
    invoice_id: Optional[str] = None
    rent_amount: Optional[float] = None
    amount_paid: Optional[float] = None
    balance: Optional[float] = None
    duration_months: Optional[int] = None
    invoice_status: Optional[str] = None
    due_date: Optional[str] = None
    # Tenant contact details for in-app WhatsApp / call actions
    phone: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    mpesa_phone: Optional[str] = None


class PaidTenant(BaseModel):
    unit_number: str
    tenant_name: str
    amount: float
    duration_months: int


class VacantUnit(BaseModel):
    unit_number: str
    status: str


class Defaulter(BaseModel):
    property_name: str
    unit_number: str
    tenant_name: Optional[str] = None
    rent_amount: float
    amount_paid: float
    balance: float
    due_date: Optional[str] = None
    duration_months: Optional[int] = None


class HostelBoard(BaseModel):
    property_id: str
    name: str
    property_type: str
    total_units: int
    occupied: int
    vacant: int
    paid_count: int
    unpaid_count: int
    expected: float
    collected: float
    outstanding: float
    units: List[UnitLight]
    paid_tenants: List[PaidTenant]
    vacant_units: List[VacantUnit]


class OwnerBoard(BaseModel):
    hostels: List[HostelBoard]
    totals: dict
    defaulters: List[Defaulter] = []


class OwnerMetrics(BaseModel):
    total_units: int
    occupied: int
    vacant: int
    occupancy_rate: float  # percent
    total_revenue: float  # collected this calendar month (rent)
    total_arrears: float  # cumulative unpaid rent balance across all months
    expected_this_month: float
    collected_this_month: float
    outstanding_this_month: float
    paid_count: int
    unpaid_count: int


class PerformancePoint(BaseModel):
    month: str  # "2026-07"
    label: str  # "Jul 2026"
    collected: float  # revenue banked that month
    arrears: float  # unpaid balance that month
