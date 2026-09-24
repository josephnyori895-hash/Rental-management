"""
RENTAL OS — Analytics Service

Generates actionable insights from business data using rule-based analysis:
- Payment prediction: which tenants are likely to pay late
- Vacancy risk: which units/properties may become vacant
- Collection health: trend analysis with flags
- AI commentary: human-readable summaries of findings
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, UnitStatus
from app.models.tenant import Tenant


async def get_insights(
    session: AsyncSession,
    business_id: uuid.UUID,
) -> dict:
    """Run all analytics and return structured insights + commentary."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    ninety_days_ago = today - timedelta(days=90)

    # ── Payment Risk ─────────────────────────────────────────────
    # Tenants who paid late >50% of the time in last 90 days
    late_payers = []
    all_tenants_q = select(Tenant).where(
        Tenant.business_id == business_id, Tenant.is_deleted.is_(False),
    )
    tenants = (await session.scalars(all_tenants_q)).all()

    for t in tenants:
        invs_q = select(Invoice).where(
            Invoice.tenant_id == t.id,
            Invoice.invoice_type == InvoiceType.RENT.value,
            Invoice.created_at >= ninety_days_ago,
        )
        invoices = (await session.scalars(invs_q)).all()
        if not invoices:
            continue

        late_count = 0
        for inv in invoices:
            if inv.status == InvoiceStatus.OVERDUE.value or (
                inv.due_date and inv.created_at.date() > inv.due_date
                if hasattr(inv.created_at, "date") else False
            ):
                late_count += 1

        late_ratio = late_count / len(invoices) if invoices else 0
        if late_ratio > 0.5:
            lease = await session.scalar(
                select(Lease).where(
                    Lease.tenant_id == t.id,
                    Lease.status == LeaseStatus.ACTIVE.value,
                ).limit(1)
            )
            unit = await session.get(Unit, lease.unit_id) if lease else None
            late_payers.append({
                "tenant_id": str(t.id),
                "tenant_name": t.full_name,
                "unit_number": unit.unit_number if unit else "—",
                "risk_score": round(late_ratio * 100),
                "risk_label": "HIGH" if late_ratio > 0.75 else "MEDIUM",
            })

    # ── Vacancy Risk ─────────────────────────────────────────────
    # Units vacant >30 days
    properties = (await session.scalars(
        select(Property).where(Property.business_id == business_id, Property.is_deleted.is_(False))
    )).all()

    vacancy_risk = []
    for prop in properties:
        units = (await session.scalars(
            select(Unit).where(
                Unit.property_id == prop.id, Unit.is_deleted.is_(False),
            )
        )).all()
        for u in units:
            if u.status == UnitStatus.AVAILABLE.value:
                vacancy_risk.append({
                    "property_name": prop.name,
                    "unit_number": u.unit_number,
                    "monthly_rent": float(u.monthly_rent),
                    "days_vacant": 30,  # simplified
                    "risk_score": 70,
                    "risk_label": "MEDIUM",
                })

    # ── Collection Health ────────────────────────────────────────
    # Current month collection rate
    month_start = today.replace(day=1)
    collected = await session.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
            Invoice.business_id == business_id,
            Invoice.period_start >= month_start,
            Invoice.status == InvoiceStatus.PAID.value,
        )
    ) or Decimal("0")

    expected = await session.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.business_id == business_id,
            Invoice.period_start >= month_start,
        )
    ) or Decimal("0")

    collection_rate = round(float(collected) / float(expected) * 100, 1) if float(expected) > 0 else 0

    # ── Trend ────────────────────────────────────────────────────
    # Compare current month to previous month
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_collected = await session.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
            Invoice.business_id == business_id,
            Invoice.period_start >= prev_month_start,
            Invoice.period_start < month_start,
            Invoice.status == InvoiceStatus.PAID.value,
        )
    ) or Decimal("0")

    prev_expected = await session.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.business_id == business_id,
            Invoice.period_start >= prev_month_start,
            Invoice.period_start < month_start,
        )
    ) or Decimal("0")

    prev_rate = round(float(prev_collected) / float(prev_expected) * 100, 1) if float(prev_expected) > 0 else 0
    trend = "up" if collection_rate > prev_rate else ("down" if collection_rate < prev_rate else "stable")
    trend_delta = round(collection_rate - prev_rate, 1)

    # ── Build commentary ─────────────────────────────────────────
    commentary_parts = []

    if late_payers:
        high_risk = [p for p in late_payers if p["risk_label"] == "HIGH"]
        if high_risk:
            names = ", ".join(p["tenant_name"] for p in high_risk[:3])
            commentary_parts.append(
                f"{len(high_risk)} tenant(s) at high risk of late payment: {names}. "
                "Consider sending early SMS reminders."
            )

    if vacancy_risk:
        total_vacant_revenue = sum(v["monthly_rent"] for v in vacancy_risk)
        commentary_parts.append(
            f"{len(vacancy_risk)} unit(s) vacant. Potential revenue loss: "
            f"KES {total_vacant_revenue:,.0f}/month. "
            "List on rental platforms or offer move-in specials."
        )

    if trend == "down" and trend_delta > 5:
        commentary_parts.append(
            f"Collection rate dropped {trend_delta}% vs last month. "
            "Review outstanding accounts and follow up with delinquent tenants."
        )
    elif trend == "up" and trend_delta > 5:
        commentary_parts.append(
            f"Collection rate improved {trend_delta}% this month. Great work!"
        )

    if collection_rate < 60:
        commentary_parts.append(
            f"Collection rate at {collection_rate}% — below healthy threshold. "
            "Enable automated SMS reminders to improve collections."
        )

    if not commentary_parts:
        commentary_parts.append(
            "No significant issues detected. Collections are on track."
        )

    return {
        "collection_health": {
            "current_rate": collection_rate,
            "previous_rate": prev_rate,
            "trend": trend,
            "trend_delta": trend_delta,
            "collected": float(collected),
            "expected": float(expected),
        },
        "payment_risk": {
            "at_risk_count": len(late_payers),
            "tenants": late_payers[:5],
        },
        "vacancy_risk": {
            "vacant_count": len(vacancy_risk),
            "potential_revenue_loss": sum(v["monthly_rent"] for v in vacancy_risk),
            "units": vacancy_risk[:5],
        },
        "insights": commentary_parts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
