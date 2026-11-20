from __future__ import annotations

import uuid

from tests.conftest import requires_db


def _layout_body(unit_id: str) -> dict:
    return {
        "layout_config": {
            "version": 1,
            "building_type": "hostel",
            "sections": [
                {
                    "id": "block-a",
                    "name": "Block A",
                    "kind": "block",
                    "levels": [{"id": "g", "label": "Ground", "order": 0}],
                    "faces": [{"id": "front", "label": "Front", "orientation": "front"}],
                }
            ],
            "placements": [
                {
                    "unit_id": unit_id,
                    "section_id": "block-a",
                    "level_id": "g",
                    "face_id": "front",
                    "position": 0,
                }
            ],
        }
    }


@requires_db
async def test_an_owner_reads_their_own_units_and_rooms(client, businesses):
    first, _ = businesses

    for path in ("units", "rooms"):
        res = await client.get(
            f"/api/v1/properties/{first.property.id}/{path}", headers=first.bearer
        )
        assert res.status_code == 200, res.text
        payload = res.json()
        assert [row["unit_number"] for row in payload] == [first.unit.unit_number]


@requires_db
async def test_units_of_another_business_are_reported_missing(client, businesses):
    first, second = businesses

    for path in ("units", "rooms"):
        res = await client.get(
            f"/api/v1/properties/{first.property.id}/{path}", headers=second.bearer
        )
        assert res.status_code == 404, res.text
        assert res.json()["detail"] == "Property not found"
        assert str(first.unit.id) not in res.text


@requires_db
async def test_a_deleted_property_is_reported_missing(client, businesses, db_session):
    first, _ = businesses
    first.property.is_deleted = True
    await db_session.flush()

    for path in ("units", "rooms", "layout"):
        res = await client.get(
            f"/api/v1/properties/{first.property.id}/{path}", headers=first.bearer
        )
        assert res.status_code == 404, res.text


@requires_db
async def test_malformed_property_ids_are_refused_not_crashed(client, businesses):
    first, _ = businesses

    for path in ("units", "rooms", "layout"):
        res = await client.get(
            f"/api/v1/properties/not-a-uuid/{path}", headers=first.bearer
        )
        assert res.status_code == 422, res.text

    res = await client.post(
        "/api/v1/properties/not-a-uuid/units",
        json={"unit_number": "Z1", "unit_type": "room", "monthly_rent": 1000},
        headers=first.bearer,
    )
    assert res.status_code == 422, res.text


@requires_db
async def test_writes_persist_for_the_owning_business(client, businesses):
    first, _ = businesses

    res = await client.post(
        "/api/v1/properties",
        json={"name": "Riverbend Flats", "address": "Ngong", "property_type": "apartment"},
        headers=first.bearer,
    )
    assert res.status_code in (200, 201), res.text
    created = res.json()

    listed = await client.get("/api/v1/properties", headers=first.bearer)
    assert listed.status_code == 200
    assert created["id"] in [row["id"] for row in listed.json()]

    res = await client.post(
        f"/api/v1/properties/{created['id']}/units",
        json={
            "unit_number": "B7",
            "unit_type": "studio",
            "monthly_rent": 11500,
            "deposit_amount": 11500,
            "max_occupants": 2,
        },
        headers=first.bearer,
    )
    assert res.status_code in (200, 201), res.text
    unit = res.json()
    assert unit["unit_number"] == "B7"

    readback = await client.get(
        f"/api/v1/properties/{created['id']}/units", headers=first.bearer
    )
    assert [row["unit_number"] for row in readback.json()] == ["B7"]


@requires_db
async def test_layout_round_trips_and_is_scoped_to_the_property(client, businesses):
    first, _ = businesses
    body = _layout_body(str(first.unit.id))

    saved = await client.put(
        f"/api/v1/properties/{first.property.id}/layout",
        json=body,
        headers=first.bearer,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["property_id"] == str(first.property.id)

    fetched = await client.get(
        f"/api/v1/properties/{first.property.id}/layout", headers=first.bearer
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["layout_config"]["sections"][0]["id"] == "block-a"
    assert (
        fetched.json()["layout_config"]["placements"][0]["unit_id"]
        == str(first.unit.id)
    )


@requires_db
async def test_layout_rejects_a_unit_from_another_property(client, businesses):
    first, second = businesses

    res = await client.put(
        f"/api/v1/properties/{first.property.id}/layout",
        json=_layout_body(str(second.unit.id)),
        headers=first.bearer,
    )
    assert res.status_code == 422, res.text


@requires_db
async def test_layout_rejects_an_internal_space_linked_to_another_property(client, businesses):
    first, second = businesses
    body = _layout_body(str(first.unit.id))
    body["layout_config"]["placements"] = []
    body["layout_config"]["sections"][0]["levels"][0]["spaces"] = [{
        "id": "foreign-bedroom",
        "label": "Foreign bedroom",
        "kind": "bedroom",
        "rentable_unit_id": str(second.unit.id),
    }]

    res = await client.put(
        f"/api/v1/properties/{first.property.id}/layout",
        json=body,
        headers=first.bearer,
    )
    assert res.status_code == 422, res.text


@requires_db
async def test_caretaker_can_be_assigned_and_unassigned(client, businesses):
    first, _ = businesses

    res = await client.post(
        "/api/v1/auth/staff",
        json={
            "full_name": "Caretaker One",
            "email": "caretaker1@alpha-holdings.co.ke",
            "password": "caretaker123",
            "role": "agent",
        },
        headers=first.bearer,
    )
    assert res.status_code in (200, 201), res.text
    staff_id = res.json()["id"]

    assigned = await client.patch(
        f"/api/v1/properties/{first.property.id}/caretaker",
        json={"user_id": staff_id},
        headers=first.bearer,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["caretaker_id"] == staff_id

    cleared = await client.patch(
        f"/api/v1/properties/{first.property.id}/caretaker",
        json={"user_id": None},
        headers=first.bearer,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["caretaker_id"] is None


@requires_db
async def test_cross_business_writes_are_refused(client, businesses):
    first, second = businesses
    other = first.property.id

    cases = [
        await client.post(
            f"/api/v1/properties/{other}/units",
            json={"unit_number": "X1", "unit_type": "room", "monthly_rent": 900},
            headers=second.bearer,
        ),
        await client.patch(
            f"/api/v1/properties/{other}/caretaker",
            json={"user_id": None},
            headers=second.bearer,
        ),
        await client.put(
            f"/api/v1/properties/{other}/layout",
            json=_layout_body(str(second.unit.id)),
            headers=second.bearer,
        ),
    ]

    for res in cases:
        assert res.status_code == 404, res.text
        assert res.json()["detail"] == "Property not found"


@requires_db
async def test_unknown_property_ids_do_not_leak_other_business_records(client, businesses):
    _, second = businesses
    missing = str(uuid.uuid4())

    for path in ("units", "rooms", "layout"):
        res = await client.get(
            f"/api/v1/properties/{missing}/{path}", headers=second.bearer
        )
        assert res.status_code == 404, res.text
        assert str(second.unit.id) not in res.text


async def _extra_unit(db_session, business, property_id, unit_number: str):
    from decimal import Decimal

    from app.models.property import Unit, UnitStatus

    unit = Unit(
        business_id=business.id,
        property_id=property_id,
        unit_number=unit_number,
        status=UnitStatus.OCCUPIED.value,
        monthly_rent=Decimal("15000"),
        is_deleted=False,
    )
    db_session.add(unit)
    await db_session.flush()
    return unit


async def _lease(db_session, *, business_id, unit, tenant_id, property_id, notes=None):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.models.lease import Lease, LeaseStatus

    lease = Lease(
        business_id=business_id,
        unit_id=unit.id,
        tenant_id=tenant_id,
        property_id=property_id,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=335),
        rent_amount=Decimal("15000"),
        deposit_amount=Decimal("15000"),
        status=LeaseStatus.ACTIVE.value,
        notes=notes,
    )
    db_session.add(lease)
    await db_session.flush()
    return lease


async def _invoice(db_session, *, business_id, unit, tenant_id, property_id, lease_id, number):
    from datetime import date
    from decimal import Decimal

    from app.models.billing import Invoice, InvoiceStatus

    invoice = Invoice(
        business_id=business_id,
        lease_id=lease_id,
        tenant_id=tenant_id,
        unit_id=unit.id,
        property_id=property_id,
        invoice_number=number,
        invoice_type="rent",
        period_start=date.today().replace(day=1),
        due_date=date.today(),
        amount=Decimal("15000"),
        paid_amount=Decimal("15000"),
        balance=Decimal("0"),
        status=InvoiceStatus.PAID.value,
    )
    db_session.add(invoice)
    await db_session.flush()
    return invoice


@requires_db
async def test_rooms_ignore_a_lease_owned_by_another_business(
    client, businesses, db_session
):
    """The lease itself is foreign, so it is excluded before any join."""
    first, second = businesses

    unit = await _extra_unit(db_session, first.business, first.property.id, "FOREIGN-LEASE")
    await _lease(
        db_session,
        business_id=second.business.id,
        unit=unit,
        tenant_id=second.tenant.id,
        property_id=first.property.id,
        notes="SENSITIVE-NOTE-FOREIGN-LEASE",
    )

    res = await client.get(
        f"/api/v1/properties/{first.property.id}/rooms", headers=first.bearer
    )
    assert res.status_code == 200, res.text
    room = {row["unit_number"]: row for row in res.json()}["FOREIGN-LEASE"]

    assert room["tenant_id"] is None
    assert room["tenant_name"] is None
    assert room["tenant_phone"] is None
    assert room["lease_start"] is None
    assert room["lease_end"] is None
    assert room["duration_months"] is None
    assert room["condition_notes"] is None

    assert second.tenant.full_name not in res.text
    assert second.tenant.phone not in res.text
    assert "SENSITIVE-NOTE-FOREIGN-LEASE" not in res.text


@requires_db
async def test_rooms_withhold_lease_details_when_the_tenant_is_foreign(
    client, businesses, db_session
):
    """Lease belongs to A, tenant belongs to B: the tenant guard must fire,
    and no lease-derived value may be published alongside it."""
    first, second = businesses

    unit = await _extra_unit(db_session, first.business, first.property.id, "FOREIGN-TENANT")
    await _lease(
        db_session,
        business_id=first.business.id,
        unit=unit,
        tenant_id=second.tenant.id,
        property_id=first.property.id,
        notes="SENSITIVE-NOTE-FOREIGN-TENANT",
    )

    res = await client.get(
        f"/api/v1/properties/{first.property.id}/rooms", headers=first.bearer
    )
    assert res.status_code == 200, res.text
    room = {row["unit_number"]: row for row in res.json()}["FOREIGN-TENANT"]

    assert room["tenant_id"] is None
    assert room["tenant_name"] is None
    assert room["tenant_phone"] is None
    assert room["lease_start"] is None
    assert room["lease_end"] is None
    assert room["duration_months"] is None
    assert room["condition_notes"] is None

    body = res.text
    assert str(second.tenant.id) not in body
    assert second.tenant.full_name not in body
    assert second.tenant.phone not in body
    assert "SENSITIVE-NOTE-FOREIGN-TENANT" not in body


@requires_db
async def test_rooms_ignore_an_invoice_owned_by_another_business(
    client, businesses, db_session
):
    """Valid lease, foreign invoice: the tenant renders, the money does not."""
    first, second = businesses

    unit = await _extra_unit(db_session, first.business, first.property.id, "FOREIGN-INVOICE")
    lease = await _lease(
        db_session,
        business_id=first.business.id,
        unit=unit,
        tenant_id=first.tenant.id,
        property_id=first.property.id,
    )
    await _invoice(
        db_session,
        business_id=second.business.id,
        unit=unit,
        tenant_id=second.tenant.id,
        property_id=first.property.id,
        lease_id=lease.id,
        number="BRAVO-FOREIGN-0001",
    )

    res = await client.get(
        f"/api/v1/properties/{first.property.id}/rooms", headers=first.bearer
    )
    assert res.status_code == 200, res.text
    room = {row["unit_number"]: row for row in res.json()}["FOREIGN-INVOICE"]

    assert room["tenant_name"] == first.tenant.full_name
    assert room["invoice_status"] is None
    assert room["invoice_balance"] == 0.0
    assert room["total_paid"] == 0.0
    assert "BRAVO-FOREIGN-0001" not in res.text


@requires_db
async def test_rooms_render_a_correctly_linked_lease(client, businesses):
    """Positive control: the guard must not blank legitimate data."""
    first, _ = businesses

    res = await client.get(
        f"/api/v1/properties/{first.property.id}/rooms", headers=first.bearer
    )
    assert res.status_code == 200, res.text
    room = {row["unit_number"]: row for row in res.json()}[first.unit.unit_number]

    assert room["tenant_id"] == str(first.tenant.id)
    assert room["tenant_name"] == first.tenant.full_name
    assert room["tenant_phone"]
    assert room["lease_start"] is not None
    assert room["lease_end"] is not None
    assert room["duration_months"] is not None
    assert room["invoice_status"] is not None
