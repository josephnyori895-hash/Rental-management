"""
Deposits post as a liability, not as income.

A security deposit is money held on the tenant's behalf. The schema always said
so — `InvoiceType.DEPOSIT`, a `deposit_refunds` table and a
`2100 Security Deposits Payable` account all existed, and the tenant detail
endpoint already assembled a whole `deposit` object from them. What was missing
was the write side: nothing ever created a deposit invoice or a refund, so the
endpoint always reported `status: "pending"`, `paid: 0`.

Worse, the one path that *could* produce a deposit invoice —
`POST /billing/bills` with `bill_type="deposit"` — posted it through
`auto_post_invoice` with the default income account, booking a liability as
rental income.

The policy this file pins:

    invoice raised    Dr 1100 Tenant Receivables   / Cr 2100 Deposits Payable
    deposit paid      Dr 1000 Cash                / Cr 1100 Tenant Receivables
    deposit refunded  Dr 2100 Deposits Payable    / Cr 1000 Cash

The first leg is implemented here. The payment leg already worked
(`auto_post_payment` is invoice-agnostic). The refund leg has no write path yet,
so it is not asserted against — `test_the_refund_leg_is_still_unbuilt` documents
that gap rather than pretending otherwise.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.accounting.service import (
    DEFAULT_COA,
    DEPOSIT_LIABILITY_CODE,
    LIABILITY_INVOICE_CODES,
    credit_account_code,
)
from tests.conftest import enroll_tenant, requires_db

PROVISIONED_CODES = {row[0] for row in DEFAULT_COA}
RENT_INCOME_CODE = "4000"
RECEIVABLE_CODE = "1100"


# ── The mapping ────────────────────────────────────────────────────


def test_a_deposit_invoice_credits_the_deposit_liability():
    assert credit_account_code("deposit", RENT_INCOME_CODE) == DEPOSIT_LIABILITY_CODE
    assert DEPOSIT_LIABILITY_CODE == "2100"


@pytest.mark.parametrize("spelling", ["deposit", "Deposit", "DEPOSIT", "  deposit  "])
def test_deposit_matching_tolerates_free_text(spelling):
    """`bill_type` is free text on the deprecated endpoint, so a deposit typed
    as "Deposit" must not quietly fall through to rental income."""
    assert credit_account_code(spelling, RENT_INCOME_CODE) == DEPOSIT_LIABILITY_CODE


@pytest.mark.parametrize(
    ("invoice_type", "income_code"),
    [
        ("rent", RENT_INCOME_CODE),
        ("utility", "4030"),
        ("late_fee", "4020"),
        ("water", RENT_INCOME_CODE),  # unrecognised types keep the caller's code
        (None, RENT_INCOME_CODE),
        ("", RENT_INCOME_CODE),
    ],
)
def test_non_deposit_invoices_keep_their_income_account(invoice_type, income_code):
    assert credit_account_code(invoice_type, income_code) == income_code


def test_every_liability_invoice_code_is_provisioned():
    for invoice_type, code in LIABILITY_INVOICE_CODES.items():
        assert code in PROVISIONED_CODES, (
            f"{invoice_type} deposits post to {code}, "
            "which DEFAULT_COA never creates"
        )


# ── The posting ────────────────────────────────────────────────────


class _Account:
    def __init__(self, account_id):
        self.id = account_id


class _StubSession:
    def __init__(self, results):
        self._results = list(results)

    async def scalar(self, _query):
        return self._results.pop(0)


def _invoice(invoice_type, amount="20000.00"):
    return SimpleNamespace(
        id=uuid4(),
        business_id=uuid4(),
        property_id=uuid4(),
        tenant_id=uuid4(),
        invoice_type=invoice_type,
        amount=Decimal(amount),
        invoice_number="INV-DEP-1",
        created_at=datetime(2026, 9, 30, 10, 0, 0),
    )


async def _capture(monkeypatch, invoice, receivable, credit):
    from app.accounting import service

    posted: list[list[dict]] = []

    async def _recorder(session, business_id, entries, **kwargs):
        posted.append(entries)

    monkeypatch.setattr(service, "post_journal_entry", _recorder)
    session = _StubSession([_Account(receivable), _Account(credit)])
    await service.auto_post_invoice(session, invoice)
    return posted


async def test_a_deposit_posts_debit_receivable_credit_liability(monkeypatch):
    receivable, liability = uuid4(), uuid4()
    posted = await _capture(monkeypatch, _invoice("deposit"), receivable, liability)

    debit, credit = posted[0]
    assert debit["account_id"] == receivable and debit["debit"] == 20000.0
    assert credit["account_id"] == liability and credit["credit"] == 20000.0


async def test_a_rent_invoice_still_posts_to_rental_income(monkeypatch):
    """The deposit rule must not capture ordinary rent."""
    receivable, income = uuid4(), uuid4()
    posted = await _capture(monkeypatch, _invoice("rent"), receivable, income)

    debit, credit = posted[0]
    assert debit["account_id"] == receivable
    assert credit["account_id"] == income
    assert credit["credit"] == 20000.0


# ── Against the real ledger ────────────────────────────────────────


async def _accounts_for(session, business_id):
    from app.accounting.models import ChartOfAccount

    rows = (
        await session.execute(
            select(ChartOfAccount).where(ChartOfAccount.business_id == business_id)
        )
    ).scalars().all()
    return {account.id: account for account in rows}


async def _entries_for(session, source_id):
    from app.accounting.models import JournalEntry

    return (
        await session.execute(
            select(JournalEntry).where(JournalEntry.source_id == source_id)
        )
    ).scalars().all()


async def _deposit_invoice_for(session, tenant_id):
    from app.models.billing import Invoice, InvoiceType

    return await session.scalar(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.invoice_type == InvoiceType.DEPOSIT.value,
        )
    )


@requires_db
async def test_an_enrolled_deposit_reaches_the_ledger_as_a_liability(
    client, businesses, db_session
):
    """End to end through the path that actually raises deposit invoices.

    Tenant enrollment creates the deposit invoice; it used to raise it without
    posting anything at all, and had it posted it would have credited rental
    income. Both halves are asserted here: the entry must exist, and it must
    credit the deposits-payable liability.
    """
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, deposit="20000")
    tenant_id = enrolled["body"]["tenant_id"]

    invoice = await _deposit_invoice_for(db_session, tenant_id)
    assert invoice is not None, "enrollment must raise a deposit invoice"

    entries = await _entries_for(db_session, invoice.id)
    assert len(entries) == 2, "the deposit invoice must reach the ledger"

    accounts = await _accounts_for(db_session, first.business.id)
    credited = [e for e in entries if e.credit > 0]
    debited = [e for e in entries if e.debit > 0]
    assert len(credited) == 1 and len(debited) == 1

    assert accounts[credited[0].account_id].code == DEPOSIT_LIABILITY_CODE, (
        "a deposit must credit Security Deposits Payable"
    )
    assert accounts[debited[0].account_id].code == RECEIVABLE_CODE
    assert credited[0].credit == Decimal("20000.00")
    assert all(
        accounts[entry.account_id].code != RENT_INCOME_CODE for entry in entries
    ), "a deposit must never be posted as rental income"


@requires_db
async def test_the_tenant_detail_endpoint_now_reports_a_real_deposit(
    client, businesses, db_session
):
    """The read side existed and was always empty; now it has something to read.

    Before any deposit invoice exists the endpoint reports `pending` with the
    full lease deposit outstanding. Once enrollment raises one it reports the
    invoice's real balance, so the UI stops showing an unpaid deposit that was
    never billed.
    """
    first, _ = businesses

    before = await client.get(f"/api/v1/tenants/{first.tenant.id}", headers=first.bearer)
    assert before.status_code == 200, before.text
    assert before.json()["deposit"]["status"] == "pending"
    assert before.json()["deposit"]["paid"] == 0

    enrolled = await enroll_tenant(db_session, client, first, deposit="15000")
    new_tenant_id = enrolled["body"]["tenant_id"]

    after = await client.get(
        f"/api/v1/tenants/{new_tenant_id}", headers=first.bearer
    )
    deposit = after.json()["deposit"]
    assert deposit["paid"] == 0
    assert deposit["balance"] == 15000.0
    assert deposit["status"] == "partial", (
        "a raised but unpaid deposit invoice is outstanding, not pending and "
        "not paid"
    )


def test_the_refund_leg_is_still_unbuilt():
    """Honest record of what this change does *not* do.

    `DepositRefund` is read by the tenant detail endpoint but nothing in the
    application creates one, so the refund posting — Dr 2100 / Cr 1000 — has no
    write path to hang off. Asserted as a known gap so that wiring one up is a
    deliberate act accompanied by its posting, not an omission discovered later
    in a balance sheet.
    """
    import ast
    from pathlib import Path

    app_root = Path(__file__).resolve().parents[1] / "app"
    writes = []
    for path in sorted(app_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in {"add", "add_all"}:
                    for arg in node.args:
                        if (
                            isinstance(arg, ast.Call)
                            and getattr(arg.func, "id", None) == "DepositRefund"
                        ):
                            writes.append(path.name)
    assert writes == [], (
        "DepositRefund is now created in "
        f"{writes} — post the refund leg (Dr 2100 / Cr 1000) in the same change, "
        "then delete this test"
    )
