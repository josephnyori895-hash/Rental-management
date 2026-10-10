"""
Tests for the aged-receivables and rent-roll reports.

These run without a database: the report queries are compiled against the
PostgreSQL dialect (including their bound parameters) to prove they are
structurally valid and correctly scoped, and the aging bucketing logic is
exercised directly.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.dialects import postgresql

from app.main import app
from app.reports.receivables import (
    AGING_BUCKETS,
    OUTSTANDING_STATUSES,
    _age_bucket,
    _aged_receivables_query,
    _outstanding_by_lease_query,
    _rent_roll_query,
)

DIALECT = postgresql.dialect()

# Fixed "today" so the day arithmetic below is never flaky.
TODAY = date(2026, 9, 30)


@pytest.fixture
def business_id():
    return uuid4()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# ── Query construction ────────────────────────────────────────────

@pytest.mark.parametrize("build", [
    _aged_receivables_query,
    _rent_roll_query,
    _outstanding_by_lease_query,
])
def test_report_queries_compile_against_postgres(build, business_id):
    """A malformed column or join would raise here, without needing a DB."""
    sql = str(build(business_id).compile(dialect=DIALECT))
    assert "SELECT" in sql.upper()
    assert "FROM" in sql.upper()


def test_aged_receivables_is_scoped_and_filters_to_outstanding(business_id):
    """Business isolation + only money-owing invoices, guarded by bound params."""
    compiled = _aged_receivables_query(business_id).compile(dialect=DIALECT)
    sql = str(compiled)

    assert "invoices.business_id" in sql
    assert "invoices.balance >" in sql

    assert compiled.params["business_id_1"] == business_id
    assert list(compiled.params["status_1"]) == list(OUTSTANDING_STATUSES)
    assert compiled.params["balance_1"] == 0


def test_rent_roll_is_scoped_and_limited_to_active_leases(business_id):
    compiled = _rent_roll_query(business_id).compile(dialect=DIALECT)
    sql = str(compiled)

    assert "leases.business_id" in sql
    assert compiled.params["business_id_1"] == business_id
    assert compiled.params["status_1"] == "active"


def test_outstanding_by_lease_groups_by_lease(business_id):
    sql = str(_outstanding_by_lease_query(business_id).compile(dialect=DIALECT))
    assert "GROUP BY" in sql.upper()


def test_outstanding_statuses_exclude_settled_invoices():
    """Intent lock: paid/draft/cancelled invoices must never appear as arrears."""
    for settled in ("paid", "draft", "cancelled", "refunded"):
        assert settled not in OUTSTANDING_STATUSES


# ── Aging buckets ─────────────────────────────────────────────────
#
# Bucketing is `overdue_days <= 30 / 60 / 90`; the due dates below were
# computed by hand against TODAY and are exact off-by-one guards.

@pytest.mark.parametrize("due,expected", [
    (None, "current"),                      # no due date -> never ages
    (date(2026, 9, 30), "current"),         # due today (0 days)
    (date(2026, 10, 5), "current"),         # future
    (date(2026, 9, 29), "days_1_30"),       # 1 day
    (date(2026, 8, 31), "days_1_30"),       # 30 days
    (date(2026, 8, 30), "days_31_60"),      # 31 days
    (date(2026, 8, 1), "days_31_60"),       # 60 days
    (date(2026, 7, 31), "days_61_90"),      # 61 days
    (date(2026, 7, 2), "days_61_90"),       # 90 days
    (date(2026, 7, 1), "days_90_plus"),     # 91 days
    (date(2026, 6, 30), "days_90_plus"),    # 92 days
    (date(2020, 1, 1), "days_90_plus"),     # long overdue
])
def test_age_bucket_boundaries(due, expected):
    assert _age_bucket(due, TODAY) == expected


def test_bucket_flip_days_are_exactly_30_60_90():
    """The day a bucket flips must be exact — no off-by-one."""
    assert _age_bucket(date(2026, 8, 31), TODAY) == "days_1_30"      # 30
    assert _age_bucket(date(2026, 8, 30), TODAY) == "days_31_60"     # 31
    assert _age_bucket(date(2026, 8, 1), TODAY) == "days_31_60"      # 60
    assert _age_bucket(date(2026, 7, 31), TODAY) == "days_61_90"     # 61
    assert _age_bucket(date(2026, 7, 2), TODAY) == "days_61_90"      # 90
    assert _age_bucket(date(2026, 7, 1), TODAY) == "days_90_plus"    # 91


def test_bucket_order_is_stable():
    assert AGING_BUCKETS[0] == "current"
    assert AGING_BUCKETS[-1] == "days_90_plus"
    assert len(AGING_BUCKETS) == 5


# ── Route registration & auth ─────────────────────────────────────

def test_new_report_routes_are_registered():
    paths = app.openapi()["paths"]
    for path in ("/api/v1/reports/aged-receivables", "/api/v1/reports/rent-roll"):
        assert path in paths
        assert "get" in paths[path]


async def test_new_report_routes_require_a_token():
    """Reports are mounted behind owner-only auth — no token means 401."""
    async with _client() as client:
        for path in ("/api/v1/reports/aged-receivables", "/api/v1/reports/rent-roll"):
            response = await client.get(path)
            assert response.status_code == 401, path
