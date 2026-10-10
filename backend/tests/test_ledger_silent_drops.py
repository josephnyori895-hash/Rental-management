"""
Every ledger posting path, audited for the same failure that broke utilities.

The utility defect was not an arithmetic bug. It was a posting that could not
resolve its account and **returned without a sound**, inside a caller that
wrapped it in a bare `except Exception: pass`. Two independent silencers, and
between them an entire revenue stream went missing while every test passed.

So the audit is not "does posting work" — it is "when posting cannot work, does
anything say so". There are three hooks, and each one is checked here:

    auto_post_invoice   Dr 1100 / Cr income      (rent, utilities)
    auto_post_payment   Dr 1000 / Cr 1100        (money in)
    auto_post_expense   Dr expense / Cr 1000     (money out)

Plus a structural guard: a posting call may not sit in a `try` whose handler is
an empty `pass`. That is the silencer, and it is caught by shape rather than by
remembering to check it.
"""

from __future__ import annotations

import ast
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.accounting import service
from app.accounting.service import (
    DEFAULT_EXPENSE_CODE,
    DEFAULT_COA,
    EXPENSE_ACCOUNT_CODES,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
PROVISIONED_CODES = {row[0] for row in DEFAULT_COA}

POSTING_HOOKS = ("auto_post_invoice", "auto_post_payment", "auto_post_expense")


class _Account:
    def __init__(self, account_id):
        self.id = account_id


class _StubSession:
    """Serves one `scalar` result per `get_account_id_by_code` call."""

    def __init__(self, results):
        self._results = list(results)

    async def scalar(self, _query):
        return self._results.pop(0)


def _stub_posting(monkeypatch):
    posted: list[list[dict]] = []

    async def _recorder(session, business_id, entries, **kwargs):
        posted.append(entries)

    monkeypatch.setattr(service, "post_journal_entry", _recorder)
    return posted


def _payment():
    return SimpleNamespace(
        id=uuid4(),
        business_id=uuid4(),
        tenant_id=uuid4(),
        amount=Decimal("3000.00"),
        reference="QK123456",
        paid_at=datetime(2026, 9, 30, 9, 0, 0),
    )


def _expense(category="repairs"):
    return SimpleNamespace(
        id=uuid4(),
        business_id=uuid4(),
        property_id=uuid4(),
        amount=Decimal("4500.00"),
        category=category,
        description="Burst pipe",
        paid_at=datetime(2026, 9, 29, 8, 0, 0),
    )


# ── The indirect account table ─────────────────────────────────────


def test_every_expense_category_posts_to_a_provisioned_account():
    """The second account-code table, guarded like the first.

    `auto_post_expense` resolves its account from a category map and passes a
    *variable* to `get_account_id_by_code`, so the source-scan guard in
    `test_utility_ledger.py` — which matches string literals — cannot see these.
    A category added here pointing at a non-existent account would silently
    drop the expense, exactly as "4200" dropped utility income.
    """
    for category, code in EXPENSE_ACCOUNT_CODES.items():
        assert code in PROVISIONED_CODES, (
            f"expense category {category!r} posts to {code}, "
            "which DEFAULT_COA never creates"
        )


def test_the_default_expense_code_is_provisioned():
    assert DEFAULT_EXPENSE_CODE in PROVISIONED_CODES


async def test_an_unknown_expense_category_still_posts(monkeypatch):
    """An unmapped category must fall back, not vanish."""
    posted = _stub_posting(monkeypatch)
    supplies = uuid4()
    session = _StubSession([_Account(uuid4()), _Account(supplies)])

    await service.auto_post_expense(session, _expense(category="roof-thatching"))

    assert len(posted) == 1, "an unrecognised category must still post"
    assert posted[0][0]["account_id"] == supplies, "must fall back to supplies"


# ── Missing accounts must be audible ───────────────────────────────


async def test_a_missing_cash_account_is_logged_for_a_payment(monkeypatch, caplog):
    posted = _stub_posting(monkeypatch)
    # Cash resolves, receivable does not.
    session = _StubSession([_Account(uuid4()), None])

    with caplog.at_level(logging.WARNING, logger="app.accounting.service"):
        await service.auto_post_payment(session, _payment())

    assert posted == [], "must not post a half-entry"
    assert any(
        record.levelno == logging.WARNING and "1000" in record.getMessage()
        for record in caplog.records
    ), f"expected a warning naming the unresolvable account, got {caplog.text!r}"


async def test_a_missing_expense_account_is_logged(monkeypatch, caplog):
    posted = _stub_posting(monkeypatch)
    session = _StubSession([_Account(uuid4()), None])

    with caplog.at_level(logging.WARNING, logger="app.accounting.service"):
        await service.auto_post_expense(session, _expense())

    assert posted == [], "must not post a half-entry"
    assert any(
        record.levelno == logging.WARNING and "5000" in record.getMessage()
        for record in caplog.records
    ), f"expected a warning naming the unresolvable account, got {caplog.text!r}"


async def test_a_payment_posts_balanced(monkeypatch):
    """The happy path, asserted on the entry: Dr cash / Cr receivable."""
    posted = _stub_posting(monkeypatch)
    cash, receivable = uuid4(), uuid4()
    session = _StubSession([_Account(cash), _Account(receivable)])

    await service.auto_post_payment(session, _payment())

    debit, credit = posted[0]
    assert debit["account_id"] == cash and debit["debit"] == 3000.0
    assert credit["account_id"] == receivable and credit["credit"] == 3000.0


async def test_an_expense_posts_balanced(monkeypatch):
    """Dr expense / Cr cash — costs are recorded, cash goes down."""
    posted = _stub_posting(monkeypatch)
    cash, repairs = uuid4(), uuid4()
    session = _StubSession([_Account(cash), _Account(repairs)])

    await service.auto_post_expense(session, _expense())

    debit, credit = posted[0]
    assert debit["account_id"] == repairs and debit["debit"] == 4500.0
    assert credit["account_id"] == cash and credit["credit"] == 4500.0


async def test_an_unbalanced_entry_is_refused_by_the_poster(monkeypatch):
    """`post_journal_entry` rejects books that do not balance, so callers must
    surface that rather than swallow it."""
    session = _StubSession([])
    with pytest.raises(ValueError, match="does not balance"):
        await service.post_journal_entry(
            session, uuid4(),
            entries=[
                {"account_id": uuid4(), "debit": 100, "credit": 0},
                {"account_id": uuid4(), "debit": 0, "credit": 90},
            ],
        )


# ── The silencer, caught by shape ──────────────────────────────────


def _swallowed_posting_calls() -> list[str]:
    """Every posting call sitting in a `try` whose handlers are all `pass`.

    A bare `pass` handler means *any* failure — a missing account, a database
    error, an unbalanced entry — leaves no trace whatsoever. Best-effort posting
    is fine; best-effort posting that reports nothing is how this feature broke.

    Parsed with `ast` so formatting, comments and added logging lines cannot
    hide it from the check.
    """
    offenders: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            called = {
                getattr(inner.func, "attr", None) or getattr(inner.func, "id", None)
                for inner in ast.walk(node)
                if isinstance(inner, ast.Call)
            }
            if not called.intersection(POSTING_HOOKS):
                continue
            for handler in node.handlers:
                body = [stmt for stmt in handler.body if not isinstance(stmt, ast.Expr)]
                if body and all(isinstance(stmt, ast.Pass) for stmt in body):
                    offenders.append(f"{path.name}:{handler.lineno}")
    return offenders


def test_no_posting_call_is_wrapped_in_a_bare_pass():
    offenders = _swallowed_posting_calls()
    assert not offenders, (
        "these posting calls are wrapped in `except: pass`, so a failed ledger "
        f"posting would leave no trace: {offenders}"
    )


def test_the_silencer_check_can_actually_see_a_silencer():
    """Guard the guard: the AST walk must recognise the shape it forbids."""
    source = (
        "async def f(session, obj):\n"
        "    try:\n"
        "        await auto_post_payment(session, obj)\n"
        "    except Exception:\n"
        "        pass\n"
    )
    tree = ast.parse(source)
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and any(
            (getattr(c.func, "attr", None) or getattr(c.func, "id", None)) in POSTING_HOOKS
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
        )
        and any(
            all(isinstance(s, ast.Pass) for s in h.body if not isinstance(s, ast.Expr))
            for h in node.handlers
        )
    ]
    assert found, "the detector failed to recognise a bare-pass posting wrapper"
