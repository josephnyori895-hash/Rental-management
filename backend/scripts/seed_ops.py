"""
RENTAL OS — Operations seed (idempotent-ish demo data)
Adds maintenance tickets + expenses for the existing demo business so the
Maintenance, Expenses, and Reports pages have real content.

Run:  PYTHONPATH=. ./venv/bin/python scripts/seed_ops.py
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text, select

from app.core.database import async_session_factory
from app.models.billing import Payment, Invoice, InvoiceStatus
from app.models.maintenance import MaintenanceTicket, TicketPriority, TicketStatus
from app.models.expense import Expense, ExpenseCategory
from app.models.property import Property, Unit
from app.models.tenant import Tenant


async def main() -> None:
    async with async_session_factory() as s:
        biz = await s.scalar(text("SELECT id FROM businesses LIMIT 1"))
        if not biz:
            print("No business found. Run seed.py first.")
            return
        biz_id = biz if isinstance(biz, uuid.UUID) else biz[0]

        props = (await s.scalars(
            select(Property).where(Property.business_id == biz_id)
        )).all()

        # Collect some units + tenants for realistic links
        units = (await s.scalars(
            select(Unit).where(Unit.business_id == biz_id, Unit.status == "occupied")
        )).all()
        # tenants link to units via active leases
        lease_rows = (await s.execute(
            text("SELECT tenant_id, unit_id FROM leases WHERE business_id = :b AND status='active'"),
            {"b": biz_id},
        )).all()
        tenant_by_unit = {lr.unit_id: lr.tenant_id for lr in lease_rows}

        # ── Maintenance tickets ──
        tickets = [
            ("Burst pipe in shared bathroom", "plumbing", TicketPriority.HIGH, TicketStatus.IN_PROGRESS, -2),
            ("Flickering corridor lights", "electrical", TicketPriority.MEDIUM, TicketStatus.OPEN, -1),
            ("Broken window latch M05", "structural", TicketPriority.LOW, TicketStatus.RESOLVED, -10),
            ("Pest control common area", "pest_control", TicketPriority.MEDIUM, TicketStatus.ASSIGNED, -3),
            ("Slow drain kitchen S03", "plumbing", TicketPriority.LOW, TicketStatus.OPEN, 0),
            ("WiFi router reset needed", "appliance", TicketPriority.URGENT, TicketStatus.RESOLVED, -14),
            ("Door lock replacement M11", "security", TicketPriority.HIGH, TicketStatus.CLOSED, -20),
        ]
        for idx, (title, cat, prio, status, days) in enumerate(tickets):
            unit = units[idx % len(units)] if units else None
            t = MaintenanceTicket(
                business_id=biz_id,
                property_id=unit.property_id if unit else (props[0].id if props else None),
                unit_id=unit.id if unit else None,
                tenant_id=tenant_by_unit.get(unit.id) if unit and unit.id in tenant_by_unit else None,
                title=title,
                description=f"Reported via caretaker app. {cat.title()} issue.",
                category=cat,
                priority=prio.value if hasattr(prio, "value") else prio,
                status=status.value if hasattr(status, "value") else status,
                tenant_visible=True,
                created_at=date.today() + timedelta(days=days),
            )
            s.add(t)

        # ── Expenses ──
        expenses = [
            ("repairs", 8500, "Plumber — burst pipe Sunrise", "Jua Kali Plumbers", -2),
            ("utilities", 12000, "KPLC tokens July", "KPLC", -3),
            ("water", 6000, "County water bill", "NCWSC", -5),
            ("wifi", 4500, "Safaricom Fibre monthly", "Safaricom", -6),
            ("cleaning", 7000, "Monthly common-area cleaning", "Tidy Crew", -8),
            ("security", 9000, "Guard service July", "SecureForce", -10),
            ("garbage", 2500, "Waste collection", "City Waste", -12),
            ("salary", 15000, "Caretaker stipend", "Caretaker Kim", -15),
            ("supplies", 3200, "Bulbs, locks, paint", "Hardware Mart", -7),
            ("repairs", 4300, "Window latch replacement", "Jua Kali Plumbers", -18),
        ]
        for cat, amt, desc, vendor, days in expenses:
            e = Expense(
                business_id=biz_id,
                property_id=props[0].id if props else None,
                category=cat,
                amount=amt,
                description=desc,
                vendor=vendor,
                paid_at=date.today() + timedelta(days=days),
            )
            s.add(e)

        # ── Inject a few PARTIAL payments so the building view shows amber windows ──
        # Pick a handful of occupied units and mark their latest invoice as partially paid.
        occ_units = (await s.scalars(
            select(Unit).where(Unit.business_id == biz_id, Unit.status == "occupied")
        )).all()
        import random as _r
        _r.seed(7)
        partial_targets = _r.sample(occ_units, min(4, len(occ_units)))
        for u in partial_targets:
            inv = await s.scalar(
                select(Invoice).where(Invoice.unit_id == u.id)
                .order_by(Invoice.period_start.desc().nullslast()).limit(1)
            )
            if inv and inv.status != InvoiceStatus.PAID.value:
                half = float(inv.amount) * 0.6
                inv.paid_amount = Decimal(str(round(half, 2)))
                inv.balance = inv.amount - inv.paid_amount
                inv.status = "partial"
                s.add(inv)

        await s.commit()
        print(f"Seeded {len(tickets)} maintenance tickets and {len(expenses)} expenses.")


if __name__ == "__main__":
    asyncio.run(main())
