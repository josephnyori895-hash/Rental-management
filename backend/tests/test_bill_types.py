"""
`bill_type` is validated, and it decides the revenue account.

`POST /billing/bills` accepted `bill_type` as **unvalidated free text** and
stored it verbatim as `invoice_type`, while posting to the default income
account. Two consequences, both silent:

  * a typo invented a new invoice type, so `"waterr"` was a category nobody
    could report on;
  * anything that spelled "deposit" booked a **liability as rental income**.

The endpoint is deprecated in favour of `POST /billing/utilities/readings` and
is a *utility* bill endpoint, so it now accepts exactly the utilities the rest
of the system knows about. Rent and deposit invoices come from tenant
enrollment. The income account is likewise derived from the bill type, so a
water bill posted here lands on the same account as one posted to the
replacement endpoint — previously the same word meant two different accounts.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.billing.router import ALLOWED_BILL_TYPES, CreateBillRequest
from app.billing.utilities import UTILITY_INCOME_CODES, income_code_for
from app.models.utilities import UtilityType
from tests.conftest import requires_db

RENT_INCOME_CODE = "4000"
RECEIVABLE_CODE = "1100"


def _request(bill_type: str):
    return CreateBillRequest(unit_id="any-unit", bill_type=bill_type, amount=100)


# ── What is allowed ────────────────────────────────────────────────


def test_every_utility_type_is_accepted():
    for kind in UtilityType:
        assert _request(kind.value).bill_type == kind.value


def test_the_allowed_set_is_exactly_the_utility_types():
    assert set(ALLOWED_BILL_TYPES) == {kind.value for kind in UtilityType}


@pytest.mark.parametrize("spelling", ["water", "Water", "WATER", "  water  "])
def test_case_and_whitespace_are_normalised_not_rejected(spelling):
    """A typed label is not an error just because of its casing."""
    assert _request(spelling).bill_type == "water"


@pytest.mark.parametrize("bad", ["waterr", "watre", "elecricity", "water bill", "", "  "])
def test_typos_are_rejected(bad):
    with pytest.raises(ValidationError):
        _request(bad)


def test_a_deposit_cannot_be_raised_here():
    """Deposits come from tenant enrollment, where they post to the liability.

    Accepting one here is what allowed a liability to be booked as income, so
    the endpoint refuses the word outright rather than relying on the posting
    layer to route it correctly.
    """
    with pytest.raises(ValidationError):
        _request("deposit")


@pytest.mark.parametrize("bad", ["rent", "late_fee", "invoice", "income"])
def test_non_utility_invoice_types_are_rejected(bad):
    with pytest.raises(ValidationError):
        _request(bad)


def test_the_error_names_the_allowed_values():
    with pytest.raises(ValidationError) as caught:
        _request("waterr")
    message = str(caught.value)
    assert "water" in message and "bill_type" in message


# ── Where the money lands ──────────────────────────────────────────


def test_every_bill_type_resolves_to_a_utility_income_account_not_rent():
    """A utility bill must never post to rental income."""
    for bill_type in ALLOWED_BILL_TYPES:
        code = income_code_for(bill_type)
        assert code != RENT_INCOME_CODE, f"{bill_type} would post to rental income"
        assert code in {"4010", "4030", "4040", "4050"}


def test_water_and_electricity_agree_with_the_replacement_endpoint():
    """Same word, same account — the inconsistency this change closed."""
    assert income_code_for("water") == UTILITY_INCOME_CODES["water"] == "4030"
    assert income_code_for("electricity") == UTILITY_INCOME_CODES["electricity"] == "4040"


# ── Against the real endpoint ──────────────────────────────────────


@requires_db
async def test_a_typo_is_refused_by_the_endpoint_and_creates_nothing(
    client, businesses, db_session
):
    """A 422 must not leave a half-created invoice behind."""
    from app.models.billing import Invoice

    first, _ = businesses
    before = len((await db_session.execute(select(Invoice))).scalars().all())

    response = await client.post(
        "/api/v1/billing/bills",
        headers=first.bearer,
        json={"unit_id": str(first.unit.id), "bill_type": "waterr", "amount": 500},
    )
    assert response.status_code == 422, response.text

    after = len((await db_session.execute(select(Invoice))).scalars().all())
    assert after == before, "a rejected bill must not create an invoice"


@requires_db
async def test_a_water_bill_posts_to_water_income_not_rent(client, businesses, db_session):
    """The point of the whole change, checked in the ledger."""
    from app.accounting.models import ChartOfAccount, JournalEntry

    first, _ = businesses

    response = await client.post(
        "/api/v1/billing/bills",
        headers=first.bearer,
        json={
            "unit_id": str(first.unit.id),
            "bill_type": "Water",
            "amount": 3500,
            "description": "Water top-up",
        },
    )
    assert response.status_code == 200, response.text
    invoice_id = response.json()["invoice_id"]

    entries = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_id == invoice_id)
        )
    ).scalars().all()
    assert len(entries) == 2

    accounts = {
        account.id: account
        for account in (
            await db_session.execute(
                select(ChartOfAccount).where(
                    ChartOfAccount.business_id == first.business.id
                )
            )
        ).scalars().all()
    }
    credited = [e for e in entries if e.credit > 0]
    debited = [e for e in entries if e.debit > 0]
    assert accounts[credited[0].account_id].code == "4030", "must credit Water Bill Income"
    assert accounts[debited[0].account_id].code == RECEIVABLE_CODE
    assert credited[0].credit == Decimal("3500.00")
    assert all(
        accounts[e.account_id].code != RENT_INCOME_CODE for e in entries
    ), "a water bill must never be posted as rental income"
