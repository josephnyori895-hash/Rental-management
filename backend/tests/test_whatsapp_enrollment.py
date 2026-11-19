"""
WhatsApp enrollment, end to end.

The web console enrolls into a unit it already knows. WhatsApp does not: the
message carries a unit *number*, and the same number exists in every building.
Enrollment therefore has to resolve the property, raise the move-in invoices,
let the new tenant pay them, and activate the lease — otherwise "ADD" reserves
a unit nobody can ever pay for.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from tests.conftest import requires_db


async def _property_with_unit(session, business, name: str, unit_number: str):
    from app.models.property import Property, Unit

    prop = Property(business_id=business.business.id, name=name)
    session.add(prop)
    await session.flush()

    unit = Unit(
        business_id=business.business.id,
        property_id=prop.id,
        unit_number=unit_number,
        status="available",
        monthly_rent=Decimal("12000"),
    )
    session.add(unit)
    await session.flush()
    return prop, unit


def test_add_command_parses_an_optional_property_hint():
    from app.notifications.inbound_user import parse_add_command

    assert parse_add_command("ADD 254712345678 A1 James Kariuki") == (
        "254712345678", "A1", "James Kariuki", None,
    )
    assert parse_add_command(
        "add 254712345678 a1 James Kariuki in Greenview Apartments"
    ) == ("254712345678", "a1", "James Kariuki", "Greenview Apartments")
    assert parse_add_command("ADD 2547 A1") is None


@requires_db
async def test_an_ambiguous_unit_asks_which_property(businesses, db_session):
    """A1 already exists in the seeded property; a second A1 must not guess."""
    from app.models.tenant import Tenant
    from app.notifications.inbound_user import _cmd_user_add

    first, _ = businesses
    await _property_with_unit(db_session, first, "Greenview Apartments", "A1")

    reply = await _cmd_user_add(
        db_session, first.user, first.business.id,
        "add 254799900101 A1 Faith Wanjiru", "254700000000",
    )

    assert "more than one property" in reply["message"]
    assert "Greenview Apartments" in reply["message"]
    assert await db_session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == "254799900101")
    ) is None


@requires_db
async def test_a_qualified_add_enrolls_into_the_named_property(businesses, db_session):
    from app.models.billing import Invoice
    from app.models.lease import Lease, LeaseStatus
    from app.models.tenant import Tenant
    from app.notifications.inbound_user import _cmd_user_add

    first, _ = businesses
    greenview, unit = await _property_with_unit(
        db_session, first, "Greenview Apartments", "A1"
    )

    reply = await _cmd_user_add(
        db_session, first.user, first.business.id,
        "add 254799900102 A1 Faith Wanjiru IN Greenview", "254700000000",
    )

    assert "Greenview Apartments" in reply["message"]

    tenant = await db_session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == "254799900102")
    )
    lease = await db_session.scalar(select(Lease).where(Lease.tenant_id == tenant.id))
    assert lease.property_id == greenview.id
    assert lease.status == LeaseStatus.PENDING.value

    await db_session.refresh(unit)
    assert unit.status == "reserved"

    invoices = (
        await db_session.scalars(select(Invoice).where(Invoice.lease_id == lease.id))
    ).all()
    assert {inv.invoice_type for inv in invoices} == {"deposit", "rent"}
    assert {inv.description.split(" — ")[0] for inv in invoices} == {
        "Deposit", "First rent",
    }
    assert sum(float(inv.balance) for inv in invoices) == 24000.0


@requires_db
async def test_a_reserved_tenant_can_pay_and_the_lease_activates(businesses, db_session):
    from app.models.billing import Invoice
    from app.models.lease import Lease, LeaseStatus
    from app.models.tenant import Tenant
    from app.notifications.inbound_tenant import _cmd_tenant_balance, _cmd_tenant_pay
    from app.notifications.inbound_user import _cmd_user_add
    from app.payments.service import apply_payment

    first, _ = businesses
    _, unit = await _property_with_unit(db_session, first, "Greenview Apartments", "B7")

    await _cmd_user_add(
        db_session, first.user, first.business.id,
        "add 254799900103 B7 Peter Otieno IN Greenview", "254700000000",
    )
    tenant = await db_session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == "254799900103")
    )
    lease = await db_session.scalar(select(Lease).where(Lease.tenant_id == tenant.id))
    invoices = {
        inv.invoice_type: inv
        for inv in (
            await db_session.scalars(
                select(Invoice).where(Invoice.lease_id == lease.id)
            )
        ).all()
    }

    # A pending tenant must be able to see and pay the move-in bill.
    first.business.mpesa_shortcode = "600600"
    await db_session.flush()
    pay_reply = await _cmd_tenant_pay(db_session, tenant, first.business.id)
    assert "No active lease" not in pay_reply["message"]
    assert "12,000" in pay_reply["message"]

    balance_reply = await _cmd_tenant_balance(db_session, tenant, first.business.id)
    assert "24,000" in balance_reply["message"]

    # Deposit alone is not enough to move in.
    await apply_payment(db_session, str(invoices["deposit"].id), invoices["deposit"].balance)
    await db_session.refresh(lease)
    assert lease.status == LeaseStatus.PENDING.value

    await apply_payment(db_session, str(invoices["rent"].id), invoices["rent"].balance)
    await db_session.refresh(lease)
    await db_session.refresh(unit)

    assert lease.status == LeaseStatus.ACTIVE.value
    assert unit.status == "occupied"
    assert unit.current_lease_id == lease.id
