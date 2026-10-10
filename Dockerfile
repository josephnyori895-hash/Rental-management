# syntax=docker/dockerfile:1
#
# One image, one service, one origin.
#
# The product is written same-origin — the SPA fetches relative `/api/...`
# paths — so the API serves the built frontend itself (see
# `app/main.py::_mount_frontend`). That means no CORS to configure, no
# build-time API URL to keep in sync, and the whole thing fits on a single free
# instance instead of two.

# ── Stage 1: build the frontend ──────────────────────────────────────
FROM node:22-alpine AS frontend

WORKDIR /app/frontend

# Dependencies first, so a source change does not re-resolve the whole tree.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# `npm run build` runs `tsc --noEmit && vite build`, so a type error fails the
# image instead of shipping.
RUN npm run build


# ── Stage 2: runtime ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# passlib imports the stdlib `crypt` module, which is gone in 3.13 — the pin in
# requirements.txt and this base image are both load-bearing.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl only, for the container health check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist

# `main.py` resolves the frontend relative to itself as parents[2]/frontend/dist,
# so the layout above is what makes the SPA resolve — `/app/frontend/dist`.

# Uploaded documents land here. On a free instance the filesystem is ephemeral,
# so these are lost on redeploy; move to object storage before real use.
RUN mkdir -p /app/storage && chmod +x /app/backend/docker-entrypoint.sh

# Non-root at runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend

EXPOSE 8000

# Migrations run here, so a deploy cannot serve traffic against an old schema.
# The entrypoint execs uvicorn, so it stays PID 1 and receives signals.
CMD ["./docker-entrypoint.sh"]
