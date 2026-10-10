"""
Utility revenue accounting — the part of this feature that was silently broken.

Utility invoices were created, tenants were billed, and the ledger received
**no journal entry at all**, because `auto_post_invoice` was asked for account
"4200" and no business has a 4200. `get_account_id_by_code` returned `None`
and the function returned without a sound.

Nothing in the earlier suite could see that, because every assertion stopped at
the invoice. So this file closes both halves of the gap:

  * a guard asserting that *every* account code the application resolves is
    one `DEFAULT_COA` actually provisions — the class of bug, not the instance;
  * a database-backed test that follows a real water reading all the way into
    `journal_entries` and checks which account was credited.

Only the second would have caught the original defect. The first is what stops
it being reintroduced on the next feature that needs an account.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.accounting.service import DEFAULT_COA
from app.billing.utilities import (
    UTILITY_FALLBACK_INCOME_CODE,
    UTILITY_INCOME_CODES,
    income_code_for,
)
from tests.conftest import requires_db

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
PROVISIONED_CODES = {row[0] for row in DEFAULT_COA}

# The account every utility charge must *not* land on. Rent is the line an
# operator looks at first, so a mislabelled water charge hides in plain sight.
RENT_INCOME_CODE = "4000"


# ── The guard ──────────────────────────────────────────────────────


def test_every_utility_income_code_is_provisioned():
    """The mapping must point at accounts that exist, not at account names."""
    for utility_type, code in UTILITY_INCOME_CODES.items():
        assert code in PROVISIONED_CODES, (
            f"{utility_type} posts to {code}, which DEFAULT_COA never creates"
        )


def test_the_fallback_income_code_is_provisioned():
    assert UTILITY_FALLBACK_INCOME_CODE in PROVISIONED_CODES


def test_no_utility_charge_posts_to_rental_income():
    """A utility recharge is not rent; it must never be reported as such."""
    for utility_type in UTILITY_INCOME_CODES:
        assert income_code_for(utility_type) != RENT_INCOME_CODE
    assert income_code_for("water") != RENT_INCOME_CODE
    assert income_code_for(None) != RENT_INCOME_CODE
    assert income_code_for("a-utility-we-have-never-heard-of") != RENT_INCOME_CODE


def test_every_account_code_the_source_resolves_is_provisioned():
    """Scan the application for literal account codes and cross-check them.

    `get_account_id_by_code(session, business_id, "NNNN")` is the only way the
    codebase reaches a specific ledger account. A code here that `DEFAULT_COA`
    does not create is a posting that can never happen, which is exactly the
    defect this file exists for — so the check is against the real source text
    rather than a hand-maintained list, and it covers code not yet written.
    """
    literal_calls = re.compile(
        r"get_account_id_by_code\(\s*[^,]+,\s*[^,]+,\s*[\"'](\d{4})[\"']"
    )
    found: dict[str, list[str]] = {}
    for path in sorted(APP_ROOT.rglob("*.py")):
        for code in literal_calls.findall(path.read_text(encoding="utf-8")):
            found.setdefault(code, []).append(path.name)

    assert found, "expected to find literal account-code lookups to check"

    unresolved = {code: files for code, files in found.items() if code not in PROVISIONED_CODES}
    assert not unresolved, (
        "these account codes are looked up but never provisioned, so those "
        f"postings silently do nothing: {unresolved}"
    )


def test_no_call_site_hardcodes_an_income_code():
    """Every `income_code=` must come from the resolver.

    A literal here is how the original defect got in: one hardcoded "4200" in
    a call site, invisible to every assertion that stopped at the invoice. The
    WhatsApp billing branch in particular is not reached by the dispatcher
    tests, which stop at "no property set up", so a wrong code there would
    otherwise never be exercised. Parsed with `ast` rather than a regex so a
    reformatted call cannot slip past.
    """
    import ast

    offenders: list[str] = []
    seen = 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name != "auto_post_invoice":
                continue
            seen += 1
            for keyword in node.keywords:
                if keyword.arg != "income_code":
                    continue
                value = keyword.value
                if isinstance(value, ast.Call):
                    # `income_code_for(x)` is a Name; a module-qualified call
                    # would be an Attribute. Accept either spelling.
                    resolver = getattr(value.func, "attr", None) or getattr(
                        value.func, "id", None
                    )
                else:
                    resolver = None
                if resolver != "income_code_for":
                    offenders.append(f"{path.name}:{node.lineno}")

    assert seen > 0, "expected to find auto_post_invoice call sites"
    assert not offenders, (
        "these pass a hardcoded income_code instead of income_code_for(): "
        f"{offenders}"
    )


def test_the_removed_placeholder_code_is_gone_from_the_source():
    """`UTILITY_INCOME_CODE = "4200"` must not come back anywhere."""
    stale = [
        path.name
        for path in sorted(APP_ROOT.rglob("*.py"))
        if "UTILITY_INCOME_CODE " in path.read_text(encoding="utf-8")
        or "UTILITY_INCOME_CODE," in path.read_text(encoding="utf-8")
    ]
    assert not stale, f"dead placeholder constant still referenced in {stale}"


@pytest.mark.parametrize(
    ("utility_type", "expected"),
    [
        ("water", "4030"),
        ("electricity", "4040"),
        ("service_charge", "4010"),
        ("gas", UTILITY_FALLBACK_INCOME_CODE),
        ("wifi", UTILITY_FALLBACK_INCOME_CODE),
        ("garbage", UTILITY_FALLBACK_INCOME_CODE),
        ("other", UTILITY_FALLBACK_INCOME_CODE),
    ],
)
def test_income_code_for_maps_each_utility(utility_type, expected):
    assert income_code_for(utility_type) == expected


def test_income_code_lookup_is_case_insensitive_and_defaults_safely():
    assert income_code_for("WATER") == income_code_for("water")
    assert income_code_for(None) == UTILITY_FALLBACK_INCOME_CODE
    assert income_code_for("") == UTILITY_FALLBACK_INCOME_CODE


# ── The silent drop ────────────────────────────────────────────────


class _Account:
    def __init__(self, account_id):
        self.id = account_id


class _StubSession:
    """Just enough session for `get_account_id_by_code`'s single `scalar` call."""

    def __init__(self, results):
        self._results = list(results)

    async def scalar(self, _query):
        return self._results.pop(0)


def _invoice(amount="100.00"):
    return SimpleNamespace(
        id=uuid4(),
        business_id=uuid4(),
        property_id=uuid4(),
        tenant_id=uuid4(),
        amount=Decimal(amount),
        invoice_number="INV-TEST-1",
        created_at=datetime(2026, 9, 30, 10, 0, 0),
    )


async def test_a_missing_account_is_logged_rather_than_swallowed(monkeypatch, caplog):
    """An unresolvable account must be audible in the logs.

    The original code path returned silently, which is why the defect survived
    a full test suite and a manual review. Skipping the entry is defensible
    (the invoice still exists and can be reposted); doing it quietly is not.
    """
    from app.accounting import service

    posted = []

    async def _recorder(*args, **kwargs):
        posted.append(kwargs)

    monkeypatch.setattr(service, "post_journal_entry", _recorder)

    # Receivable resolves, income does not — the exact production shape.
    session = _StubSession([_Account(uuid4()), None])
    with caplog.at_level(logging.WARNING, logger="app.accounting.service"):
        await service.auto_post_invoice(session, _invoice(), income_code="4200")

    assert posted == [], "must not post an unbalanced or bogus entry"
    assert any(
        record.levelno == logging.WARNING and "4200" in record.getMessage()
        for record in caplog.records
    ), f"expected a warning naming the missing account, got {caplog.text!r}"


async def test_a_resolvable_account_is_posted_balanced(monkeypatch):
    """The happy path, asserted on the entry itself rather than a return value."""
    from app.accounting import service

    posted = []

    async def _recorder(session, business_id, entries, **kwargs):
        posted.append(entries)

    monkeypatch.setattr(service, "post_journal_entry", _recorder)

    receivable, income = uuid4(), uuid4()
    session = _StubSession([_Account(receivable), _Account(income)])
    await service.auto_post_invoice(session, _invoice("1250.00"), income_code="4030")

    assert len(posted) == 1
    debit, credit = posted[0]
    assert debit["account_id"] == receivable
    assert credit["account_id"] == income
    assert debit["debit"] == credit["credit"] == 1250.0


# ── The real thing ─────────────────────────────────────────────────


@requires_db
async def test_a_water_reading_reaches_the_ledger_as_utility_income(client, businesses, db_session):
    """End to end: reading → invoice → journal entry crediting Water Bill Income.

    This is the assertion the earlier suite lacked. It does not stop at the
    invoice; it checks the ledger actually moved, and moved to the right
    account.
    """
    from sqlalchemy import select

    from app.accounting.models import ChartOfAccount, JournalEntry

    first, _ = businesses

    response = await client.post(
        "/api/v1/billing/utilities/readings",
        headers=first.bearer,
        json={
            "unit_id": str(first.unit.id),
            "utility_type": "water",
            "previous_reading": 1200,
            "current_reading": 1300,
            "rate_per_unit": 150,
            "fixed_charge": 200,
            "bill": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["billed"] is True, body
    assert body["amount"] == 15200.0, body

    invoice_id = body["invoice_id"]
    assert invoice_id

    entries = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_id == invoice_id)
        )
    ).scalars().all()
    assert len(entries) == 2, f"expected a double entry, got {len(entries)}"

    accounts = {
        account.id: account
        for account in (
            await db_session.execute(
                select(ChartOfAccount).where(ChartOfAccount.business_id == first.business.id)
            )
        ).scalars().all()
    }

    credited = [entry for entry in entries if entry.credit > 0]
    debited = [entry for entry in entries if entry.debit > 0]
    assert len(credited) == 1 and len(debited) == 1

    assert accounts[credited[0].account_id].code == "4030", "must credit Water Bill Income"
    assert accounts[debited[0].account_id].code == "1100", "must debit Tenant Receivables"
    assert credited[0].credit == Decimal("15200.00")
    assert all(
        accounts[entry.account_id].code != RENT_INCOME_CODE for entry in entries
    ), "a water recharge must never be posted as rental income"


@requires_db
async def test_electricity_posts_to_its_own_account(client, businesses, db_session):
    """A second utility, to prove the mapping is per-type and not hardcoded."""
    from sqlalchemy import select

    from app.accounting.models import ChartOfAccount, JournalEntry

    first, _ = businesses

    response = await client.post(
        "/api/v1/billing/utilities/readings",
        headers=first.bearer,
        json={
            "unit_id": str(first.unit.id),
            "utility_type": "electricity",
            "previous_reading": 500,
            "current_reading": 600,
            "rate_per_unit": 25,
            "fixed_charge": 0,
            "bill": True,
        },
    )
    assert response.status_code == 201, response.text
    invoice_id = response.json()["invoice_id"]

    entries = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_id == invoice_id)
        )
    ).scalars().all()
    accounts = {
        account.id: account
        for account in (
            await db_session.execute(
                select(ChartOfAccount).where(ChartOfAccount.business_id == first.business.id)
            )
        ).scalars().all()
    }

    credited = [entry for entry in entries if entry.credit > 0]
    assert len(credited) == 1
    assert accounts[credited[0].account_id].code == "4040", "must credit Electricity Income"
    assert credited[0].credit == Decimal("2500.00")
