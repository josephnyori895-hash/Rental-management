#!/usr/bin/env sh
# Container entrypoint: bring the schema up to date, then serve.
#
# Migrations run before the API accepts traffic so a deploy can never serve
# requests against a schema older than the code. `alembic upgrade head` is
# idempotent, and on a single instance there is no concurrent-run race.
set -e

echo "[entrypoint] Applying migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Starting API on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:create_app \
    --factory \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
