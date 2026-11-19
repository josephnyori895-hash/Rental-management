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
