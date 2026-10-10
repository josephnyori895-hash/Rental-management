"""
RENTAL OS — Utility Billing Router

- GET  /billing/utilities/rates        : list configured tariffs
- POST /billing/utilities/rates        : create or update a tariff (upsert)
- GET  /billing/utilities/readings     : list meter readings
- POST /billing/utilities/readings     : record a reading, optionally bill it
- POST /billing/utilities/bill-shared  : apportion one shared cost across units

Mounted owner-only from `app.main`. All arithmetic lives in
`app.billing.utilities` so it stays testable without a database; the routes
here only resolve scope, persist, and post to the ledger.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.accounting.service import auto_post_invoice
from app.api.deps import SessionDep, get_current_business
from app.billing.utilities import (
    income_code_for,
    ReadingError,
    apportion,
    build_weights,
    compute_amount,
    compute_consumption,
    quantize_money,
    resolve_rate,
    split_method_for,
)
from app.models.billing import Invoice, InvoiceStatus
from app.models.business import Business
from app.models.lease import Lease
from app.models.property import Property, Unit, UnitStatus
from app.models.utilities import (
    MeterReading,
    MeterSource,
    SplitMethod,
    UtilityRate,
    UtilityType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/utilities", tags=["billing"])

VALID_UTILITY_TYPES = {t.value for t in UtilityType}
VALID_SPLIT_METHODS = {m.value for m in SplitMethod}


# ── Request bodies ─────────────────────────────────────────────────


class RateRequest(BaseModel):
    property_id: str
    unit_id: str | None = None
    utility_type: str = UtilityType.WATER.value
    label: str | None = None
    rate_per_unit: float = 0
    fixed_charge: float = 0
    split_method: str = SplitMethod.METERED.value
    is_active: bool = True


class ReadingRequest(BaseModel):
    current_reading: float
    unit_id: str | None = None
    property_id: str | None = None
    utility_type: str = UtilityType.WATER.value
    previous_reading: float | None = None
    reading_date: date | None = None
    rate_per_unit: float | None = None
    fixed_charge: float | None = None
    due_date: date | None = None
    bill: bool = True
    notes: str | None = None


class SharedBillRequest(BaseModel):
    property_id: str
    utility_type: str = UtilityType.WATER.value
    total_amount: float | None = None
    current_reading: float | None = None
    previous_reading: float | None = None
    rate_per_unit: float | None = None
    fixed_charge: float | None = None
    split_method: str | None = None
    period_start: date | None = None
    reading_date: date | None = None
    due_date: date | None = None
    bill: bool = True
    notes: str | None = None


# ── Helpers ────────────────────────────────────────────────────────


def _uuid(value, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _check_utility_type(value: str) -> str:
    if value not in VALID_UTILITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown utility_type '{value}'. Use one of: {sorted(VALID_UTILITY_TYPES)}",
        )
    return value


def _rate_json(rate: UtilityRate) -> dict:
    return {
        "id": str(rate.id),
        "property_id": str(rate.property_id),
        "unit_id": str(rate.unit_id) if rate.unit_id else None,
        "utility_type": rate.utility_type,
        "label": rate.label,
        "rate_per_unit": float(rate.rate_per_unit or 0),
        "fixed_charge": float(rate.fixed_charge or 0),
        "split_method": rate.split_method,
        "is_active": rate.is_active,
    }


def _reading_json(reading: MeterReading, unit_number: str | None = None) -> dict:
    return {
        "id": str(reading.id),
        "property_id": str(reading.property_id),
        "unit_id": str(reading.unit_id) if reading.unit_id else None,
        "unit_number": unit_number,
        "is_bulk": reading.is_bulk,
        "utility_type": reading.utility_type,
        "reading_date": str(reading.reading_date),
        "previous_reading": float(reading.previous_reading) if reading.previous_reading is not None else None,
        "current_reading": float(reading.current_reading),
        "units_consumed": float(reading.units_consumed or 0),
        "rate_per_unit": float(reading.rate_per_unit or 0),
        "fixed_charge": float(reading.fixed_charge or 0),
        "amount": float(reading.amount or 0),
        "invoice_id": str(reading.invoice_id) if reading.invoice_id else None,
        "source": reading.source,
        "notes": reading.notes,
    }


async def _get_property(session, business: Business, property_id) -> Property:
    prop = await session.get(Property, property_id)
    if not prop or prop.business_id != business.id or prop.is_deleted:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


async def _get_unit(session, business: Business, unit_id) -> Unit:
    unit = await session.get(Unit, unit_id)
    if not unit or unit.business_id != business.id or unit.is_deleted:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


async def _active_rates(session, business_id, property_id) -> list[UtilityRate]:
    rows = await session.execute(
        select(UtilityRate).where(
            UtilityRate.business_id == business_id,
            UtilityRate.property_id == property_id,
            UtilityRate.is_active.is_(True),
        )
    )
    return list(rows.scalars().all())


async def _last_reading(session, business_id, property_id, utility_type, unit_id):
    """Most recent reading for one meter scope (unit meter, or bulk)."""
    q = select(MeterReading).where(
        MeterReading.business_id == business_id,
        MeterReading.property_id == property_id,
        MeterReading.utility_type == utility_type,
    )
    if unit_id:
        q = q.where(MeterReading.unit_id == unit_id)
    else:
        q = q.where(MeterReading.unit_id.is_(None))
    q = q.order_by(MeterReading.reading_date.desc(), MeterReading.created_at.desc()).limit(1)
    return await session.scalar(q)


async def _active_lease(session, unit: Unit) -> Lease | None:
    if not unit.current_lease_id:
        return None
    lease = await session.get(Lease, unit.current_lease_id)
    if not lease or lease.status != "active":
        return None
    return lease


async def _bill_unit(
    session, business: Business, unit: Unit, lease: Lease,
    utility_type: str, amount: Decimal, description: str, due_date: date | None,
) -> Invoice:
    """Raise a utility invoice for one unit and post it to the ledger."""
    invoice = Invoice(
        business_id=business.id,
        lease_id=lease.id,
        tenant_id=lease.tenant_id,
        unit_id=unit.id,
        property_id=unit.property_id,
        invoice_type=utility_type,
        amount=amount,
        paid_amount=Decimal("0"),
        balance=amount,
        status=InvoiceStatus.PENDING.value,
        due_date=due_date,
        description=description,
    )
    session.add(invoice)
    await session.flush()
    try:
        await auto_post_invoice(
            session, invoice, income_code=income_code_for(utility_type)
        )
    except Exception:
        # Billing must not fail because the chart of accounts is incomplete.
        logger.warning("Ledger posting failed for utility invoice %s", invoice.id, exc_info=True)
    return invoice


def _resolve_pricing(data, rate) -> tuple[Decimal, Decimal]:
    """Explicit request values win over the stored tariff."""
    if data.rate_per_unit is not None:
        rate_per_unit = Decimal(str(data.rate_per_unit))
    elif rate is not None:
        rate_per_unit = rate.rate_per_unit
    else:
        rate_per_unit = Decimal("0")

    if data.fixed_charge is not None:
        fixed_charge = Decimal(str(data.fixed_charge))
    elif rate is not None:
        fixed_charge = rate.fixed_charge
    else:
        fixed_charge = Decimal("0")

    return rate_per_unit, fixed_charge


# ── Tariffs ────────────────────────────────────────────────────────


@router.get("/rates")
async def list_rates(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    property_id: Optional[str] = Query(None),
    utility_type: Optional[str] = Query(None),
):
    """List configured utility tariffs."""
    q = select(UtilityRate).where(UtilityRate.business_id == business.id)
    if property_id:
        q = q.where(UtilityRate.property_id == _uuid(property_id, "property_id"))
    if utility_type:
        q = q.where(UtilityRate.utility_type == utility_type)
    q = q.order_by(UtilityRate.utility_type, UtilityRate.unit_id.asc().nullsfirst())

    rates = (await session.execute(q)).scalars().all()
    return {"total": len(rates), "rates": [_rate_json(r) for r in rates]}


@router.post("/rates", status_code=201)
async def upsert_rate(
    data: RateRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Create or update a tariff for a property (optionally one unit)."""
    prop = await _get_property(session, business, _uuid(data.property_id, "property_id"))
    utility_type = _check_utility_type(data.utility_type)

    if data.split_method not in VALID_SPLIT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown split_method '{data.split_method}'. Use one of: {sorted(VALID_SPLIT_METHODS)}",
        )

    unit_id = None
    if data.unit_id:
        unit_id = _uuid(data.unit_id, "unit_id")
        unit = await _get_unit(session, business, unit_id)
        if unit.property_id != prop.id:
            raise HTTPException(status_code=400, detail="Unit does not belong to that property")

    q = select(UtilityRate).where(
        UtilityRate.business_id == business.id,
        UtilityRate.property_id == prop.id,
        UtilityRate.utility_type == utility_type,
    )
    q = q.where(UtilityRate.unit_id == unit_id) if unit_id else q.where(UtilityRate.unit_id.is_(None))
    rate = await session.scalar(q.limit(1))

    if rate is None:
        rate = UtilityRate(
            business_id=business.id,
            property_id=prop.id,
            unit_id=unit_id,
            utility_type=utility_type,
        )
        session.add(rate)

    rate.label = data.label
    rate.rate_per_unit = Decimal(str(data.rate_per_unit))
    rate.fixed_charge = Decimal(str(data.fixed_charge))
    rate.split_method = data.split_method
    rate.is_active = data.is_active

    await session.commit()
    return _rate_json(rate)


# ── Readings ───────────────────────────────────────────────────────


@router.get("/readings")
async def list_readings(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    property_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    utility_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List meter readings, newest first."""
    q = (
        select(MeterReading, Unit.unit_number)
        .select_from(MeterReading)
        .outerjoin(Unit, MeterReading.unit_id == Unit.id)
        .where(MeterReading.business_id == business.id)
        .order_by(MeterReading.reading_date.desc(), MeterReading.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if property_id:
        q = q.where(MeterReading.property_id == _uuid(property_id, "property_id"))
    if unit_id:
        q = q.where(MeterReading.unit_id == _uuid(unit_id, "unit_id"))
    if utility_type:
        q = q.where(MeterReading.utility_type == utility_type)

    rows = (await session.execute(q)).all()
    return {
        "total": len(rows),
        "readings": [_reading_json(reading, unit_number) for reading, unit_number in rows],
    }


@router.post("/readings", status_code=201)
async def record_reading(
    data: ReadingRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Record a meter reading and (for an occupied unit) invoice the tenant."""
    if not data.unit_id and not data.property_id:
        raise HTTPException(status_code=400, detail="unit_id or property_id is required")

    unit: Unit | None = None
    if data.unit_id:
        unit = await _get_unit(session, business, _uuid(data.unit_id, "unit_id"))
        prop = await _get_property(session, business, unit.property_id)
    else:
        prop = await _get_property(session, business, _uuid(data.property_id, "property_id"))

    utility_type = _check_utility_type(data.utility_type)
    reading_date = data.reading_date or date.today()

    if data.previous_reading is not None:
        previous = Decimal(str(data.previous_reading))
    else:
        last = await _last_reading(
            session, business.id, prop.id, utility_type, unit.id if unit else None
        )
        previous = last.current_reading if last else None

    try:
        consumed = compute_consumption(previous, data.current_reading)
    except ReadingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    rate = resolve_rate(
        await _active_rates(session, business.id, prop.id),
        utility_type,
        unit.id if unit else None,
    )
    rate_per_unit, fixed_charge = _resolve_pricing(data, rate)
    amount = compute_amount(consumed, rate_per_unit, fixed_charge)

    reading = MeterReading(
        business_id=business.id,
        property_id=prop.id,
        unit_id=unit.id if unit else None,
        utility_type=utility_type,
        reading_date=reading_date,
        previous_reading=Decimal(str(previous)) if previous is not None else None,
        current_reading=Decimal(str(data.current_reading)),
        units_consumed=consumed,
        rate_per_unit=rate_per_unit,
        fixed_charge=fixed_charge,
        amount=amount,
        source=MeterSource.WEB.value,
        notes=data.notes,
    )
    session.add(reading)
    await session.flush()

    note = None
    invoice: Invoice | None = None
    if data.bill and unit is not None:
        lease = await _active_lease(session, unit)
        if lease is None:
            note = "Unit is vacant — reading stored, nothing billed."
        elif amount > 0:
            invoice = await _bill_unit(
                session, business, unit, lease, utility_type, amount,
                f"{utility_type.replace('_', ' ').title()} — {reading_date.isoformat()}",
                data.due_date,
            )
            reading.invoice_id = invoice.id
        else:
            note = "Baseline reading — no consumption to bill yet."

    if note:
        reading.notes = f"{reading.notes}\n{note}".strip() if reading.notes else note

    await session.commit()

    return {
        "reading": _reading_json(reading, unit.unit_number if unit else None),
        "consumed": float(consumed),
        "amount": float(amount),
        "billed": invoice is not None,
        "invoice_id": str(invoice.id) if invoice else None,
        "note": note,
    }


# ── Shared (bulk) meters ───────────────────────────────────────────


@router.post("/bill-shared", status_code=201)
async def bill_shared(
    data: SharedBillRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Apportion one shared utility cost across a property's occupied units.

    Pass `total_amount` for an already-known bill (e.g. the water company's
    invoice), or a `current_reading` to price the consumption yourself.
    """
    prop = await _get_property(session, business, _uuid(data.property_id, "property_id"))
    utility_type = _check_utility_type(data.utility_type)
    reading_date = data.reading_date or date.today()
    period_start = data.period_start or reading_date.replace(day=1)

    rates = await _active_rates(session, business.id, prop.id)
    rate = resolve_rate(rates, utility_type, None)
    method = data.split_method or split_method_for(rate)
    if method not in VALID_SPLIT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown split_method '{method}'. Use one of: {sorted(VALID_SPLIT_METHODS)}",
        )

    previous = None
    consumed = None
    rate_per_unit, fixed_charge = _resolve_pricing(data, rate)
    if data.total_amount is not None:
        total = quantize_money(data.total_amount)
    else:
        if data.current_reading is None:
            raise HTTPException(
                status_code=400,
                detail="Provide total_amount, or current_reading plus a configured tariff",
            )
        if data.previous_reading is not None:
            previous = Decimal(str(data.previous_reading))
        else:
            last = await _last_reading(session, business.id, prop.id, utility_type, None)
            previous = last.current_reading if last else None

        try:
            consumed = compute_consumption(previous, data.current_reading)
        except ReadingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if rate_per_unit == 0 and fixed_charge == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No tariff configured for '{utility_type}' on this property. "
                    "Set one via POST /billing/utilities/rates, or pass total_amount."
                ),
            )
        total = compute_amount(consumed, rate_per_unit, fixed_charge)

    units = (await session.execute(
        select(Unit)
        .where(
            Unit.business_id == business.id,
            Unit.property_id == prop.id,
            Unit.is_deleted.is_(False),
            Unit.status == UnitStatus.OCCUPIED.value,
            Unit.current_lease_id.is_not(None),
        )
        .order_by(Unit.unit_number)
    )).scalars().all()

    if not units:
        raise HTTPException(status_code=400, detail="No occupied units in this property")

    # Per-unit consumption inside the period, for a "metered" split.
    rows = (await session.execute(
        select(MeterReading.unit_id, func.sum(MeterReading.units_consumed))
        .where(
            MeterReading.business_id == business.id,
            MeterReading.property_id == prop.id,
            MeterReading.utility_type == utility_type,
            MeterReading.unit_id.is_not(None),
            MeterReading.reading_date >= period_start,
            MeterReading.reading_date <= reading_date,
        )
        .group_by(MeterReading.unit_id)
    )).all()
    consumed_by_unit = {row[0]: row[1] for row in rows}
    for unit in units:
        unit.consumed = consumed_by_unit.get(unit.id)

    weights, missing = build_weights(units, method)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot split '{method}' — no meter reading this period for: "
                f"{', '.join(missing)}. Record unit readings first, or pass split_method=equal."
            ),
        )

    shares = apportion(total, weights, method)

    breakdown = []
    for index, (unit, share) in enumerate(zip(units, shares)):
        lease = await _active_lease(session, unit)
        invoice = None
        if data.bill and lease is not None and share > 0:
            invoice = await _bill_unit(
                session, business, unit, lease, utility_type, share,
                (
                    f"{utility_type.replace('_', ' ').title()} "
                    f"{period_start.isoformat()} to {reading_date.isoformat()}"
                ),
                data.due_date,
            )
        breakdown.append({
            "unit_id": str(unit.id),
            "unit_number": unit.unit_number,
            "weight": float(weights[index]) if method != SplitMethod.EQUAL.value else 1.0,
            "share": float(share),
            "invoice_id": str(invoice.id) if invoice else None,
            "tenant_id": str(lease.tenant_id) if lease else None,
            "billed": invoice is not None,
        })

    bulk_reading = None
    if data.current_reading is not None:
        bulk_reading = MeterReading(
            business_id=business.id,
            property_id=prop.id,
            unit_id=None,
            utility_type=utility_type,
            reading_date=reading_date,
            previous_reading=Decimal(str(previous)) if previous is not None else None,
            current_reading=Decimal(str(data.current_reading)),
            units_consumed=consumed or Decimal("0"),
            rate_per_unit=rate_per_unit,
            fixed_charge=fixed_charge,
            amount=total,
            source=MeterSource.WEB.value,
            notes=data.notes,
        )
        session.add(bulk_reading)

    await session.commit()

    return {
        "property_id": str(prop.id),
        "utility_type": utility_type,
        "split_method": method,
        "period_start": str(period_start),
        "period_end": str(reading_date),
        "total": float(total),
        "units_billed": sum(1 for row in breakdown if row["billed"]),
        "reading_id": str(bulk_reading.id) if bulk_reading else None,
        "breakdown": breakdown,
    }
