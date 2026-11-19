from __future__ import annotations

import pytest

from tests.conftest import requires_db


@requires_db
async def test_an_owner_can_create_a_property_and_a_unit(client, businesses, db_session):
    first, _ = businesses

    res = await client.post(
        "/api/v1/properties",
        json={"name": "Sunset Hostel", "address": "Kasarani", "property_type": "hostel"},
        headers=first.bearer,
    )
    assert res.status_code == 201 or res.status_code == 200, res.text
    prop = res.json()
    assert prop["name"] == "Sunset Hostel"

    res = await client.post(
        f"/api/v1/properties/{prop['id']}/units",
        json={
            "unit_number": "A1",
            "unit_type": "room",
            "monthly_rent": 8000,
            "deposit_amount": 8000,
            "max_occupants": 1,
        },
        headers=first.bearer,
    )
    assert res.status_code in (200, 201), res.text
    unit = res.json()
    assert unit["unit_number"] == "A1"
    assert float(unit["monthly_rent"]) == 8000.0

    res = await client.get(
        f"/api/v1/properties/{prop['id']}/units",
        headers=first.bearer,
    )
    assert res.status_code == 200
    assert any(u["id"] == unit["id"] for u in res.json())


@requires_db
async def test_an_owner_cannot_add_a_unit_to_another_business_property(
    client, businesses, db_session
):
    first, second = businesses

    res = await client.post(
        "/api/v1/properties",
        json={"name": "Foreign", "property_type": "hostel"},
        headers=first.bearer,
    )
    prop_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/properties/{prop_id}/units",
        json={"unit_number": "X1", "monthly_rent": 5000},
        headers=second.bearer,
    )
    assert res.status_code == 404