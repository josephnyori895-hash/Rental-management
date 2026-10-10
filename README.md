# Rental OS

Property and hostel management platform for the Kenyan rental market:
properties → units → leases → rent billing → M-PESA collection → accounting →
reports, with a tenant self-service portal and SMS/WhatsApp notifications.

This working copy is the source of `josephnyori895-hash/Rental-management`.

## Capabilities

| Area | What's implemented |
|---|---|
| Portfolio | Properties, units, building/floorplan canvas views |
| Tenancy | Leases, tenants, enrollment flow, caretaker dashboard |
| Billing | Rent invoices, billing runs, monthly scheduler, utility/service-charge tariffs with meter readings and shared-cost apportionment |
| Collections | M-PESA Daraja STK push + callbacks, reconciliation, payment matching |
| Accounting | Chart of accounts, ledger, backfill of historical payments |
| Reporting | Owner console, analytics, PDF statements, eTIMS payloads |
| Documents | Uploads and per-tenant document vault |
| Messaging | Africa's Talking SMS, WhatsApp, inbound message handling, webhook router |
| Portal | Tenant-facing self-service endpoints |
| Social | Facebook/Instagram bot webhook |

## Stack

- **Backend** — FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic, PostgreSQL
- **Frontend** — React 19 + TypeScript + Vite 6 + TailwindCSS 3 (PWA: manifest + service worker)
- **Desktop** — Tauri 2 shell (`frontend/src-tauri`); `rental_desktop.py` is a legacy GTK/WebKit launcher
- **Python** — 3.12

## Layout

```
rental-os/
├── backend/
│   ├── app/
│   │   ├── main.py              # app factory, router mounting, /health
│   │   ├── core/                # config, database, security, encryption, events, ratelimit
│   │   ├── models/              # SQLAlchemy models (base, property, lease, tenant, billing, …)
│   │   ├── api/                 # shared deps (require_owner) and error handlers
│   │   └── <domain>/            # one package per domain: router.py + service.py (+ models/schemas)
│   ├── migrations/versions/     # Alembic revisions
│   ├── scripts/                 # seeders, backfills, stress test, verification
│   ├── requirements.txt         # pinned runtime deps
│   ├── requirements-dev.txt     # pytest + ruff
│   └── .env.example             # every supported setting
├── frontend/
│   ├── src/{pages,components,lib,styles}
│   └── src-tauri/               # Tauri desktop wrapper
├── deploy/nginx-rental.conf
├── secure/                      # live credentials vault (gitignored)
└── rental.sh                    # start backend + frontend + desktop
```

Domain packages: `accounting`, `analytics`, `auth`, `billing`, `dashboard`,
`documents`, `expenses`, `maintenance`, `notifications`, `payments`, `portal`,
`properties`, `reconciliation`, `reports`, `social`, `tenants`.

Unauthenticated routes are mounted explicitly (login, M-PESA callback, WhatsApp
webhook, social bot); everything else is gated behind `require_owner`.
API prefix is `/api/v1`; `/docs` and `/redoc` are disabled when `APP_ENV=production`.

## Getting started

```bash
# 1. Backend
cd backend
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY
./venv/bin/alembic upgrade head
./venv/bin/python -m uvicorn app.main:app --reload --port 8011

# 2. Frontend
cd frontend
npm ci
npm run dev                   # http://localhost:5173
```

Backend must be started from `backend/` — `alembic.ini` and the `.env` lookup are
both CWD-relative.

Or start everything at once:

```bash
./rental.sh                   # backend :8011, Vite :5173, desktop shell
```

### Seed data

```bash
cd backend
./venv/bin/python scripts/seed_user.py       # create the first owner login
./venv/bin/python scripts/seed.py            # properties, units, tenants, leases
./venv/bin/python scripts/seed_ops.py        # maintenance + expenses
./venv/bin/python scripts/seed_payments.py   # sample M-PESA payments
```

## Configuration

All settings live in `backend/app/core/config.py` and are documented in
`backend/.env.example`. Nothing is read from anywhere else — if a value is not
in that template it is not configurable.

Secrets: `backend/.env` and `secure/credentials.env` are gitignored and must
stay that way. Before any real deployment, replace `SECRET_KEY`,
`JWT_SECRET` and `ENCRYPTION_KEY` (the `change-me-in-production` defaults) —
`ENCRYPTION_KEY` protects M-PESA credentials at rest, so rotating it makes
previously stored credentials unreadable.

### M-PESA callback security

`POST /api/v1/payments/mpesa/callback` is unauthenticated by necessity
(Safaricom cannot send a bearer token), so it is protected by a shared secret in
the callback URL:

```
https://<host>/api/v1/payments/mpesa/callback?token=<MPESA_CALLBACK_SECRET>
```

Set `MPESA_CALLBACK_SECRET` to a random value and register the tokenised URL with
Daraja. **While the secret is empty or left at a `change-...` placeholder the
check is skipped** (a warning is logged), and any POST that names a known
`CheckoutRequestID` will be accepted as a payment.

## Deployment

One service serves both the API and the built frontend, so there is no CORS to
configure and no build-time API URL to keep in sync. Full walkthrough:
[`docs/DEPLOY.md`](docs/DEPLOY.md).

```bash
docker build -t rental-os .
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e ENCRYPTION_KEY=... rental-os
```

The image runs `alembic upgrade head` before serving, so a deploy cannot serve
traffic against an older schema. `render.yaml` is a Render blueprint that
provisions a single free web service.

> **Free-tier trap:** Render's free PostgreSQL expires 30 days after creation
> and takes the data with it, so the blueprint declares no database and takes
> `DATABASE_URL` from Neon instead (free plan, no expiry). `tests/test_deploy.py`
> fails if a self-expiring database is ever added back.

## Testing

```bash
cd backend
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/python -m pytest          # 245 tests
```

**210 of them run with no database at all.** They cover JWT issuance and
validation (including `alg: none`, tampering and expiry), password hashing, the
M-PESA callback shared-secret check, rate limiter behaviour, configuration
defaults and app wiring, plus areas that would otherwise only fail in
production:

- **Money arithmetic** — utility consumption, pricing, and apportionment that is
  remainder-exact (per-unit shares must sum to the total, or the ledger drifts).
- **Report and billing queries** — compiled against the real PostgreSQL dialect,
  including bound parameters, so a malformed column or join fails here.
- **Models vs migrations** — the utility migration is rendered offline and
  compared column-by-column against the models, and the revision history is
  checked for a single linear chain with one head.
- **Route bodies** — the utility billing routes are called directly with a stub
  session, exercising consumption → tariff lookup → invoice without a database.
- **Ledger account codes** — every account code the source resolves is
  cross-checked against the chart of accounts the application provisions, and the
  indirect category tables (`EXPENSE_ACCOUNT_CODES`) are checked separately,
  since a lookup that passes a variable is invisible to a literal scan. A code
  that is looked up but never created is a posting that silently never happens;
  see the utility-income note under [Known gaps](#known-gaps).
- **Ledger silent drops** — all three posting hooks are asserted to *log* when
  an account cannot be resolved rather than returning quietly, and an `ast` guard
  fails if any posting call is ever wrapped in a bare `except: pass`. Best-effort
  posting is fine; best-effort posting that reports nothing is not.

### Database-backed tests (tenant isolation)

The remaining **35 tests need PostgreSQL**, because tenant isolation cannot be
verified any other way: it is enforced by a `business_id` filter written
separately in every router, and a missing one returns another operator's data
while every other test still passes.

They run against a **scratch** database, never the development one. By default
the URL is `DATABASE_URL` with `_test` appended to the database name; override
with `TEST_DATABASE_URL`. If that database is unreachable, these tests **skip**
rather than fail, so `pytest` still works on a machine without PostgreSQL.

```bash
# one-time setup
sudo -u postgres createdb -O rental rental_test
cd backend && ./venv/bin/python -m pytest
# 245 passed            (database reachable)
# 210 passed, 35 skipped (database not reachable)
```

Each test runs inside a transaction that is always rolled back — routes commit
into a savepoint — so the scratch database is left exactly as it was found.

> If `createdb` fails with *"collation version mismatch"*, the cluster was
> built before a glibc upgrade. Fix it once per cluster:
> `ALTER DATABASE template1 REFRESH COLLATION VERSION;`

`backend/scripts/verify_full_system_logic.py` and
`backend/scripts/stress_test_capacity.py` are manual verification scripts, not
tests.

## Migrations

```bash
cd backend
./venv/bin/alembic revision --autogenerate -m "describe change"
./venv/bin/alembic upgrade head
./venv/bin/alembic downgrade -1
```

## Known gaps

Concrete, verified gaps in this repository:

1. **No CI** — nothing runs on push. Note that a CI run without a database
   would silently skip the 29 database-backed tests, so the workflow needs a
   PostgreSQL service container to be meaningful.
2. **Dead duplicate account model** — `app/models/accounting.py` defines
   `Account` (table `accounts`) *and* `SYSTEM_ACCOUNTS`, neither of which
   anything reads: the live ledger is `app/accounting/models.py::ChartOfAccount`
   (table `chart_of_accounts`). The `accounts` table exists in the live database
   with **0 rows** and is created by no migration — it only appears when
   something calls `Base.metadata.create_all`. `app/models/accounting.py` also
   owns the `journal_entries` table, so it cannot simply be deleted; the
   duplicate `Account` and `SYSTEM_ACCOUNTS` can.
3. **`/payments/simulate` moves no money** — owner-only, but it has no
   `APP_ENV` guard, so it is reachable in production.
4. **Two desktop shells** — the Tauri app and `rental_desktop.py` overlap.
5. **Oversized modules** — the backend notifications and reports
   modules have been split: `notifications/inbound.py` → `inbound.py` +
   `inbound_tenant.py` + `inbound_user.py`; `reports/router.py` → `router.py` +
   `statement.py` + `books.py` + `exports.py`; `notifications/service.py` →
   `service.py` + `templates.py`. Remaining are frontend-only (`OwnerBoard.tsx` 692,
   `BuildingCanvas.tsx` 670, `BooksPage.tsx` 637) — the frontend cannot be
   typechecked until `npm ci` runs.
6. **Python 3.13 is not supported** — passlib imports the stdlib `crypt` module,
   which is removed in 3.13. Stay on 3.12 (see the `bcrypt` pin in
   `requirements.txt`).
7. **In-process rate limiting** — `core/ratelimit.py` keys on
   `X-Forwarded-For`, which a client can spoof to get a fresh quota. Fine behind
   a proxy that overwrites the header; not fine if exposed directly.
8. **Model/migration drift on `created_at`** — `TimestampMixin.created_at` is
   declared `index=True`, but no migration in `migrations/versions/` ever
   created those indexes, so the models and the live database disagree. Adding
   the model/migration comparison test made this visible; it is pinned, not yet
   fixed.
9. **Utility tariffs have no effective dating** — editing a rate changes future
   readings only in the sense that nothing re-prices: readings already raised
   keep their original rate. Add effective-dated tariffs before rates change
   often in production.
10. **Deposit refunds cannot be recorded** — a deposit invoice now posts
    correctly (Dr 1100 / Cr 2100), and payments clear it via receivables, but
    `DepositRefund` is only ever *read*, so the refund leg (Dr 2100 / Cr 1000)
    has nothing to hang off. A test fails the moment one is created, forcing the
    posting to land with it.
11. **Rent invoices are raised once, at enrollment** — `enroll_tenant` creates
    the first rent invoice and any deposit invoice, and both now post. There is
    no recurring monthly rent-invoice generator, so a tenancy does not accrue
    further invoices on its own.

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the competitive analysis and the
phased plan (Phase 0 cleanup → table-stakes gaps → moat → real-estate/agency).
