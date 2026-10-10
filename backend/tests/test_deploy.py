"""
Deployment invariants.

These are the deploy-level facts that either work or fail loudly at 2am, and
that nothing else in the suite touches. A hosted Postgres DSN is not a local
one: it carries `sslmode`, and it is often behind a connection pooler, neither
of which asyncpg reads from a URL. Getting that wrong means a deploy that
imports cleanly and then cannot open a connection.

The rest guard the shape of the deployment rather than its code — the free
database that deletes itself after 30 days, and the credentials that must not be
baked into an image.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.database import _connect_args_and_url

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_YAML = REPO_ROOT / "render.yaml"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
ENTRYPOINT = REPO_ROOT / "backend" / "docker-entrypoint.sh"


# ── DSN translation ────────────────────────────────────────────────


def test_a_local_dsn_is_left_alone():
    args, url = _connect_args_and_url("postgresql+asyncpg://imani:imani@localhost:5432/rental")
    assert args == {}
    assert url == "postgresql+asyncpg://imani:imani@localhost:5432/rental"


def test_sslmode_becomes_asyncpgs_ssl_argument():
    """A hosted DSN says `?sslmode=require`; asyncpg does not read that."""
    args, _ = _connect_args_and_url(
        "postgresql+asyncpg://u:p@db.example.com:5432/rental?sslmode=require"
    )
    assert args["ssl"] == "require"


def test_a_pooler_host_disables_the_statement_cache():
    """Cached prepared statements do not survive a transaction-mode pooler.

    This is the failure that looks like a random intermittent 500 under load —
    `prepared statement "__asyncpg_stmt_1__" does not exist` — and it is not
    reproducible locally, because a direct connection has no pooler in front.
    """
    args, _ = _connect_args_and_url(
        "postgresql+asyncpg://u:p@ep-cool-1234-pooler.eu-central-1.aws.neon.tech/rental?sslmode=require"
    )
    assert args["statement_cache_size"] == 0
    assert args["ssl"] == "require"


def test_a_direct_host_keeps_the_statement_cache():
    args, _ = _connect_args_and_url(
        "postgresql+asyncpg://u:p@direct.example.com:5432/rental?sslmode=require"
    )
    assert "statement_cache_size" not in args


def test_an_explicit_statement_cache_setting_wins_over_detection():
    args, _ = _connect_args_and_url(
        "postgresql+asyncpg://u:p@plain.example.com/rental?statement_cache_size=0"
    )
    assert args["statement_cache_size"] == 0


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql+asyncpg://u:p@h/rental?sslmode=require",
        "postgresql+asyncpg://u:p@h/rental?ssl=require&statement_cache_size=0",
    ],
)
def test_translated_keys_are_removed_from_the_url(dsn):
    """Left in place, SQLAlchemy's asyncpg dialect rejects them as unknown."""
    _, url = _connect_args_and_url(dsn)
    assert "sslmode" not in url
    assert "statement_cache_size" not in url


def test_the_dsn_helpers_run_at_import_time():
    """The app engine and alembic both read these, so they must exist."""
    from app.core import database

    assert isinstance(database.DATABASE_URL, str)
    assert isinstance(database.DATABASE_CONNECT_ARGS, dict)
    assert database.engine is not None


# ── Deployment shape ───────────────────────────────────────────────


def test_no_self_expiring_database_is_configured():
    """Render's free Postgres is deleted 30 days after creation.

    A rent ledger is a system of record; it must not be configured to disappear
    on a schedule. The blueprint therefore declares no database and takes
    `DATABASE_URL` from elsewhere (Neon's free plan does not expire).
    """
    text = RENDER_YAML.read_text(encoding="utf-8")
    assert "type: postgres" not in text and "databases:" not in text, (
        "render.yaml declares a Render database — if that is a free plan it "
        "expires 30 days after creation and takes the books with it"
    )
    assert "DATABASE_URL" in text


def test_credentials_are_never_baked_into_the_image():
    """`.env` and `secure/` hold real keys and must stay out of the build."""
    patterns = DOCKERIGNORE.read_text(encoding="utf-8")
    assert "secure/" in patterns
    assert "**/.env" in patterns
    assert ".env.example" in patterns, "the template should still be available"


def test_the_encryption_key_is_not_auto_generated():
    """`encryption.py` calls `bytes.fromhex()`, so a random base64 value fails.

    A platform-generated secret looks like it works until the first encrypted
    write, which is a confusing way to find out.
    """
    text = RENDER_YAML.read_text(encoding="utf-8")
    block = text.split("ENCRYPTION_KEY", 1)[1].split("- key:", 1)[0]
    assert "generateValue: true" not in block, (
        "ENCRYPTION_KEY must be 64 hex chars from `openssl rand -hex 32`, "
        "not a platform-generated base64 secret"
    )
    assert "sync: false" in block


def test_the_container_migrates_before_it_serves():
    """A deploy must not serve traffic against an older schema."""
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert "alembic upgrade head" in text
    assert "uvicorn" in text
    assert text.index("alembic upgrade head") < text.index("uvicorn")
    assert "exec " in text, "exec keeps the server as PID 1 so it receives signals"


def test_the_container_serves_the_frontend_build():
    """One service on one origin — the API hosts the SPA."""
    text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "npm run build" in text, "the frontend must be built in the image"
    assert "/app/frontend/dist" in text, (
        "main.py resolves the build as parents[2]/frontend/dist"
    )
    assert "SERVE_FRONTEND" in RENDER_YAML.read_text(encoding="utf-8")


def test_the_container_runs_as_a_non_root_user():
    text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in text
