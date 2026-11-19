"""
Many caretakers, each responsible for different properties.

Caretakers are `User` rows with the agent role, and the building they run is
`Property.manager_id`. Every caretaker notification used to ask for "the first
active agent in the business", so a ticket from one building went to whichever
caretaker happened to be created first. The fix is to resolve the recipient
through the property — and when a property has no caretaker, to tell the owner
rather than a stranger.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from tests.conftest import requires_db


async def _caretaker(session, business, name: str, phone: str):
    from app.models.business import User

    user = User(
        business_id=business.business.id,
        email=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}@caretakers.test",
        password_hash="not-used-in-these-tests",
        full_name=name,
        phone=phone,
        role="agent",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _second_property(session, business, manager=None):
    """Another building with its own occupied unit and an unpaid rent invoice."""
    from app.models.billing import Invoice
    from app.models.lease import Lease
    from app.models.property import Property, Unit
    from app.models.tenant import Tenant

    today = date.today()
    prop = Property(
        business_id=business.business.id,
        name="Bravo Block",
        manager_id=manager.id if manager is not None else None,
    )
    session.add(prop)
    await session.flush()

    unit = Unit(
        business_id=business.business.id,
        property_id=prop.id,
        unit_number="B1",
        status="occupied",
        monthly_rent=Decimal("12000"),
    )
    tenant = Tenant(
        business_id=business.business.id,
        full_name="Bravo Tenant",
        phone="254711000333",
        whatsapp_phone="254711000333",
        mpesa_phone="254711000333",
    )
    session.add_all([unit, tenant])
    await session.flush()

    lease = Lease(
        business_id=business.business.id,
        unit_id=unit.id,
        tenant_id=tenant.id,
        property_id=prop.id,
        start_date=today - timedelta(days=30),
        rent_amount=Decimal("12000"),
        deposit_amount=Decimal("0"),
        status="active",
    )
    session.add(lease)
    await session.flush()

    invoice = Invoice(
        business_id=business.business.id,
        lease_id=lease.id,
        tenant_id=tenant.id,
        unit_id=unit.id,
        property_id=prop.id,
        invoice_number="BRAVO-INV-0001",
        invoice_type="rent",
        period_start=today.replace(day=1),
        due_date=today - timedelta(days=2),
        amount=Decimal("12000"),
        paid_amount=Decimal("0"),
        balance=Decimal("12000"),
        status="pending",
    )
    session.add(invoice)
    await session.flush()

    return prop, unit, tenant, lease, invoice


async def _assign(client, business, prop, user) -> None:
    response = await client.patch(
        f"/api/v1/properties/{prop.id}/caretaker",
        headers=business.bearer,
        json={"user_id": str(user.id)},
    )
    assert response.status_code == 200, response.text


def _agent_bearer(user) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_the_arrears_digest_groups_a_caretakers_properties():
    """Pure formatting: one message, grouped, with the detail capped."""
    from app.notifications.templates import _build_wa_caretaker_arrears

    body = _build_wa_caretaker_arrears(
        [
            {
                "property": "Alpha Apartments",
                "unpaid": 2,
                "total": 30000.0,
                "units": ["A1 Ann: KES 15,000", "A2 Bob: KES 15,000"],
            },
            {
                "property": "Bravo Block",
                "unpaid": 1,
                "total": 12000.0,
                "units": ["B1 Cid: KES 12,000"],
            },
        ]
    )

    assert "3 unpaid" in body
    assert "Alpha Apartments: 2" in body
    assert "Bravo Block: 1" in body
    assert "A1 Ann" in body and "B1 Cid" in body


@requires_db
async def test_an_owner_assigns_a_caretaker_to_one_property(client, businesses, db_session):
    first, _ = businesses
    caretaker = await _caretaker(db_session, first, "Kelvin Mwangi", "254712300001")

    await _assign(client, first, first.property, caretaker)

    await db_session.refresh(first.property)
    assert first.property.manager_id == caretaker.id


@requires_db
async def test_a_caretaker_cannot_reassign_properties(client, businesses, db_session):
    first, _ = businesses
    caretaker = await _caretaker(db_session, first, "Kelvin Mwangi", "254712300002")

    response = await client.patch(
        f"/api/v1/properties/{first.property.id}/caretaker",
        headers=_agent_bearer(caretaker),
        json={"user_id": None},
    )

    assert response.status_code == 403


@requires_db
async def test_a_ticket_notifies_only_the_caretaker_of_that_property(
    client, businesses, db_session
):
    from app.notifications.inbound_tenant import _cmd_tenant_report
    from app.notifications.models import NotificationLog

    first, _ = businesses
    alpha_caretaker = await _caretaker(db_session, first, "Alpha Caretaker", "254712300010")
    bravo_caretaker = await _caretaker(db_session, first, "Bravo Caretaker", "254712300011")
    await _assign(client, first, first.property, alpha_caretaker)
    await _second_property(db_session, first, manager=bravo_caretaker)

    await _cmd_tenant_report(
        db_session, first.tenant, first.business.id, "burst pipe in the bathroom"
    )

    logs = (
        await db_session.scalars(
            select(NotificationLog).where(
                NotificationLog.template_name == "caretaker_ticket"
            )
        )
    ).all()
    assert [log.recipient for log in logs] == ["254712300010"]


@requires_db
async def test_a_renewal_notifies_only_the_caretaker_of_that_property(
    client, businesses, db_session
):
    from app.notifications.inbound_tenant import _cmd_tenant_renew
    from app.notifications.models import NotificationLog

    first, _ = businesses
    alpha_caretaker = await _caretaker(db_session, first, "Alpha Caretaker", "254712300020")
    bravo_caretaker = await _caretaker(db_session, first, "Bravo Caretaker", "254712300021")
    await _assign(client, first, first.property, alpha_caretaker)
    await _second_property(db_session, first, manager=bravo_caretaker)

    await _cmd_tenant_renew(db_session, first.tenant, first.business.id)

    logs = (
        await db_session.scalars(
            select(NotificationLog).where(
                NotificationLog.template_name == "caretaker_renewal_request"
            )
        )
    ).all()
    assert [log.recipient for log in logs] == ["254712300020"]


@requires_db
async def test_an_unassigned_property_falls_back_to_the_owner(
    client, businesses, db_session
):
    """No assignment must never mean "any caretaker will do"."""
    from app.notifications.inbound_tenant import _cmd_tenant_report
    from app.notifications.models import NotificationLog

    first, _ = businesses
    first.user.phone = "254700900001"
    bravo_caretaker = await _caretaker(db_session, first, "Bravo Caretaker", "254712300031")
    await _second_property(db_session, first, manager=bravo_caretaker)
    await db_session.flush()

    await _cmd_tenant_report(db_session, first.tenant, first.business.id, "leaking tap")

    logs = (
        await db_session.scalars(
            select(NotificationLog).where(
                NotificationLog.template_name == "caretaker_ticket"
            )
        )
    ).all()
    assert [log.recipient for log in logs] == ["254700900001"]


@requires_db
async def test_a_caretaker_can_only_enroll_into_their_own_properties(
    client, businesses, db_session
):
    from app.models.property import Unit
    from app.models.tenant import Tenant
    from app.notifications.inbound_user import _cmd_user_add

    first, _ = businesses
    alpha_caretaker = await _caretaker(db_session, first, "Alpha Caretaker", "254712300040")
    bravo_caretaker = await _caretaker(db_session, first, "Bravo Caretaker", "254712300041")
    await _assign(client, first, first.property, alpha_caretaker)
    prop_b, _, _, _, _ = await _second_property(db_session, first, manager=bravo_caretaker)

    unit_b = Unit(
        business_id=first.business.id,
        property_id=prop_b.id,
        unit_number="B2",
        status="available",
        monthly_rent=Decimal("9000"),
    )
    unit_a = Unit(
        business_id=first.business.id,
        property_id=first.property.id,
        unit_number="A2",
        status="available",
        monthly_rent=Decimal("9000"),
    )
    db_session.add_all([unit_b, unit_a])
    await db_session.flush()

    blocked = await _cmd_user_add(
        db_session, alpha_caretaker, first.business.id,
        "add 254799900011 b2 Intruder Tenant", "254712300040",
    )
    assert "not found" in blocked["message"].lower()
    assert await db_session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == "254799900011")
    ) is None

    allowed = await _cmd_user_add(
        db_session, alpha_caretaker, first.business.id,
        "add 254799900012 a2 New Tenant", "254712300040",
    )
    assert "added" in allowed["message"].lower()
    assert await db_session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == "254799900012")
    ) is not None


@requires_db
async def test_owner_assigns_a_caretaker_to_a_property_over_whatsapp(
    businesses, db_session
):
    """Every building can be staffed without opening the console."""
    from app.models.business import User
    from app.notifications.inbound_user import _cmd_owner_add_caretaker

    first, _ = businesses

    reply = await _cmd_owner_add_caretaker(
        db_session, first.user, first.business.id,
        "add caretaker 254712300070 Kevin Otieno IN Alpha Apartments",
        "254700000000",
    )

    assert "Alpha Apartments" in reply["message"]
    caretaker = await db_session.scalar(
        select(User).where(User.phone == "254712300070")
    )
    assert caretaker.role == "agent"
    await db_session.refresh(first.property)
    assert first.property.manager_id == caretaker.id

    # The same person can be given a second building without a new account.
    bravo, _, _, _, _ = await _second_property(db_session, first)
    reassigned = await _cmd_owner_add_caretaker(
        db_session, first.user, first.business.id,
        "add caretaker 254712300070 Kevin Otieno IN Bravo Block",
        "254700000000",
    )
    assert "Bravo Block" in reassigned["message"]
    await db_session.refresh(bravo)
    assert bravo.manager_id == caretaker.id


@requires_db
async def test_each_caretaker_gets_one_digest_for_their_own_property(
    client, businesses, db_session
):
    from app.core.scheduler import run_reminder_sweep
    from app.notifications.models import NotificationLog

    first, _ = businesses
    alpha_caretaker = await _caretaker(db_session, first, "Alpha Caretaker", "254712300050")
    bravo_caretaker = await _caretaker(db_session, first, "Bravo Caretaker", "254712300051")
    await _assign(client, first, first.property, alpha_caretaker)
    await _second_property(db_session, first, manager=bravo_caretaker)

    await run_reminder_sweep(db_session)

    digests = (
        await db_session.scalars(
            select(NotificationLog).where(
                NotificationLog.template_name == "caretaker_arrears"
            )
        )
    ).all()
    assert {log.recipient for log in digests} == {"254712300050", "254712300051"}

    alpha_body = next(log.body for log in digests if log.recipient == "254712300050")
    bravo_body = next(log.body for log in digests if log.recipient == "254712300051")
    assert "Alpha Apartments" in alpha_body
    assert "Bravo Block" not in alpha_body
    assert "Bravo Block" in bravo_body
    assert "Alpha Apartments" not in bravo_body

    # Once a day: the sweep is idempotent, so a restart cannot nag twice.
    await run_reminder_sweep(db_session)
    again = (await db_session.scalars(
        select(NotificationLog).where(
            NotificationLog.template_name == "caretaker_arrears"
        )
    )).all()
    assert len(again) == 2


@requires_db
async def test_one_caretaker_on_two_properties_gets_a_single_digest(
    client, businesses, db_session
):
    from app.core.scheduler import run_reminder_sweep
    from app.notifications.models import NotificationLog

    first, _ = businesses
    caretaker = await _caretaker(db_session, first, "Both Blocks", "254712300060")
    await _assign(client, first, first.property, caretaker)
    await _second_property(db_session, first, manager=caretaker)

    await run_reminder_sweep(db_session)

    digests = (
        await db_session.scalars(
            select(NotificationLog).where(
                NotificationLog.template_name == "caretaker_arrears"
            )
        )
    ).all()
    assert len(digests) == 1
    assert "Alpha Apartments" in digests[0].body
    assert "Bravo Block" in digests[0].body
