"""
Tenant isolation, against a real PostgreSQL database.

Every router scopes its own queries with a `business_id` filter written
independently in that file — 69 call sites across 15 routers. Nothing checks
that any individual filter is correct, so a missing one returns another
operator's tenants, invoices and arrears while every other test in this suite
still passes. That is what this file is for.

Two properties make these assertions non-vacuous, which matters more than the
assertions themselves:

  * each business owns a full data set, so "ours is present" can be asserted
    alongside "theirs is absent" — otherwise a 500 or an empty list would look
    like a pass;
  * each endpoint gets its own transaction and its own seed, so one failing
    query cannot poison the transaction and cascade into unrelated failures.

Requires a scratch database; see `tests/conftest.py`. Without one these tests
skip rather than fail.
"""

from __future__ import annotations

import pytest

from tests.conftest import requires_db

# Every one of these is scoped by a hand-written business_id filter somewhere.
# `/notifications/log`, `/documents/list` and `/reconciliation/unmatched` are
# only worth testing because the seed gives each business a row that the
# endpoint is designed to return — an empty list would prove nothing.
LIST_ENDPOINTS = [
    "/api/v1/properties",
    "/api/v1/tenants",
    "/api/v1/billing/invoices",
    "/api/v1/expenses",
    "/api/v1/maintenance/tickets",
    "/api/v1/payments/history",
    "/api/v1/accounts",
    "/api/v1/documents/list",
    "/api/v1/notifications/log",
    "/api/v1/reconciliation/unmatched",
    "/api/v1/analytics/insights",
    "/api/v1/reports/aged-receivables",
    "/api/v1/reports/rent-roll",
    "/api/v1/billing/utilities/rates",
    "/api/v1/billing/utilities/readings",
]


@requires_db
@pytest.mark.parametrize("path", LIST_ENDPOINTS)
async def test_list_returns_only_the_callers_own_rows(path, client, businesses):
    first, second = businesses

    response = await client.get(path, headers=first.bearer)
    assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text[:300]}"

    leaked = [str(i) for i in second.owned_ids() if str(i) in response.text]
    assert leaked == [], f"{path} exposed ids belonging to another business: {leaked}"

    ours = [str(i) for i in first.owned_ids() if str(i) in response.text]
    assert ours, f"{path} returned none of our own rows — the leak check above is vacuous"


@requires_db
async def test_dashboard_counts_only_the_callers_units(client, businesses):
    """No ids in this payload, so the leak check has to be the numbers."""
    first, _ = businesses

    response = await client.get("/api/v1/dashboard/owner/metrics", headers=first.bearer)
    assert response.status_code == 200

    body = response.json()
    assert body["total_units"] == 1, "counted units from another business"
    assert body["occupied"] == 1
    assert body["vacant"] == 0
    assert body["total_arrears"] == 15000.0, "summed another business's arrears"


@requires_db
async def test_owner_statement_totals_only_the_callers_books(client, businesses):
    first, _ = businesses

    response = await client.get("/api/v1/reports/owner-statement", headers=first.bearer)
    assert response.status_code == 200

    body = response.json()
    assert body["income"]["total_expected"] == 15000.0
    assert body["income"]["outstanding"] == 15000.0
    assert body["expenses"]["total"] == 3200.0


# ── Fetching another business's row by id ──────────────────────────


@requires_db
async def test_invoice_detail_is_404_for_another_business(client, businesses):
    first, second = businesses

    theirs = await client.get(
        f"/api/v1/billing/invoices/{second.invoice.id}", headers=first.bearer
    )
    assert theirs.status_code == 404, "another business's invoice was readable"

    ours = await client.get(
        f"/api/v1/billing/invoices/{first.invoice.id}", headers=first.bearer
    )
    assert ours.status_code == 200, "our own invoice must still be readable"
    assert ours.json()["invoice_number"] == "ALPHA-INV-0001"


# ── Writes must land in the authoring business ─────────────────────


@requires_db
async def test_a_created_expense_is_invisible_to_the_other_business(client, businesses, db_session):
    first, second = businesses

    created = await client.post(
        "/api/v1/expenses",
        headers=first.bearer,
        json={"category": "security", "amount": 777, "description": "isolation probe"},
    )
    assert created.status_code == 201, created.text[:300]
    expense_id = created.json()["id"]

    mine = await client.get("/api/v1/expenses", headers=first.bearer)
    assert expense_id in mine.text, "the expense we just created is missing from our own list"

    theirs = await client.get("/api/v1/expenses", headers=second.bearer)
    assert expense_id not in theirs.text, "a new expense leaked into another business"


@requires_db
async def test_a_bill_cannot_be_raised_against_another_businesss_unit(client, businesses):
    """The unit lookup is scoped, so another operator's unit is simply not found."""
    first, second = businesses

    response = await client.post(
        "/api/v1/billing/bills",
        headers=first.bearer,
        json={"unit_id": str(second.unit.id), "bill_type": "water", "amount": 100},
    )
    assert response.status_code == 404, "billed another business's unit"


@requires_db
async def test_a_utility_reading_cannot_be_recorded_against_another_businesss_unit(
    client, businesses
):
    first, second = businesses

    response = await client.post(
        "/api/v1/billing/utilities/readings",
        headers=first.bearer,
        json={
            "unit_id": str(second.unit.id),
            "utility_type": "water",
            "current_reading": 999,
        },
    )
    assert response.status_code == 404


# ── The token decides the business, not the request ────────────────


@requires_db
async def test_an_unknown_or_foreign_token_is_rejected(client, businesses):
    first, _ = businesses

    assert (await client.get("/api/v1/tenants")).status_code == 401
    assert (
        await client.get("/api/v1/tenants", headers={"Authorization": "Bearer not-a-token"})
    ).status_code == 401


# ── Billing pagination & deprecation (were broken) ─────────────────


@requires_db
async def test_invoice_total_counts_every_matching_row_not_the_page(client, businesses):
    """`total` used to be the page length, so pagination could never work."""
    first, second = businesses

    # A second invoice for this business only.
    created = await client.post(
        "/api/v1/billing/bills",
        headers=first.bearer,
        json={"unit_id": str(first.unit.id), "bill_type": "water", "amount": 800},
    )
    assert created.status_code == 200

    page = await client.get("/api/v1/billing/invoices?limit=1", headers=first.bearer)
    assert page.status_code == 200
    body = page.json()

    assert len(body["invoices"]) == 1, "limit was ignored"
    assert body["total"] == 2, "total is the page size, not the number of matching invoices"
    assert body["limit"] == 1 and body["offset"] == 0

    # The count must respect the other filters too, and stay scoped to us.
    # The other business also has an invoice; a leaking count would say 3.
    paid = await client.get("/api/v1/billing/invoices?status=paid", headers=first.bearer)
    assert paid.json()["total"] == 0
    assert paid.json()["invoices"] == []


@requires_db
async def test_the_superseded_bill_endpoint_says_so_in_its_headers(client, businesses):
    first, _ = businesses

    response = await client.post(
        "/api/v1/billing/bills",
        headers=first.bearer,
        json={"unit_id": str(first.unit.id), "bill_type": "water", "amount": 250},
    )

    # Still functional — deprecating must not break existing clients.
    assert response.status_code == 200
    assert response.json()["invoice_id"]
    assert response.headers["deprecation"] == "true"
    assert "successor-version" in response.headers["link"]
    assert "/billing/utilities/readings" in response.headers["link"]
