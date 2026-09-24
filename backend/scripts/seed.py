"""
RENTAL OS — Seed script

Creates a demo business, an owner, a caretaker (agent), two hostels with rooms,
and a mix of paid / unpaid / vacant rooms so the owner board is meaningful.

Also back-fills 6 months of monthly rent invoices per occupied unit so the
Business Console performance-history chart has real data.

Run:  PYTHONPATH=. ./venv/bin/python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.business import Business, SubscriptionTier, User, UserRole
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyType, Unit, UnitStatus
from app.models.tenant import Tenant


def _month_start(offset: int) -> date:
    """First day of the month `offset` months before today (offset<=0 = current)."""
    today = date.today()
    y, mo = today.year, today.month - offset
    while mo <= 0:
        mo += 12
        y -= 1
    return date(y, mo, 1)


async def main() -> None:
    random.seed(42)
    async with async_session_factory() as s:
        # Idempotent: wipe any prior demo business (cascades to all children).
        await s.execute(text("DELETE FROM businesses"))
        await s.commit()

        biz = Business(
            name="Nyorii Hostels",
            slug="nyorii-hostels",
            owner_id=uuid.uuid4(),
            subscription_tier=SubscriptionTier.BASIC.value,
        )
        s.add(biz)
        await s.flush()

        owner = User(
            business_id=biz.id,
            email="owner@rental.dev",
            password_hash=hash_password("rental1234"),
            full_name="Nyorii Owner",
            role=UserRole.OWNER.value,
            is_active=True,
        )
        caretaker = User(
            business_id=biz.id,
            email="caretaker@rental.dev",
            password_hash=hash_password("rental1234"),
            full_name="Caretaker Kim",
            phone="0711000000",
            role=UserRole.AGENT.value,
            pin_hash=hash_password("1234"),
            is_active=True,
        )
        s.add_all([owner, caretaker])
        await s.flush()
        biz.owner_id = owner.id

        hostels = [
            ("Sunrise Hostel", PropertyType.HOSTEL.value, 4000.0, 12),
            ("Moonlight Hostel", PropertyType.HOSTEL.value, 5000.0, 18),
        ]

        HISTORY_MONTHS = 6

        for hname, htype, rent, nunits in hostels:
            prop = Property(
                business_id=biz.id,
                name=hname,
                property_type=htype,
                address=f"{hname} Street",
            )
            s.add(prop)
            await s.flush()
            for i in range(1, nunits + 1):
                unit_no = f"{hname[0]}{i:02d}"
                unit = Unit(
                    business_id=biz.id,
                    property_id=prop.id,
                    unit_number=unit_no,
                    unit_type="room",
                    status=UnitStatus.AVAILABLE.value,
                    monthly_rent=Decimal(str(rent)),
                    max_occupants=1,
                )
                s.add(unit)
                await s.flush()

                if random.random() > 0.7:
                    continue  # ~30% vacant

                unit.status = UnitStatus.OCCUPIED.value
                first = random.choice([
                    "John", "Grace", "Peter", "Faith", "David", "Esther", "James", "Mary",
                    "Samuel", "Sarah", "Daniel", "Ruth", "Joseph", "Hannah", "Paul", "Elizabeth",
                    "George", "Jane", "Patrick", "Margaret", "Michael", "Alice", "Kevin", "Diana",
                    "Brian", "Catherine", "Thomas", "Dorothy", "Chris", "Agnes", "Mark", "Lucy",
                    "Alex", "Monica", "Eric", "Nancy", "Francis", "Ann", "Timothy", "Joy",
                ])
                surname = random.choice([
                    "Kamau", "Wanjiku", "Ochieng", "Akinyi", "Muthoni", "Njoroge", "Atieno",
                    "Kiprop", "Chebet", "Mwangi", "Nyambura", "Otieno", "Waithera", "Kibet",
                    "Wambui", "Odhiambo", "Wangari", "Kiprono", "Njoki", "Omondi",
                    "Kariuki", "Wanjiru", "Ouma", "Kemunto", "Ndegwa", "Nyokabi", "Rotich",
                    "Jepkosgei", "Mwaura", "Wairimu", "Barasa", "Nekesa", "Kinyua", "Mumbi",
                    "Langat", "Jerotich", "Mutua", "Kasyoka", "Kipngetich", "Metet",
                ])
                full_name = f"{first} {surname}"
                tenant = Tenant(
                    business_id=biz.id,
                    full_name=full_name,
                    phone=f"07{random.randint(10000000, 99999999)}",
                    mpesa_phone=f"2547{random.randint(10000000, 99999999)}",
                )
                s.add(tenant)
                await s.flush()

                months_ago = random.randint(1, 14)
                start = date.today() - timedelta(days=30 * months_ago)
                lease = Lease(
                    business_id=biz.id,
                    unit_id=unit.id,
                    tenant_id=tenant.id,
                    property_id=prop.id,
                    start_date=start,
                    rent_amount=Decimal(str(rent)),
                    deposit_amount=Decimal(str(rent)),
                    payment_day=1,
                    payment_frequency="monthly",
                    status=LeaseStatus.ACTIVE.value,
                )
                s.add(lease)
                await s.flush()
                unit.current_lease_id = lease.id

                for back in range(HISTORY_MONTHS - 1, -1, -1):
                    ms = _month_start(back)
                    is_current = back == 0
                    # current month ~60% paid; historical months ~80% paid
                    paid = random.random() < (0.6 if is_current else 0.8)
                    inv = Invoice(
                        business_id=biz.id,
                        lease_id=lease.id,
                        tenant_id=tenant.id,
                        unit_id=unit.id,
                        property_id=prop.id,
                        invoice_type=InvoiceType.RENT.value,
                        period_start=ms,
                        period_end=ms + timedelta(days=30),
                        due_date=ms,
                        amount=Decimal(str(rent)),
                        paid_amount=Decimal(str(rent)) if paid else Decimal("0"),
                        balance=Decimal("0") if paid else Decimal(str(rent)),
                        status=InvoiceStatus.PAID.value if paid else InvoiceStatus.PENDING.value,
                    )
                    s.add(inv)

        await s.commit()
        print("SEED DONE")
        print("  business slug : nyorii-hostels")
        print("  owner login   : owner@rental.dev / rental1234")
        print("  caretaker pin : business slug 'nyorii-hostels' + PIN '1234'")
        print("  board         : ~70% occupied, ~60% of those paid (rest red), ~30% vacant")
        print(f"  history       : {HISTORY_MONTHS} months of invoices back-filled per unit")


if __name__ == "__main__":
    asyncio.run(main())
