"""
RENTAL OS — Reports: Aged Receivables & Rent Roll

The two operational reports an agency opens first:

  - **aged receivables** — outstanding invoices bucketed by how overdue they are
  - **rent roll** — one row per active lease, with its arrears balance

Query construction is kept in module-level, side-effect-free builders so the
statements can be compiled and asserted on without a live database.
Mounted under `/reports` by `app.reports.router`.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select

from app.api.deps import SessionDep, get_current_user
from app.models.billing import Invoice
from app.models.business import User
from app.models.lease import Lease
from app.models.property import Property, Unit
from app.models.tenant import Tenant

router = APIRouter()

# Invoice states that still owe money.
OUTSTANDING_STATUSES = ("pending", "partial", "overdue")

# Standard aging buckets, oldest debt last so callers can render left-to-right.
AGING_BUCKETS = ("current", "days_1_30", "days_31_60", "days_61_90", "days_90_plus")


def _age_bucket(due: date | None, today: date) -> str:
    """Bucket an outstanding invoice by how overdue it is."""
    if due is None or due >= today:
        return "current"
    overdue_days = (today - due).days
    if overdue_days <= 30:
        return "days_1_30"
    if overdue_days <= 60:
        return "days_31_60"
    if overdue_days <= 90:
        return "days_61_90"
    return "days_90_plus"


def _aged_receivables_query(business_id: UUID) -> Select:
    """Outstanding invoices joined to the tenant and unit they belong to."""
    return (
        select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.invoice_type,
            Invoice.due_date,
            Invoice.amount,
            Invoice.paid_amount,
            Invoice.balance,
            Invoice.status,
            Tenant.id.label("tenant_id"),
            Tenant.full_name,
            Tenant.phone,
            Unit.unit_number,
        )
        .join(Tenant, Invoice.tenant_id == Tenant.id)
        .join(Unit, Invoice.unit_id == Unit.id)
        .where(
            Invoice.business_id == business_id,
            Invoice.status.in_(OUTSTANDING_STATUSES),
            Invoice.balance > 0,
        )
        .order_by(Invoice.due_date.asc())
    )


def _rent_roll_query(business_id: UUID) -> Select:
    """One row per active lease."""
    return (
        select(
            Lease.id,
            Lease.rent_amount,
            Lease.deposit_amount,
            Lease.start_date,
            Lease.end_date,
            Lease.payment_day,
            Lease.status,
            Unit.unit_number,
            Unit.status.label("unit_status"),
            Property.name.label("property_name"),
            Tenant.full_name,
            Tenant.phone,
        )
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Lease.property_id == Property.id)
        .join(Tenant, Lease.tenant_id == Tenant.id)
        .where(Lease.business_id == business_id, Lease.status == "active")
        .order_by(Property.name, Unit.unit_number)
    )


def _outstanding_by_lease_query(business_id: UUID) -> Select:
    """Total outstanding balance per lease, for attaching to the rent roll."""
    return (
        select(Invoice.lease_id, func.coalesce(func.sum(Invoice.balance), 0))
        .where(
            Invoice.business_id == business_id,
            Invoice.status.in_(OUTSTANDING_STATUSES),
            Invoice.balance > 0,
        )
        .group_by(Invoice.lease_id)
    )


@router.get("/aged-receivables")
async def aged_receivables(
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """
    Outstanding rent bucketed by how overdue it is.

    Returns per-invoice detail, per-tenant rollup, and bucket totals.
    """
    today = date.today()
    rows = (await session.execute(_aged_receivables_query(user.business_id))).all()

    totals = {bucket: 0.0 for bucket in AGING_BUCKETS}
    by_tenant: dict[str, dict] = {}
    invoices: list[dict] = []

    for r in rows:
        bucket = _age_bucket(r.due_date, today)
        balance = float(r.balance or 0)
        days_overdue = (today - r.due_date).days if r.due_date and r.due_date < today else 0

        invoices.append({
            "invoice_id": str(r.id),
            "invoice_number": r.invoice_number,
            "type": r.invoice_type,
            "status": r.status,
            "tenant_id": str(r.tenant_id),
            "tenant": r.full_name,
            "unit": r.unit_number,
            "due_date": str(r.due_date) if r.due_date else None,
            "days_overdue": days_overdue,
            "bucket": bucket,
            "amount": float(r.amount or 0),
            "paid": float(r.paid_amount or 0),
            "balance": balance,
        })

        totals[bucket] += balance

        key = str(r.tenant_id)
        entry = by_tenant.setdefault(key, {
            "tenant_id": key,
            "tenant": r.full_name,
            "phone": r.phone,
            "units": set(),
            "aging": {b: 0.0 for b in AGING_BUCKETS},
        })
        entry["units"].add(r.unit_number)
        entry["aging"][bucket] += balance

    tenants = []
    for entry in by_tenant.values():
        entry["units"] = sorted(entry["units"])
        entry["aging"] = {b: round(v, 2) for b, v in entry["aging"].items()}
        entry["total"] = round(sum(entry["aging"].values()), 2)
        tenants.append(entry)
    tenants.sort(key=lambda t: t["total"], reverse=True)

    return {
        "as_at": str(today),
        "buckets": list(AGING_BUCKETS),
        "summary": {
            "total_outstanding": round(sum(totals.values()), 2),
            "invoice_count": len(invoices),
            "tenant_count": len(tenants),
            **{b: round(v, 2) for b, v in totals.items()},
        },
        "by_tenant": tenants,
        "invoices": invoices,
    }


@router.get("/rent-roll")
async def rent_roll(
    session: SessionDep = None,
    user: User = Depends(get_current_user),
):
    """One row per active lease, with rent, deposit and arrears."""
    today = date.today()
    rows = (await session.execute(_rent_roll_query(user.business_id))).all()
    balance_rows = (await session.execute(_outstanding_by_lease_query(user.business_id))).all()
    outstanding = {row[0]: float(row[1] or 0) for row in balance_rows}

    items: list[dict] = []
    monthly_total = 0.0
    outstanding_total = 0.0

    for r in rows:
        rent = float(r.rent_amount or 0)
        arrears = outstanding.get(r.id, 0.0)
        monthly_total += rent
        outstanding_total += arrears

        items.append({
            "lease_id": str(r.id),
            "property": r.property_name,
            "unit": r.unit_number,
            "unit_status": r.unit_status,
            "tenant": r.full_name,
            "phone": r.phone,
            "rent": rent,
            "deposit": float(r.deposit_amount or 0),
            "payment_day": r.payment_day,
            "start_date": str(r.start_date) if r.start_date else None,
            "end_date": str(r.end_date) if r.end_date else None,
            "status": r.status,
            "outstanding": arrears,
        })

    return {
        "as_at": str(today),
        "summary": {
            "active_leases": len(items),
            "monthly_rent": round(monthly_total, 2),
            "total_outstanding": round(outstanding_total, 2),
        },
        "rows": items,
    }
