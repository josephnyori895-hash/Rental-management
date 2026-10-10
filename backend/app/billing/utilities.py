"""
RENTAL OS — Utility Billing Logic (pure)

Module:
    Consumption, pricing, apportionment, tariff resolution and the
    caretaker's WhatsApp meter-reading grammar.

Purpose:
    Everything here is a pure function over plain values or detached model
    objects — no session, no I/O. That is deliberate: this is where the
    money arithmetic lives, so it is the part that must be unit-testable
    without a database.

Money is always `Decimal` quantized to 2dp (ROUND_HALF_UP) and meter
readings to 3dp, because KES amounts and kWh/litre readings are both
rounded at these places and float drift is not acceptable in a ledger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable, Sequence

from app.models.utilities import SplitMethod, UtilityType

MONEY_PLACES = Decimal("0.01")
UNIT_PLACES = Decimal("0.001")
ZERO = Decimal("0")

# Revenue account per utility type, keyed to the codes that `DEFAULT_COA`
# in `app.accounting.service` actually provisions. Utilities are not rent:
# a water recharge must land on "Water Bill Income" so it never inflates
# the rental income line on the P&L.
#
# These codes are guarded by a test that asserts every account code the
# application references exists in `DEFAULT_COA`. That guard exists
# because the first version of this module posted to "4200 Utility
# Reimbursement" — a code that was only ever declared on a dead duplicate
# model and that no business has, so every utility invoice was written and
# then quietly never posted to the ledger at all.
UTILITY_INCOME_CODES: dict[str, str] = {
    UtilityType.WATER.value: "4030",          # Water Bill Income
    UtilityType.ELECTRICITY.value: "4040",    # Electricity Income
    UtilityType.SERVICE_CHARGE.value: "4010",  # Service Charge Income
}

# Gas, WiFi, garbage and "other" have no dedicated revenue account; they
# post to Other Income rather than guessing at a closer match.
UTILITY_FALLBACK_INCOME_CODE = "4050"
DEFAULT_UTILITY_DUE_DAYS = 7


def income_code_for(utility_type: str | None) -> str:
    """Revenue account code that a utility charge posts to.

    An unnamed or unrecognised utility falls back to "Other Income" — it
    is never allowed to default to rental income, because a mislabelled
    revenue line is harder to notice than a missing one.
    """
    if not utility_type:
        return UTILITY_FALLBACK_INCOME_CODE
    return UTILITY_INCOME_CODES.get(
        str(utility_type).lower(), UTILITY_FALLBACK_INCOME_CODE
    )

# WhatsApp grammar ────────────────────────────────────────────────
#
#   <reading>                  bulk reading (3-7 digits)
#   WATER <reading>            bulk reading for a named utility
#   METER <unit> <reading>     unit reading
#   WATER <unit> <reading>     unit reading for a named utility
#
# Aliases map to a UtilityType value; METER maps to None ("no utility named").
UTILITY_ALIASES: dict[str, str | None] = {
    "METER": None,
    "READING": None,
    "WATER": UtilityType.WATER.value,
    "W": UtilityType.WATER.value,
    "ELEC": UtilityType.ELECTRICITY.value,
    "ELECTRICITY": UtilityType.ELECTRICITY.value,
    "POWER": UtilityType.ELECTRICITY.value,
    "GAS": UtilityType.GAS.value,
    "WIFI": UtilityType.WIFI.value,
    "INTERNET": UtilityType.WIFI.value,
    "GARBAGE": UtilityType.GARBAGE.value,
    "TRASH": UtilityType.GARBAGE.value,
    "SERVICE": UtilityType.SERVICE_CHARGE.value,
    "SERVICECHARGE": UtilityType.SERVICE_CHARGE.value,
}

_READING_RE = re.compile(r"^\d{1,7}(?:\.\d{1,3})?$")
# A bare number needs >= 3 digits: "2" or "12" is far more likely to be a
# typo or a stray reply than a meter reading, and silently recording it
# would corrupt the consumption chain for that meter.
_BARE_READING_RE = re.compile(r"^\d{3,7}(?:\.\d{1,3})?$")
_UNIT_REF_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{0,11}$")


class ReadingError(ValueError):
    """A meter reading that cannot be turned into a consumption figure."""


@dataclass(frozen=True)
class MeterCommand:
    """A parsed caretaker meter-reading message."""

    reading: Decimal
    unit_ref: str | None = None
    utility_type: str | None = None


def parse_meter_command(raw_text: str) -> MeterCommand | None:
    """Parse a WhatsApp message into a meter-reading command.

    Returns ``None`` when the message is not a reading at all, so the caller
    can fall through to its "unknown command" reply.
    """
    if not raw_text or not raw_text.strip():
        return None

    tokens = raw_text.strip().upper().replace(",", "").split()
    if not tokens:
        return None

    utility: str | None = None
    if tokens[0] in UTILITY_ALIASES:
        utility = UTILITY_ALIASES[tokens[0]]
        tokens = tokens[1:]

    if len(tokens) == 1:
        token = tokens[0]
        pattern = _READING_RE if utility else _BARE_READING_RE
        if not pattern.match(token):
            return None
        return MeterCommand(reading=Decimal(token), utility_type=utility)

    if len(tokens) == 2:
        unit_ref, token = tokens
        if not _UNIT_REF_RE.match(unit_ref) or not _READING_RE.match(token):
            return None
        return MeterCommand(reading=Decimal(token), unit_ref=unit_ref, utility_type=utility)

    return None


# ── Arithmetic ─────────────────────────────────────────────────────


def quantize_money(value: Decimal | float | int | str) -> Decimal:
    """Round to the shilling place, half-up (the KES convention)."""
    return _to_decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def quantize_units(value: Decimal | float | int | str) -> Decimal:
    """Round a meter reading / consumption to 3 decimal places."""
    return _to_decimal(value).quantize(UNIT_PLACES, rounding=ROUND_HALF_UP)


def _to_decimal(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ReadingError(f"Not a number: {value!r}") from exc


def compute_consumption(
    previous: Decimal | float | int | str | None,
    current: Decimal | float | int | str,
) -> Decimal:
    """Consumption between two readings.

    A missing `previous` (first ever reading for that meter) is a baseline:
    it yields zero consumption, not the whole odometer.
    """
    current_d = quantize_units(current)
    if previous is None:
        return ZERO
    previous_d = quantize_units(previous)
    if current_d < previous_d:
        raise ReadingError(
            f"Meter reading {current_d} is lower than the previous reading "
            f"{previous_d}."
        )
    return quantize_units(current_d - previous_d)


def compute_amount(
    units_consumed: Decimal | float | int | str,
    rate_per_unit: Decimal | float | int | str = 0,
    fixed_charge: Decimal | float | int | str = 0,
) -> Decimal:
    """Charge for a consumption figure: ``units x rate + fixed charge``."""
    consumed = _to_decimal(units_consumed)
    if consumed < 0:
        raise ReadingError(f"Negative consumption: {consumed}")
    total = consumed * _to_decimal(rate_per_unit) + _to_decimal(fixed_charge)
    return quantize_money(max(total, ZERO))


def apportion(
    total: Decimal | float | int | str,
    weights: Sequence[Decimal | float | int | str],
    method: str = SplitMethod.METERED.value,
) -> list[Decimal]:
    """Split `total` across units so the parts sum *exactly* to the total.

    Naive proportional rounding loses (or invents) a cent; on a 60-unit block
    that becomes a recurring unreconciled balance in the ledger, so the
    rounding remainder is pushed onto the largest share here.
    """
    total_d = quantize_money(total)
    count = len(weights)
    if count == 0:
        raise ReadingError("Cannot apportion across zero units.")

    if method == SplitMethod.EQUAL.value:
        raw = [Decimal(1)] * count
    else:
        raw = [max(_to_decimal(w), ZERO) for w in weights]
        if sum(raw) <= ZERO:
            # No usable weights (e.g. "metered" split with no unit meters) —
            # falling back to an even split beats billing nobody.
            raw = [Decimal(1)] * count

    total_weight = sum(raw)
    shares = [
        (total_d * weight / total_weight).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
        for weight in raw
    ]

    remainder = total_d - sum(shares)
    if remainder != ZERO:
        # Deterministic: the largest share absorbs the rounding drift.
        target = max(range(count), key=lambda i: (shares[i], -i))
        shares[target] = quantize_money(shares[target] + remainder)

    return shares


# ── Tariff / rule resolution ───────────────────────────────────────


def resolve_rate(rates: Iterable, utility_type: str, unit_id=None):
    """Pick the applicable `UtilityRate` for a unit and utility type.

    A unit-specific rate beats the property-wide default. Inactive rates are
    ignored. Returns ``None`` when no tariff has been configured — callers
    must not silently invent a price.
    """
    active = [
        rate for rate in rates
        if getattr(rate, "is_active", True)
        and getattr(rate, "utility_type", None) == utility_type
    ]
    if unit_id is not None:
        for rate in active:
            if getattr(rate, "unit_id", None) == unit_id:
                return rate
    for rate in active:
        if getattr(rate, "unit_id", None) is None:
            return rate
    return None


def split_method_for(rate, default: str = SplitMethod.METERED.value) -> str:
    """The split method declared by a tariff, or `default` when unset."""
    method = getattr(rate, "split_method", None) if rate is not None else None
    return method or default


def build_weights(units: Iterable, method: str) -> tuple[list[Decimal], list[str]]:
    """Build apportionment weights for `units` under `method`.

    Each unit object must expose `unit_number`, `max_occupants`,
    `monthly_rent` and `consumed` (consumption in the period, or ``None``).

    Returns ``(weights, missing_unit_numbers)``. A non-empty `missing` list
    means the chosen method cannot be honoured yet — for a `metered` split
    every occupied unit needs its own reading.
    """
    units = list(units)

    if method == SplitMethod.EQUAL.value:
        return [Decimal(1)] * len(units), []
    if method == SplitMethod.OCCUPANCY.value:
        return [Decimal(max(int(getattr(u, "max_occupants", 1) or 1), 0)) for u in units], []
    if method == SplitMethod.RENT.value:
        return [max(_to_decimal(getattr(u, "monthly_rent", 0) or 0), ZERO) for u in units], []

    missing = [u.unit_number for u in units if getattr(u, "consumed", None) is None]
    weights = [
        max(_to_decimal(getattr(u, "consumed", 0) or 0), ZERO) for u in units
    ]
    return weights, missing
