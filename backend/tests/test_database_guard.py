from __future__ import annotations

import pytest

from tests.conftest import (
    _normalise_host,
    _require_scratch_database,
    _resolved_target,
    _same_target,
)

PROD = "postgresql+asyncpg://u:p@localhost:5432/rental"


def _url(host: str, database: str, port: str | None = None) -> str:
    authority_host = f"[{host}]" if ":" in host else host
    authority = f"{authority_host}:{port}" if port else authority_host
    return f"postgresql+asyncpg://u:p@{authority}/{database}"


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", None])
def test_every_loopback_spelling_normalises_to_one_host(host):
    assert _normalise_host(host) == "loopback"


def test_localhost_and_loopback_ip_are_the_same_target():
    assert _same_target(_url("localhost", "rental_test"), _url("127.0.0.1", "rental_test"))
    assert _same_target(_url("localhost", "rental_test"), _url("::1", "rental_test"))


def test_omitted_port_equals_the_default_postgres_port():
    assert _resolved_target(_url("localhost", "rental_test"))[1] == 5432
    assert _same_target(_url("localhost", "rental_test"), _url("localhost", "rental_test", "5432"))


def test_a_different_port_is_a_different_target():
    assert not _same_target(
        _url("localhost", "rental_test"), _url("localhost", "rental_test", "5433")
    )


def test_same_named_database_on_a_differently_written_host_is_refused():
    """Conservative: the database name alone is enough to refuse."""
    production = _url("localhost", "scratch_test", "5432")

    with pytest.raises(RuntimeError, match="named like the production database"):
        _require_scratch_database(_url("127.0.0.1", "scratch_test"), production)


def test_same_named_database_on_another_host_is_refused():
    production = _url("db.internal", "scratch_test")

    with pytest.raises(RuntimeError, match="named like the production database"):
        _require_scratch_database(_url("other.internal", "scratch_test"), production)


def test_identical_target_reached_through_different_host_spellings_is_refused():
    production = _url("localhost", "scratch_test")

    with pytest.raises(RuntimeError):
        _require_scratch_database(_url("127.0.0.1", "scratch_test", "5432"), production)


def test_a_genuinely_separate_scratch_database_is_accepted():
    _require_scratch_database(_url("localhost", "rental_test", "5432"), PROD)


def test_a_scratch_database_on_another_host_is_accepted():
    _require_scratch_database(_url("db.internal", "rental_test"), PROD)


def test_a_database_without_the_test_suffix_is_refused():
    with pytest.raises(RuntimeError, match="must end with '_test'"):
        _require_scratch_database(_url("localhost", "rental"), PROD)


def test_an_unknown_production_target_is_refused():
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        _require_scratch_database(_url("localhost", "rental_test"), "")
