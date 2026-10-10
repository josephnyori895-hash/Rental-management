"""
Tests for utility / service-charge billing.

No database is required. Three layers are covered:

1. the money arithmetic in `app.billing.utilities` (pure functions),
2. the caretaker's WhatsApp grammar,
3. the persistence contract — that the models and the Alembic migration
   actually agree, which is otherwise only discoverable in production
   because this suite has no database to run migrations against.
"""

from __future__ import annotations

import importlib.util
import io
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from alembic.migration import MigrationContext
from fastapi import HTTPException
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql

from app.billing.utilities import (
    ReadingError,
    apportion,
    build_weights,
    compute_amount,
    compute_consumption,
    parse_meter_command,
    quantize_money,
    quantize_units,
    resolve_rate,
    split_method_for,
)
from app.billing import utilities_router
from app.billing.utilities_router import ReadingRequest, SharedBillRequest
from app.main import app
from app.models.billing import Invoice, InvoiceStatus
from app.models.business import Business
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, UnitStatus
from app.models.utilities import (
    MeterReading,
    SplitMethod,
    UtilityRate,
    UtilityType,
)

DIALECT = postgresql.dialect()
BACKEND_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = BACKEND_DIR / "migrations" / "versions"
HEAD_REVISION = "e5f6a7b8c9d0"


# ── Consumption ────────────────────────────────────────────────────


def test_consumption_is_current_minus_previous():
    assert compute_consumption(100, 175) == Decimal("75.000")
    assert compute_consumption(Decimal("1000"), Decimal("1042.5")) == Decimal("42.500")


def test_consumption_of_an_unchanged_meter_is_zero():
    assert compute_consumption(500, 500) == Decimal("0.000")


def test_first_reading_is_a_baseline_not_full_consumption():
    """With no previous reading there is nothing to bill — not the odometer."""
    assert compute_consumption(None, 98765) == Decimal("0.000")


def test_backwards_meter_reading_is_rejected_not_silently_zeroed():
    with pytest.raises(ReadingError):
        compute_consumption(1000, 990)


# ── Pricing ────────────────────────────────────────────────────────


def test_amount_is_units_times_rate_plus_fixed_charge():
    assert compute_amount(12, Decimal("150"), Decimal("200")) == Decimal("2000.00")


def test_amount_rounds_half_up_to_the_shilling():
    # 3.333 x 33.333 = 111.098889 -> 111.10
    assert compute_amount(Decimal("3.333"), Decimal("33.333")) == Decimal("111.10")
    # .005 must round up, not to even
    assert compute_amount(Decimal("1"), Decimal("0.005")) == Decimal("0.01")


def test_zero_consumption_with_a_fixed_charge_still_bills_the_fixed_charge():
    assert compute_amount(0, Decimal("150"), Decimal("200")) == Decimal("200.00")


def test_negative_consumption_is_rejected():
    with pytest.raises(ReadingError):
        compute_amount(-1, 10)


def test_quantizers():
    assert quantize_money("10.005") == Decimal("10.01")
    assert quantize_units("42.0004") == Decimal("42.000")
    assert quantize_units("42.0005") == Decimal("42.001")


# ── Apportionment ──────────────────────────────────────────────────


def test_equal_split_sums_exactly_to_the_total():
    shares = apportion(100, [1, 1, 1], SplitMethod.EQUAL.value)
    assert sum(shares) == Decimal("100.00")
    assert sorted(shares) == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]


def test_proportional_split_sums_exactly_to_the_total():
    shares = apportion(1000, [10, 20, 70])
    assert sum(shares) == Decimal("1000.00")
    assert shares == [Decimal("100.00"), Decimal("200.00"), Decimal("700.00")]


@pytest.mark.parametrize("total,weights", [
    (Decimal("100"), [1, 1, 1]),
    (Decimal("0.01"), [1, 1, 1]),
    (Decimal("999.99"), [3, 5, 7, 11]),
    (Decimal("12345.67"), [1, 0, 0, 1]),
    (Decimal("50"), [0.5, 0.5]),
    (Decimal("17.77"), [Decimal("123.456")]),
])
def test_apportioned_shares_always_reconcile_to_the_total(total, weights):
    """A lost cent here becomes a permanent ledger imbalance, so assert it."""
    shares = apportion(total, weights)
    assert sum(shares) == quantize_money(total)
    assert all(share >= 0 for share in shares)


def test_metered_split_is_proportional_to_consumption():
    shares = apportion(900, [5, 10, 15], SplitMethod.METERED.value)
    assert shares == [Decimal("150.00"), Decimal("300.00"), Decimal("450.00")]


def test_occupancy_split_uses_the_supplied_weights():
    shares = apportion(400, [1, 1, 2], SplitMethod.OCCUPANCY.value)
    assert shares == [Decimal("100.00"), Decimal("100.00"), Decimal("200.00")]


def test_all_zero_weights_fall_back_to_an_even_split():
    """Billing nobody would be worse than billing everyone equally."""
    shares = apportion(300, [0, 0, 0])
    assert shares == [Decimal("100.00")] * 3


def test_apportioning_across_no_units_is_an_error():
    with pytest.raises(ReadingError):
        apportion(100, [])


# ── Tariff resolution ──────────────────────────────────────────────


def _rate(utility_type="water", unit_id=None, rate="50", fixed="0", active=True, method="metered"):
    return UtilityRate(
        business_id=uuid4(),
        property_id=uuid4(),
        unit_id=unit_id,
        utility_type=utility_type,
        rate_per_unit=Decimal(rate),
        fixed_charge=Decimal(fixed),
        split_method=method,
        is_active=active,
    )


def test_unit_specific_tariff_beats_the_property_default():
    unit_id = uuid4()
    default = _rate(rate="50")
    specific = _rate(unit_id=unit_id, rate="75")

    assert resolve_rate([default, specific], "water", unit_id) is specific
    assert resolve_rate([default, specific], "water", None) is default


def test_inactive_and_other_utility_tariffs_are_ignored():
    assert resolve_rate([_rate(active=False)], "water", None) is None
    assert resolve_rate([_rate(utility_type="electricity")], "water", None) is None


def test_no_configured_tariff_returns_none_rather_than_inventing_a_price():
    assert resolve_rate([], "water", None) is None


def test_split_method_falls_back_when_unset():
    assert split_method_for(_rate(method="equal")) == "equal"
    assert split_method_for(None) == SplitMethod.METERED.value
    assert split_method_for(SimpleNamespace(split_method=None), "equal") == "equal"


# ── Weight building ────────────────────────────────────────────────


def _unit(number, occupants=1, rent=1000, consumed=None):
    return SimpleNamespace(
        unit_number=number, max_occupants=occupants,
        monthly_rent=Decimal(str(rent)), consumed=consumed,
    )


def test_equal_weights_ignore_unit_attributes():
    weights, missing = build_weights([_unit("A", occupants=4), _unit("B")], SplitMethod.EQUAL.value)
    assert weights == [Decimal(1), Decimal(1)]
    assert missing == []


def test_occupancy_weights_track_max_occupants():
    weights, _ = build_weights(
        [_unit("A", occupants=2), _unit("B", occupants=5)], SplitMethod.OCCUPANCY.value
    )
    assert weights == [Decimal(2), Decimal(5)]


def test_rent_weights_track_monthly_rent():
    weights, _ = build_weights(
        [_unit("A", rent=12000), _unit("B", rent=8000)], SplitMethod.RENT.value
    )
    assert weights == [Decimal("12000"), Decimal("8000")]


def test_metered_split_reports_units_that_have_no_reading():
    weights, missing = build_weights(
        [_unit("A", consumed=Decimal("5")), _unit("B")], SplitMethod.METERED.value
    )
    assert weights == [Decimal("5"), Decimal(0)]
    assert missing == ["B"]


def test_metered_split_with_full_coverage_reports_nothing_missing():
    weights, missing = build_weights(
        [_unit("A", consumed=Decimal("5")), _unit("B", consumed=Decimal("2"))],
        SplitMethod.METERED.value,
    )
    assert weights == [Decimal("5"), Decimal("2")]
    assert missing == []


# ── WhatsApp grammar ───────────────────────────────────────────────


def test_bare_number_is_a_bulk_reading():
    cmd = parse_meter_command("1204")
    assert cmd is not None
    assert cmd.reading == Decimal("1204")
    assert cmd.unit_ref is None
    assert cmd.utility_type is None


def test_short_bare_numbers_are_not_readings():
    """'2' or '12' is a typo, not a meter reading."""
    assert parse_meter_command("2") is None
    assert parse_meter_command("12") is None


def test_meter_command_with_unit():
    cmd = parse_meter_command("METER A1 348")
    assert cmd is not None
    assert cmd.reading == Decimal("348")
    assert cmd.unit_ref == "A1"
    assert cmd.utility_type is None


def test_utility_keyword_with_unit_and_reading():
    cmd = parse_meter_command("water b-12 1204")
    assert cmd is not None
    assert cmd.utility_type == UtilityType.WATER.value
    assert cmd.unit_ref == "B-12"
    assert cmd.reading == Decimal("1204")


def test_utility_keyword_aliases():
    for alias in ("ELEC", "ELECTRICITY", "POWER"):
        cmd = parse_meter_command(f"{alias} 500")
        assert cmd is not None and cmd.utility_type == UtilityType.ELECTRICITY.value


def test_decimal_readings_are_accepted():
    cmd = parse_meter_command("GAS A3 45.75")
    assert cmd is not None and cmd.reading == Decimal("45.75")


def test_commas_in_readings_are_ignored():
    cmd = parse_meter_command("12,480")
    assert cmd is not None and cmd.reading == Decimal("12480")


def test_ordinary_commands_are_not_parsed_as_readings():
    for text in ("STATUS", "HELP", "FIXED", "ADD 254700000000 A1 Jane", "", "   "):
        assert parse_meter_command(text) is None


def test_reading_with_too_many_digits_is_rejected():
    assert parse_meter_command("12345678") is None


# ── WhatsApp dispatch ──────────────────────────────────────────────
#
# The caretaker flow used to dead-end in a canned "(Full integration in
# v2)" reply. These tests pin the dispatch: a reading must reach the real
# handler. A stub session is enough — the first thing the handler does is
# look for the business's properties.

class _Result:
    """Stands in for a SQLAlchemy Result: `.scalars().all()` or `.all()`."""

    def __init__(self, scalars=(), rows=()):
        self._scalars = list(scalars)
        self._rows = list(rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalars))

    def all(self):
        return list(self._rows)

    def scalar(self):
        return self._scalars[0] if self._scalars else None


class _StubDB:
    """A session that answers from a queue of prepared results.

    `execute`/`scalar` pop the next prepared result in call order, and `get`
    resolves from a list of detached ORM objects. `flush` assigns ids the way
    the database would, so the ids the routes return are not all None.
    """

    def __init__(self, results=(), objects=()):
        self._results = list(results)
        self._objects = list(objects)
        self.added = []
        self.committed = False

    async def execute(self, _statement):
        return self._results.pop(0)

    async def scalar(self, _statement):
        return self._results.pop(0).scalar()

    async def get(self, model, ident):
        for obj in self._objects:
            if isinstance(obj, model) and getattr(obj, "id", None) == ident:
                return obj
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def commit(self):
        self.committed = True


async def _dispatch(text: str, role: str):
    from app.notifications.inbound_user import _handle_user_command

    user = SimpleNamespace(
        business_id=uuid4(), id=uuid4(), role=role,
        full_name="Test Caretaker", phone="254700000000",
    )
    # The handler's first act is to look for the business's properties.
    return await _handle_user_command(
        _StubDB(results=[_Result()]), user, text.upper(), text, "254700000000", None
    )


async def test_a_bare_reading_reaches_the_meter_handler():
    reply = await _dispatch("1204", "agent")
    assert "v2" not in reply["message"]
    assert reply["message"] == "No property set up for this business yet."


async def test_owners_can_log_readings_too():
    """Owners read the shared meters, so the old agent-only gate is wrong."""
    reply = await _dispatch("METER A1 348", "owner")
    assert reply["message"] == "No property set up for this business yet."


async def test_unknown_commands_still_fall_through_to_help():
    reply = await _dispatch("FLUFF", "agent")
    assert reply["message"] == "Unknown command. Reply HELP."


async def test_help_lists_the_meter_command():
    reply = await _dispatch("HELP", "agent")
    assert "WATER <unit> <reading>" in reply["message"]


# ── Model contract ─────────────────────────────────────────────────


def test_bulk_readings_are_the_ones_without_a_unit():
    reading = MeterReading(
        business_id=uuid4(), property_id=uuid4(), unit_id=None,
        utility_type="water", reading_date=date(2026, 9, 30),
        current_reading=Decimal("1204"), units_consumed=Decimal("0"),
        rate_per_unit=Decimal("0"), fixed_charge=Decimal("0"), amount=Decimal("0"),
    )
    assert reading.is_bulk is True
    reading.unit_id = uuid4()
    assert reading.is_bulk is False


def test_both_utility_tables_carry_business_id_for_tenant_scoping():
    """Every query in the router is scoped by business_id — so it must exist."""
    for table in (UtilityRate.__table__, MeterReading.__table__):
        assert "business_id" in table.columns
        assert table.columns["business_id"].index is True


def test_a_unit_reading_is_optional_but_the_property_is_not():
    assert MeterReading.__table__.columns["unit_id"].nullable is True
    assert MeterReading.__table__.columns["property_id"].nullable is False
    assert UtilityRate.__table__.columns["unit_id"].nullable is True


def test_billing_columns_are_numeric_not_float():
    """Floats must never touch money in the ledger."""
    for column in ("rate_per_unit", "fixed_charge", "amount", "units_consumed"):
        assert MeterReading.__table__.columns[column].type.__class__.__name__ == "Numeric"


# ── Migration consistency (no database needed) ─────────────────────


def _load_migration(revision: str):
    path = VERSIONS_DIR / f"{revision}_create_utilities_tables.py"
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_upgrade_sql(module) -> str:
    """Run the migration offline and capture the SQL it would emit."""
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(context):
        module.upgrade()
    return buffer.getvalue()


def test_migration_creates_every_model_column_with_the_same_type():
    sql = _render_upgrade_sql(_load_migration(HEAD_REVISION))

    for table in (UtilityRate.__table__, MeterReading.__table__):
        assert f"CREATE TABLE {table.name}" in sql, table.name
        block = sql.split(f"CREATE TABLE {table.name} (", 1)[1].split(");", 1)[0]

        for column in table.columns:
            expected = column.name + " " + column.type.compile(dialect=DIALECT)
            if not column.nullable:
                expected += " NOT NULL"
            assert expected in block, f"{table.name}.{expected}"


# `UUIDMixin.id` and `TimestampMixin.created_at` are declared index=True in
# the models, but no migration in this repo ever created those indexes (see
# b2c3d4e5f6a7_create_notification_log). A primary key needs no index in
# Postgres, and matching the existing tables beats having two tables with an
# index nothing else has. Real drift — flagged, not widened silently.
MODEL_INDEXES_NOT_IN_MIGRATIONS = {
    "ix_utility_rates_id",
    "ix_utility_rates_created_at",
    "ix_meter_readings_id",
    "ix_meter_readings_created_at",
}

LOOKUP_INDEXES = [
    "ix_utility_rates_business_id",
    "ix_utility_rates_property_id",
    "ix_utility_rates_unit_id",
    "ix_utility_rates_utility_type",
    "ix_utility_rates_is_active",
    "ix_meter_readings_business_id",
    "ix_meter_readings_property_id",
    "ix_meter_readings_unit_id",
    "ix_meter_readings_utility_type",
    "ix_meter_readings_reading_date",
    "ix_meter_readings_invoice_id",
    "ix_meter_readings_scope",
]


def test_migration_creates_every_model_index():
    sql = _render_upgrade_sql(_load_migration(HEAD_REVISION))

    for table in (UtilityRate.__table__, MeterReading.__table__):
        for index in table.indexes:
            if index.name in MODEL_INDEXES_NOT_IN_MIGRATIONS:
                continue
            assert f"CREATE INDEX {index.name} ON {table.name}" in sql, index.name


def test_migration_indexes_every_column_the_router_filters_on():
    """Guards the allow-list above from being widened to hide a real gap."""
    sql = _render_upgrade_sql(_load_migration(HEAD_REVISION))
    for name in LOOKUP_INDEXES:
        assert f"CREATE INDEX {name} " in sql, name


def test_migration_scopes_its_foreign_keys_by_business():
    sql = _render_upgrade_sql(_load_migration(HEAD_REVISION))
    assert "fk_meter_readings_business_id_businesses FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE" in sql
    assert "fk_utility_rates_business_id_businesses FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE" in sql


def test_downgrade_drops_what_upgrade_created():
    sql = _render_upgrade_sql(_load_migration(HEAD_REVISION))
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer}
    )
    with Operations.context(context):
        _load_migration(HEAD_REVISION).downgrade()
    down_sql = buffer.getvalue()

    for table in ("utility_rates", "meter_readings"):
        assert f"CREATE TABLE {table}" in sql
        assert f"DROP TABLE {table}" in down_sql


def test_migration_history_is_a_single_linear_chain_ending_at_head():
    """A duplicate head would break `alembic upgrade head` in production."""
    revisions: dict[str, str | None] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        text = path.read_text()
        revision = re.search(r"^revision: str = ['\"]([^'\"]+)['\"]", text, re.M)
        down = re.search(r"^down_revision: Union\[str, None\] = (?:'([^']+)'|None)", text, re.M)
        assert revision, f"No revision id in {path.name}"
        assert down, f"No down_revision in {path.name}"
        revisions[revision.group(1)] = down.group(1)

    assert HEAD_REVISION in revisions
    assert revisions[HEAD_REVISION] == "d4e5f6a7b8c9"

    bases = [rev for rev, down in revisions.items() if down is None]
    heads = [rev for rev in revisions if rev not in set(revisions.values())]
    assert len(bases) == 1, f"Expected one base revision, found {bases}"
    assert heads == [HEAD_REVISION], f"Expected a single head, found {heads}"

    # Walk back from head: every step must exist and the chain must terminate.
    seen = []
    current: str | None = HEAD_REVISION
    while current is not None:
        assert current not in seen, f"Cycle in migration history at {current}"
        seen.append(current)
        current = revisions[current]
    assert len(seen) == len(revisions)


# ── Route behaviour (stub session, no database) ────────────────────
#
# The routes build their SQL at call time, so calling them directly runs the
# whole billing path — consumption, tariff lookup, amount, invoice — without
# a database. Only `auto_post_invoice` is stubbed (it needs the ledger).

async def _no_post(*_args, **_kwargs):
    return None


def _make_graph(unit_numbers=("A1", "A2", "A3")):
    """A business with one property whose units are all occupied."""
    business = Business(
        id=uuid4(), name="Test Landlord", slug="test-landlord",
        owner_id=uuid4(), is_active=True,
    )
    prop = Property(id=uuid4(), business_id=business.id, name="Block A", is_deleted=False)
    units, leases = [], []
    for number in unit_numbers:
        unit_id = uuid4()
        tenant_id = uuid4()
        lease = Lease(
            id=uuid4(), business_id=business.id, unit_id=unit_id, tenant_id=tenant_id,
            property_id=prop.id, start_date=date(2026, 1, 1),
            rent_amount=Decimal("10000"), status=LeaseStatus.ACTIVE.value,
        )
        units.append(Unit(
            id=unit_id, business_id=business.id, property_id=prop.id,
            unit_number=number, status=UnitStatus.OCCUPIED.value,
            monthly_rent=Decimal("10000"), current_lease_id=lease.id,
            is_deleted=False,
        ))
        leases.append(lease)
    return business, prop, units, leases


def _water_rate(prop, business, **overrides):
    rate = _rate(**overrides)
    rate.business_id = business.id
    rate.property_id = prop.id
    return rate


async def test_record_reading_prices_the_consumption_and_invoices_the_tenant(monkeypatch):
    monkeypatch.setattr(utilities_router, "auto_post_invoice", _no_post)
    business, prop, units, leases = _make_graph(("A1",))
    unit, lease = units[0], leases[0]
    rate = _water_rate(prop, business, rate="50")

    previous = MeterReading(
        business_id=business.id, property_id=prop.id, unit_id=unit.id,
        utility_type="water", reading_date=date(2026, 9, 1),
        current_reading=Decimal("1000"), units_consumed=Decimal("0"),
        rate_per_unit=Decimal("0"), fixed_charge=Decimal("0"), amount=Decimal("0"),
    )
    db = _StubDB(
        results=[_Result(scalars=[previous]), _Result(scalars=[rate])],
        objects=[unit, prop, lease],
    )

    result = await utilities_router.record_reading(
        ReadingRequest(unit_id=str(unit.id), utility_type="water", current_reading=1204),
        db, business,
    )

    assert result["consumed"] == 204.0
    assert result["amount"] == 10200.0   # 204 units x KES 50
    assert result["billed"] is True
    assert db.committed is True

    invoices = [obj for obj in db.added if isinstance(obj, Invoice)]
    assert len(invoices) == 1
    assert invoices[0].amount == Decimal("10200.00")
    assert invoices[0].balance == Decimal("10200.00")
    assert invoices[0].invoice_type == "water"
    assert invoices[0].tenant_id == lease.tenant_id
    assert invoices[0].status == InvoiceStatus.PENDING.value
    assert invoices[0].due_date is None   # no due date was requested


async def test_record_reading_against_a_vacant_unit_stores_but_does_not_bill(monkeypatch):
    monkeypatch.setattr(utilities_router, "auto_post_invoice", _no_post)
    business, prop, units, leases = _make_graph(("A1",))
    unit = units[0]
    unit.current_lease_id = None          # vacant
    rate = _water_rate(prop, business, rate="50")

    previous = MeterReading(
        business_id=business.id, property_id=prop.id, unit_id=unit.id,
        utility_type="water", reading_date=date(2026, 9, 1),
        current_reading=Decimal("1000"), units_consumed=Decimal("0"),
        rate_per_unit=Decimal("0"), fixed_charge=Decimal("0"), amount=Decimal("0"),
    )
    db = _StubDB(results=[_Result(scalars=[previous]), _Result(scalars=[rate])], objects=[unit, prop])

    result = await utilities_router.record_reading(
        ReadingRequest(unit_id=str(unit.id), utility_type="water", current_reading=1100),
        db, business,
    )

    assert result["billed"] is False
    assert "vacant" in result["note"].lower()
    assert not [obj for obj in db.added if isinstance(obj, Invoice)]


async def test_first_reading_is_recorded_as_a_baseline_only():
    business, prop, units, leases = _make_graph(("A1",))
    unit = units[0]
    rate = _water_rate(prop, business, rate="50")
    db = _StubDB(
        results=[_Result(), _Result(scalars=[rate])],   # no previous reading
        objects=[unit, prop, leases[0]],
    )

    result = await utilities_router.record_reading(
        ReadingRequest(unit_id=str(unit.id), utility_type="water", current_reading=1000),
        db, business,
    )

    assert result["consumed"] == 0.0
    assert result["amount"] == 0.0
    assert result["billed"] is False
    assert "baseline" in result["note"].lower()


async def test_a_backwards_reading_is_rejected_with_a_400():
    business, prop, units, _ = _make_graph(("A1",))
    unit = units[0]
    previous = MeterReading(
        business_id=business.id, property_id=prop.id, unit_id=unit.id,
        utility_type="water", reading_date=date(2026, 9, 1),
        current_reading=Decimal("2000"), units_consumed=Decimal("0"),
        rate_per_unit=Decimal("0"), fixed_charge=Decimal("0"), amount=Decimal("0"),
    )
    db = _StubDB(results=[_Result(scalars=[previous])], objects=[unit, prop])

    with pytest.raises(HTTPException) as exc:
        await utilities_router.record_reading(
            ReadingRequest(unit_id=str(unit.id), utility_type="water", current_reading=1204),
            db, business,
        )
    assert exc.value.status_code == 400
    assert "lower than the previous" in exc.value.detail


async def test_bill_shared_splits_equally_and_invoices_every_unit(monkeypatch):
    monkeypatch.setattr(utilities_router, "auto_post_invoice", _no_post)
    business, prop, units, leases = _make_graph()
    rate = _water_rate(prop, business, method=SplitMethod.EQUAL.value)
    db = _StubDB(
        results=[
            _Result(scalars=[rate]),   # configured tariffs
            _Result(scalars=units),    # occupied units
            _Result(rows=[]),          # per-unit consumption this period
        ],
        objects=[prop, *leases],
    )

    result = await utilities_router.bill_shared(
        SharedBillRequest(
            property_id=str(prop.id), utility_type="water",
            total_amount=3000, split_method=SplitMethod.EQUAL.value,
        ),
        db, business,
    )

    assert result["total"] == 3000.0
    assert result["units_billed"] == 3
    assert [row["share"] for row in result["breakdown"]] == [1000.0, 1000.0, 1000.0]

    invoices = [obj for obj in db.added if isinstance(obj, Invoice)]
    assert len(invoices) == 3
    assert sum(invoice.amount for invoice in invoices) == Decimal("3000.00")
    assert all(invoice.invoice_type == "water" for invoice in invoices)


async def test_bill_shared_metered_split_refuses_until_every_unit_is_metered(monkeypatch):
    """Billing an unmetered unit zero would quietly lose that unit's share."""
    monkeypatch.setattr(utilities_router, "auto_post_invoice", _no_post)
    business, prop, units, leases = _make_graph(("A1", "A2"))
    rate = _water_rate(prop, business, method=SplitMethod.METERED.value, rate="50")
    db = _StubDB(
        results=[
            _Result(scalars=[rate]),
            _Result(scalars=units),
            _Result(rows=[(units[0].id, Decimal("10"))]),   # only A1 has a reading
        ],
        objects=[prop, *leases],
    )

    with pytest.raises(HTTPException) as exc:
        await utilities_router.bill_shared(
            SharedBillRequest(
                property_id=str(prop.id), utility_type="water",
                total_amount=1000, split_method=SplitMethod.METERED.value,
            ),
            db, business,
        )

    assert exc.value.status_code == 400
    assert "A2" in exc.value.detail
    assert not [obj for obj in db.added if isinstance(obj, Invoice)]


async def test_bill_shared_needs_either_a_total_or_a_reading():
    business, prop, units, leases = _make_graph(("A1",))
    rate = _water_rate(prop, business)
    db = _StubDB(results=[_Result(scalars=[rate])], objects=[prop])

    with pytest.raises(HTTPException) as exc:
        await utilities_router.bill_shared(
            SharedBillRequest(property_id=str(prop.id), utility_type="water"),
            db, business,
        )

    assert exc.value.status_code == 400
    assert "total_amount" in exc.value.detail


async def test_bill_shared_refuses_a_property_with_no_occupied_units(monkeypatch):
    monkeypatch.setattr(utilities_router, "auto_post_invoice", _no_post)
    business, prop, _, _ = _make_graph()
    rate = _water_rate(prop, business, method=SplitMethod.EQUAL.value)
    db = _StubDB(results=[_Result(scalars=[rate]), _Result(scalars=[])], objects=[prop])

    with pytest.raises(HTTPException) as exc:
        await utilities_router.bill_shared(
            SharedBillRequest(property_id=str(prop.id), utility_type="water", total_amount=500),
            db, business,
        )

    assert exc.value.status_code == 400
    assert "occupied" in exc.value.detail


async def test_an_unknown_utility_type_is_rejected_before_any_query():
    business, prop, _, _ = _make_graph()
    db = _StubDB(objects=[prop])

    with pytest.raises(HTTPException) as exc:
        await utilities_router.bill_shared(
            SharedBillRequest(property_id=str(prop.id), utility_type="plutonium", total_amount=1),
            db, business,
        )

    assert exc.value.status_code == 400
    assert "utility_type" in exc.value.detail


async def test_a_property_from_another_business_is_not_visible():
    business, prop, _, _ = _make_graph()
    prop.business_id = uuid4()          # someone else's property
    db = _StubDB(objects=[prop])

    with pytest.raises(HTTPException) as exc:
        await utilities_router.bill_shared(
            SharedBillRequest(property_id=str(prop.id), utility_type="water", total_amount=1),
            db, business,
        )

    assert exc.value.status_code == 404


# ── Routes ─────────────────────────────────────────────────────────


NEW_PATHS = [
    "/api/v1/billing/utilities/rates",
    "/api/v1/billing/utilities/readings",
    "/api/v1/billing/utilities/bill-shared",
]


def test_the_superseded_bill_endpoint_is_flagged_deprecated_in_the_schema():
    """`POST /billing/bills` predates meter-driven utility billing.

    It takes an arbitrary amount and an unvalidated `bill_type`, so a typo
    silently becomes a new `invoice_type`. It still works, but clients should
    be steered to `/billing/utilities/readings`, and OpenAPI is where they
    read that.
    """
    paths = app.openapi()["paths"]
    assert paths["/api/v1/billing/bills"]["post"]["deprecated"] is True


def test_utility_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/billing/utilities/rates"]
    assert "post" in paths["/api/v1/billing/utilities/rates"]
    assert "get" in paths["/api/v1/billing/utilities/readings"]
    assert "post" in paths["/api/v1/billing/utilities/readings"]
    assert "post" in paths["/api/v1/billing/utilities/bill-shared"]


async def test_utility_routes_require_a_token():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get(NEW_PATHS[0])).status_code == 401
        assert (await client.get(NEW_PATHS[1])).status_code == 401
        assert (await client.post(NEW_PATHS[2], json={"property_id": str(uuid4())})).status_code == 401


def test_the_new_surface_is_owner_only():
    from app.main import app as fastapi_app

    for route in fastapi_app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/v1/billing/utilities"):
            assert any(
                dependency.dependency.__name__ == "require_owner"
                for dependency in route.dependencies
            ), path
