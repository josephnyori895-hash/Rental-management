"""
Database-backed test fixtures.

Everything else in this suite runs without a database, deliberately. These
fixtures exist for the checks that cannot be honest without one — starting
with tenant isolation, which is enforced by a `business_id` filter duplicated
across every router and so has no single place to verify.

Tests run against a **scratch** database, never the development one. The URL
is derived from `DATABASE_URL` in `.env` with `_test` appended to the database
name, or set explicitly:

    TEST_DATABASE_URL=postgresql+asyncpg://imani:imani@localhost:5432/rental_test

If that database is unreachable, every test needing it is skipped — `pytest`
still passes on a machine with no PostgreSQL, which has been this suite's
contract from the start.
"""

from __future__ import annotations

import asyncio
import os
import re
import zlib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

CONNECT_TIMEOUT_SECONDS = 3
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
TEST_PASSWORD = "test-password"

_PASSWORD_HASH: str | None = None


def password_hash() -> str:
    """One bcrypt hash per process — hashing is deliberately slow, and the
    seeded users are not what these tests are exercising."""
    global _PASSWORD_HASH
    if _PASSWORD_HASH is None:
        from app.core.security import hash_password

        _PASSWORD_HASH = hash_password(TEST_PASSWORD)
    return _PASSWORD_HASH


def _dotenv_value(key: str) -> str | None:
    """Read one key from `.env` without booting the settings object."""
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _derive_test_url() -> str:
    """`DATABASE_URL` pointed at the `<name>_test` database."""
    base = _dotenv_value("DATABASE_URL") or ""
    if not base:
        return ""
    return re.sub(r"/([^/?]+)(\?.*)?$", r"/\1_test\2", base)


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _derive_test_url()

# `app.core.config` reads DATABASE_URL at import time, so redirect it before
# anything imports the app. Without this the tests would write to the
# development database.
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _make_engine():
    return create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"timeout": CONNECT_TIMEOUT_SECONDS},
    )


def _database_reachable() -> bool:
    if not TEST_DATABASE_URL:
        return False

    async def _probe() -> bool:
        engine = _make_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_probe())
    except Exception:
        return False


DB_AVAILABLE = _database_reachable()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="no test database reachable (set TEST_DATABASE_URL)",
)


async def _reset_schema() -> None:
    # Import the whole app first. Importing individual model packages is not
    # enough: `Document` (for example) is only registered once
    # `app.documents.router` is imported, so `drop_all` would then fail to
    # order tables it does not know about, and `create_all` would silently
    # leave that table out.
    import app.main  # noqa: F401
    from app.core.database import Base

    engine = _make_engine()
    try:
        async with engine.begin() as conn:
            # Dropping the schema outright is order-independent and cannot be
            # tripped by a table the metadata does not know about yet.
            await conn.exec_driver_sql("DROP SCHEMA public CASCADE")
            await conn.exec_driver_sql("CREATE SCHEMA public")
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> None:
    """Build a clean schema once. No-op when there is no database."""
    if DB_AVAILABLE:
        asyncio.run(_reset_schema())


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is always rolled back.

    The connection joins with `create_savepoint`, so a route's own
    `session.commit()` only releases a savepoint and cannot escape the outer
    rollback — the scratch database is left exactly as it was found.
    """
    if not DB_AVAILABLE:
        pytest.skip("no test database reachable")

    engine = _make_engine()
    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """The real ASGI app, with its session dependency bound to the test transaction."""
    from app.core.database import get_session
    from app.main import app

    async def _use_test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _use_test_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()


# ── Seeding ────────────────────────────────────────────────────────


@dataclass
class SeededBusiness:
    """A fully populated business: one property, unit, tenant, lease and money."""

    label: str
    business: object
    user: object
    property: object
    unit: object
    tenant: object
    lease: object
    invoice: object
    payment: object
    unmatched_payment: object
    expense: object
    ticket: object
    rate: object
    reading: object
    notification: object
    document: object
    accounts: list

    @property
    def bearer(self) -> dict[str, str]:
        from app.core.security import create_access_token

        return {"Authorization": f"Bearer {create_access_token(str(self.user.id))}"}

    def owned_ids(self) -> list[UUID]:
        """Every id this business owns. The leak detector's payload."""
        return [
            self.property.id,
            self.unit.id,
            self.tenant.id,
            self.lease.id,
            self.invoice.id,
            self.payment.id,
            self.unmatched_payment.id,
            self.expense.id,
            self.ticket.id,
            self.rate.id,
            self.reading.id,
            self.notification.id,
            self.document.id,
            *[account.id for account in self.accounts],
        ]



async def seed_business(session: AsyncSession, label: str) -> SeededBusiness:
    """Create one complete, realistic business. Commits nothing itself."""
    from app.accounting.models import ChartOfAccount
    from app.accounting.service import ensure_system_accounts
    from app.documents.models import Document
    from app.models.billing import Invoice, InvoiceStatus, Payment
    from app.models.business import Business, User, UserRole
    from app.models.expense import Expense, ExpenseCategory
    from app.models.lease import Lease, LeaseStatus
    from app.models.maintenance import MaintenanceTicket
    from app.models.property import Property, Unit, UnitStatus
    from app.models.tenant import Tenant
    from app.models.utilities import MeterReading, SplitMethod, UtilityRate, UtilityType
    from app.notifications.models import NotificationLog

    today = date.today()
    phone = f"2547{abs(zlib.crc32(label.encode())) % 10_000_000:07d}"
    # `businesses.owner_id` has no FK to users, and users need a business, so
    # the owner is patched in right after the user row exists.
    business = Business(
        name=f"{label} Holdings",
        slug=f"{label}-holdings-{today.isoformat()}",
        owner_id=uuid4(),
    )
    session.add(business)
    await session.flush()

    user = User(
        business_id=business.id,
        email=f"owner@{label}.test",
        password_hash=password_hash(),
        full_name=f"{label.title()} Owner",
        role=UserRole.OWNER.value,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    business.owner_id = user.id

    property_ = Property(
        business_id=business.id,
        name=f"{label.title()} Apartments",
        address=f"{label} Road, Nairobi",
        is_deleted=False,
    )
    session.add(property_)
    await session.flush()

    tenant = Tenant(
        business_id=business.id,
        full_name=f"{label.title()} Tenant",
        phone=phone,
        whatsapp_phone=phone,
        mpesa_phone=phone,
        is_deleted=False,
    )
    session.add(tenant)
    await session.flush()

    unit = Unit(
        business_id=business.id,
        property_id=property_.id,
        unit_number=f"{label[0].upper()}1",
        status=UnitStatus.OCCUPIED.value,
        monthly_rent=Decimal("15000"),
        is_deleted=False,
    )
    session.add(unit)
    await session.flush()

    lease = Lease(
        business_id=business.id,
        unit_id=unit.id,
        tenant_id=tenant.id,
        property_id=property_.id,
        start_date=today - timedelta(days=90),
        end_date=today + timedelta(days=275),
        rent_amount=Decimal("15000"),
        deposit_amount=Decimal("15000"),
        status=LeaseStatus.ACTIVE.value,
    )
    session.add(lease)
    await session.flush()
    unit.current_lease_id = lease.id

    invoice = Invoice(
        business_id=business.id,
        lease_id=lease.id,
        tenant_id=tenant.id,
        unit_id=unit.id,
        property_id=property_.id,
        invoice_number=f"{label.upper()}-INV-0001",
        invoice_type="rent",
        period_start=today.replace(day=1),
        due_date=today - timedelta(days=5),
        amount=Decimal("15000"),
        paid_amount=Decimal("0"),
        balance=Decimal("15000"),
        status=InvoiceStatus.PENDING.value,
    )
    session.add(invoice)
    await session.flush()

    payment = Payment(
        business_id=business.id,
        invoice_id=invoice.id,
        lease_id=lease.id,
        tenant_id=tenant.id,
        amount=Decimal("5000"),
        method="mpesa",
        reference=f"{label.upper()}-PAY-0001",
        status="completed",
    )
    # A payment with no invoice attached — what the reconciliation endpoint
    # exists to surface, and the only thing that makes its test non-vacuous.
    unmatched_payment = Payment(
        business_id=business.id,
        invoice_id=None,
        lease_id=None,
        tenant_id=tenant.id,
        amount=Decimal("2000"),
        method="mpesa",
        reference=f"{label.upper()}-MPESA-ORPHAN",
        status="completed",
    )
    expense = Expense(
        business_id=business.id,
        property_id=property_.id,
        category=ExpenseCategory.REPAIRS.value,
        amount=Decimal("3200"),
        description=f"{label} plumbing repair",
        paid_at=today,
    )
    ticket = MaintenanceTicket(
        business_id=business.id,
        property_id=property_.id,
        unit_id=unit.id,
        tenant_id=tenant.id,
        title=f"{label} leaking tap",
        category="plumbing",
        priority="medium",
        status="open",
    )
    rate = UtilityRate(
        business_id=business.id,
        property_id=property_.id,
        unit_id=None,
        utility_type=UtilityType.WATER.value,
        rate_per_unit=Decimal("150"),
        fixed_charge=Decimal("200"),
        split_method=SplitMethod.METERED.value,
        is_active=True,
    )
    reading = MeterReading(
        business_id=business.id,
        property_id=property_.id,
        unit_id=unit.id,
        utility_type=UtilityType.WATER.value,
        reading_date=today,
        previous_reading=None,
        current_reading=Decimal("1200"),
        units_consumed=Decimal("0"),
        rate_per_unit=Decimal("150"),
        fixed_charge=Decimal("200"),
        amount=Decimal("0"),
        source="web",
    )
    notification = NotificationLog(
        business_id=business.id,
        tenant_id=tenant.id,
        channel="whatsapp",
        recipient=phone,
        template_name="rent_reminder",
        body=f"{label} rent reminder",
        status="sent",
        provider="console",
    )
    document = Document(
        business_id=business.id,
        tenant_id=tenant.id,
        lease_id=lease.id,
        category="receipt",
        original_name=f"{label}-receipt.pdf",
        stored_name=f"{label}-receipt.pdf",
        mime_type="application/pdf",
        file_size=2048,
        file_path=f"/tmp/{label}-receipt.pdf",
    )

    session.add_all(
        [payment, unmatched_payment, expense, ticket, rate, reading, notification, document]
    )

    await ensure_system_accounts(session, business.id)
    await session.flush()

    accounts = list(
        (
            await session.execute(
                select(ChartOfAccount).where(ChartOfAccount.business_id == business.id)
            )
        ).scalars().all()
    )

    return SeededBusiness(
        label=label,
        business=business,
        user=user,
        property=property_,
        unit=unit,
        tenant=tenant,
        lease=lease,
        invoice=invoice,
        payment=payment,
        unmatched_payment=unmatched_payment,
        expense=expense,
        ticket=ticket,
        rate=rate,
        reading=reading,
        notification=notification,
        document=document,
        accounts=list(accounts),
    )


@pytest.fixture
async def businesses(db_session: AsyncSession) -> tuple[SeededBusiness, SeededBusiness]:
    """Two independent operators, each with their own complete data set."""
    first = await seed_business(db_session, "alpha")
    second = await seed_business(db_session, "bravo")
    await db_session.flush()
    return first, second


async def enroll_tenant(
    session: AsyncSession,
    client: httpx.AsyncClient,
    business: SeededBusiness,
    *,
    rent: str = "12000",
    deposit: str = "15000",
    unit_number: str = "V9",
) -> dict:
    """Enroll a tenant into a fresh vacant unit through the real endpoint.

    Enrollment is the only path that raises rent and deposit invoices, so any
    test about how those invoices post has to go through it rather than
    inserting an Invoice directly — inserting one would prove nothing about the
    thing that was broken.
    """
    from app.models.property import Unit, UnitStatus

    unit = Unit(
        business_id=business.business.id,
        property_id=business.property.id,
        unit_number=unit_number,
        status=UnitStatus.AVAILABLE.value,
        monthly_rent=Decimal(rent),
    )
    session.add(unit)
    await session.flush()

    response = await client.post(
        "/api/v1/tenants/enroll",
        headers=business.bearer,
        json={
            "full_name": f"Enrolled {unit_number}",
            "unit_id": str(unit.id),
            "start_date": str(date.today()),
            "rent_amount": float(rent),
            "deposit_amount": float(deposit),
            "mpesa_phone": "254700111222",
        },
    )
    assert response.status_code == 201, response.text
    return {"unit": unit, "body": response.json()}
