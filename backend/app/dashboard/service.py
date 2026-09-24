"""
RENTAL OS — Dashboard Service

Computes the owner board for a business: per hostel, every room rendered as a
light (green=current rent paid / red=unpaid / empty=vacant), paid tenants with
name/amount/house/duration, vacant list, and money totals.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard.schemas import (
    Defaulter,
    HostelBoard,
    OwnerBoard,
    OwnerMetrics,
    PaidTenant,
    PerformancePoint,
    UnitLight,
    VacantUnit,
)
from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, UnitStatus
from app.models.tenant import Tenant


def _months_between(start: date, end: date) -> int:
    if not start:
        return 0
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def _f(v) -> float:
    return float(v) if isinstance(v, Decimal) else float(v or 0)


async def get_owner_board(session: AsyncSession, business_id) -> dict:
    props = (
        await session.scalars(
            select(Property).where(
                Property.business_id == business_id,
                Property.is_deleted.is_(False),
            )
        )
    ).all()

    hostels: list = []
    defaulters: list = []
    g = {"occupied": 0, "vacant": 0, "paid": 0, "unpaid": 0,
         "expected": 0.0, "collected": 0.0, "outstanding": 0.0}
    today = date.today()

    for p in props:
        units = (
            await session.scalars(
                select(Unit).where(
                    Unit.property_id == p.id, Unit.is_deleted.is_(False)
                )
            )
        ).all()

        unit_lights: list = []
        paid_tenants: list = []
        vacant_units: list = []
        occupied = vacant_c = paid_c = unpaid_c = 0
        expected = collected = outstanding = 0.0

        for u in units:
            is_vacant = u.status in (
                UnitStatus.AVAILABLE.value,
                UnitStatus.RESERVED.value,
                UnitStatus.MAINTENANCE.value,
            )
            if is_vacant:
                vacant_c += 1
                vacant_units.append(VacantUnit(unit_number=u.unit_number, status=u.status))
                unit_lights.append(UnitLight(
                    unit_id=str(u.id), unit_number=u.unit_number,
                    status=u.status, light="empty",
                ))
                continue

            lease = (
                await session.scalars(
                    select(Lease).where(
                        Lease.unit_id == u.id,
                        Lease.status == LeaseStatus.ACTIVE.value,
                    )
                )
            ).first()

            if not lease:
                # marked occupied but no active lease -> treat as vacant
                vacant_c += 1
                vacant_units.append(VacantUnit(unit_number=u.unit_number, status=u.status))
                unit_lights.append(UnitLight(
                    unit_id=str(u.id), unit_number=u.unit_number,
                    status=u.status, light="empty",
                ))
                continue

            occupied += 1
            rent = _f(u.monthly_rent)
            expected += rent

            invoice = (
                await session.scalars(
                    select(Invoice)
                    .where(
                        Invoice.lease_id == lease.id,
                        Invoice.invoice_type == InvoiceType.RENT.value,
                    )
                    .order_by(Invoice.period_start.desc().nullslast(), Invoice.created_at.desc())
                )
            ).first()

            tenant = await session.get(Tenant, lease.tenant_id)
            tname = tenant.full_name if tenant else None
            tid = str(tenant.id) if tenant else None
            duration = _months_between(lease.start_date, today)
            paid_amt = _f(invoice.paid_amount) if invoice else 0.0
            inv_id = str(invoice.id) if invoice else None

            if invoice is None or invoice.status == InvoiceStatus.PAID.value or _f(invoice.balance) == 0:
                paid_c += 1
                collected += paid_amt
                if tenant:
                    paid_tenants.append(PaidTenant(
                        unit_number=u.unit_number, tenant_name=tname,
                        amount=paid_amt, duration_months=duration,
                    ))
                unit_lights.append(UnitLight(
                    unit_id=str(u.id), unit_number=u.unit_number, status=u.status,
                    light="green", tenant_name=tname, tenant_id=tid,
                    invoice_id=inv_id, rent_amount=rent,
                    amount_paid=paid_amt, balance=0.0, duration_months=duration,
                    invoice_status=invoice.status if invoice else None,
                    phone=tenant.phone if tenant else None,
                    whatsapp_phone=tenant.whatsapp_phone if tenant else None,
                    mpesa_phone=tenant.mpesa_phone if tenant else None,
                ))
            else:
                unpaid_c += 1
                bal = _f(invoice.balance) if invoice else rent
                outstanding += bal
                unit_lights.append(UnitLight(
                    unit_id=str(u.id), unit_number=u.unit_number, status=u.status,
                    light="red", tenant_name=tname, tenant_id=tid,
                    invoice_id=inv_id, rent_amount=rent,
                    amount_paid=paid_amt, balance=bal, duration_months=duration,
                    invoice_status=invoice.status if invoice else None,
                    due_date=str(invoice.due_date) if invoice and invoice.due_date else None,
                    phone=tenant.phone if tenant else None,
                    whatsapp_phone=tenant.whatsapp_phone if tenant else None,
                    mpesa_phone=tenant.mpesa_phone if tenant else None,
                ))
                defaulters.append(Defaulter(
                    property_name=p.name,
                    unit_number=u.unit_number,
                    tenant_name=tname,
                    rent_amount=rent,
                    amount_paid=paid_amt,
                    balance=bal,
                    due_date=str(invoice.due_date) if invoice and invoice.due_date else None,
                    duration_months=duration,
                ))

        hostels.append(HostelBoard(
            property_id=str(p.id), name=p.name, property_type=p.property_type,
            total_units=len(units), occupied=occupied, vacant=vacant_c,
            paid_count=paid_c, unpaid_count=unpaid_c,
            expected=expected, collected=collected, outstanding=outstanding,
            units=unit_lights, paid_tenants=paid_tenants, vacant_units=vacant_units,
        ))
        g["occupied"] += occupied
        g["vacant"] += vacant_c
        g["paid"] += paid_c
        g["unpaid"] += unpaid_c
        g["expected"] += expected
        g["collected"] += collected
        g["outstanding"] += outstanding

    return OwnerBoard(hostels=hostels, totals=g, defaulters=defaulters)


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _next_month_start(d: date) -> date:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


async def get_owner_metrics(session: AsyncSession, business_id) -> OwnerMetrics:
    """Headline KPIs for the Business Console telemetry row."""
    props = (
        await session.scalars(
            select(Property).where(
                Property.business_id == business_id,
                Property.is_deleted.is_(False),
            )
        )
    ).all()

    total_units = occupied = vacant = 0
    for p in props:
        units = (
            await session.scalars(
                select(Unit).where(
                    Unit.property_id == p.id, Unit.is_deleted.is_(False)
                )
            )
        ).all()
        for u in units:
            total_units += 1
            if u.status in (UnitStatus.AVAILABLE.value, UnitStatus.RESERVED.value,
                            UnitStatus.MAINTENANCE.value):
                vacant += 1
            else:
                occupied += 1

    occupancy_rate = round((occupied / total_units * 100), 1) if total_units else 0.0

    ms = _month_start(date.today())
    nm = _next_month_start(date.today())

    total_revenue = _f(
        await session.scalar(
            select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                Invoice.business_id == business_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.period_start >= ms,
                Invoice.period_start < nm,
            )
        )
    )
    total_arrears = _f(
        await session.scalar(
            select(func.coalesce(func.sum(Invoice.balance), 0)).where(
                Invoice.business_id == business_id,
                Invoice.invoice_type == InvoiceType.RENT.value,
                Invoice.status != InvoiceStatus.PAID.value,
                Invoice.balance > 0,
            )
        )
    )

    m = await get_owner_board(session, business_id)
    g = m.totals
    return OwnerMetrics(
        total_units=total_units,
        occupied=occupied,
        vacant=vacant,
        occupancy_rate=occupancy_rate,
        total_revenue=total_revenue,
        total_arrears=total_arrears,
        expected_this_month=_f(g.get("expected", 0)),
        collected_this_month=_f(g.get("collected", 0)),
        outstanding_this_month=_f(g.get("outstanding", 0)),
        paid_count=int(g.get("paid", 0)),
        unpaid_count=int(g.get("unpaid", 0)),
    )


async def get_performance_history(
    session: AsyncSession, business_id, months: int = 6
) -> list:
    """Last `months` of collected-vs-arrears, one point per calendar month."""
    today = date.today()
    points: list = []
    for back in range(months - 1, -1, -1):
        y, mo = today.year, today.month - back
        while mo <= 0:
            mo += 12
            y -= 1
        ms = date(y, mo, 1)
        nm = _next_month_start(ms)
        collected = _f(
            await session.scalar(
                select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                    Invoice.business_id == business_id,
                    Invoice.invoice_type == InvoiceType.RENT.value,
                    Invoice.period_start >= ms,
                    Invoice.period_start < nm,
                )
            )
        )
        arrears = _f(
            await session.scalar(
                select(func.coalesce(func.sum(Invoice.balance), 0)).where(
                    Invoice.business_id == business_id,
                    Invoice.invoice_type == InvoiceType.RENT.value,
                    Invoice.status != InvoiceStatus.PAID.value,
                    Invoice.balance > 0,
                    Invoice.period_start >= ms,
                    Invoice.period_start < nm,
                )
            )
        )
        points.append(
            PerformancePoint(
                month=ms.strftime("%Y-%m"),
                label=ms.strftime("%b %Y"),
                collected=collected,
                arrears=arrears,
            )
        )
    return points
