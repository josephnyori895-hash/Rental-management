from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.subscriptions.service import calculate_item_total, money


def item(model="flat_recurring"):
    return SimpleNamespace(pricing_model=model)


def price(amount="1000.00", included=0, per_unit="0.00"):
    return SimpleNamespace(
        amount=Decimal(amount),
        included_units=included,
        per_unit_amount=Decimal(per_unit),
    )


def test_flat_recurring_price_uses_decimal_and_rounds_to_cents():
    assert calculate_item_total(item(), price("1250.555"), 1, 0) == Decimal("1250.56")


def test_per_billable_unit_charges_only_units_above_allowance():
    assert calculate_item_total(
        item("per_billable_unit"), price("500.00", 10, "25.00"), 1, 14
    ) == Decimal("600.00")


def test_per_billable_unit_does_not_charge_below_included_units():
    assert calculate_item_total(
        item("per_billable_unit"), price("500.00", 10, "25.00"), 1, 4
    ) == Decimal("500.00")


def test_quantity_multiplies_calculated_line_total():
    assert calculate_item_total(
        item("per_billable_unit"), price("500.00", 10, "25.00"), 2, 12
    ) == Decimal("1100.00")


def test_zero_or_negative_quantity_rejected():
    with pytest.raises(HTTPException) as error:
        calculate_item_total(item(), price(), 0, 0)
    assert error.value.status_code == 422


def test_negative_catalogue_amount_rejected():
    with pytest.raises(HTTPException) as error:
        calculate_item_total(item(), price("-1.00"), 1, 0)
    assert error.value.status_code == 409


def test_unimplemented_pricing_model_fails_closed():
    with pytest.raises(HTTPException) as error:
        calculate_item_total(item("usage_metered"), price(), 1, 0)
    assert error.value.status_code == 409


def test_money_rounding_is_decimal_half_up():
    assert money(Decimal("1.005")) == Decimal("1.01")
