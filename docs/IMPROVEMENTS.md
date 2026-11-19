# Improvement backlog

Prioritised, evidence-backed list from a read-only repo survey (November 2026).
Status is updated here as items land. `P0` = exploitable today, `P1` = money or
data integrity, `P2` = reliability/operations, `P3` = maintainability.

## P0 — Security holes exploitable today

- [ ] **WhatsApp webhook is unauthenticated** — `app/notifications/webhook_router.py`
  is public and executes `BALANCE` / `PAY` / `ADD …` from a body-supplied
  `from` number. Add a shared secret in the URL (the M-PESA pattern) and refuse
  to serve it unset in production.
- [ ] **M-PESA callback fails open** — `app/payments/router.py` skips verification
  when `MPESA_CALLBACK_SECRET` is empty or a `change-…` placeholder.
- [ ] **Airtel callback fails open** — same file, `if expected and not compare_digest(...)`.
  Flutterwave (`verif-hash`) is the only gateway verified unconditionally.
- [ ] **Facebook POST webhook is unverified** — `app/social/bot.py` never checks
  `X-Hub-Signature-256`; `FB_WEBHOOK_SECRET` defaults to `""`.
- [ ] **`/payments/simulate` has no `APP_ENV` guard** — reachable in production.
- [ ] **Default secrets boot silently** — `SECRET_KEY` / `ENCRYPTION_KEY` default to
  `change-me-in-production`; refuse to start with them when `APP_ENV=production`.
- [ ] **PIN login is only IP-limited** — 4-digit PIN with 5/min/IP, no per-account
  lockout.
- [ ] **Refresh tokens never rotate or revoke** — stolen token valid 7 days, survives
  password change, logout is client-side only.

## P1 — Money and data integrity

- [x] **`scripts/backfill_accounting.py` wiped every business's ledger** —
  now scoped to one business (`--business <slug|id>`), with `--dry-run`, and the
  summary count is per business.
- [x] **Airtel `collect()` truncated balances to whole shillings** —
  `int(inv.balance)` floored cents; now sends a 2-dp `Decimal`.
- [x] **Dead duplicate account model** — removed `Account` (table `accounts`) and
  `SYSTEM_ACCOUNTS`; the live ledger is `app/accounting/models.py::ChartOfAccount`.
- [ ] **Deposit refunds cannot be recorded** — `DepositRefund` is only read, so the
  Dr 2100 / Cr 1000 leg has no write path.
- [ ] **Utility tariffs have no effective dating**.
- [ ] **`created_at` index drift** — models declare `index=True`, no migration
  creates those indexes.
- [ ] **No automated backups / PITR** — biggest operational risk for a system of
  record.

## P2 — Reliability and operations

- [ ] **No CI** — add a workflow with a Postgres service container; 76 tests skip
  without one.
- [ ] **Scheduled work is in-process and unlocked** — sleeps with the free instance;
  N workers run N sweeps. Add a DB advisory lock or a real worker.
- [ ] **Uploaded documents sit on the ephemeral filesystem**.
- [ ] **Observability is `/health` only** — no request IDs, metrics, error tracking;
  `LOG_LEVEL` defaults to `DEBUG`.
- [ ] **Python 3.13 is blocked by passlib/crypt** — migrate to `bcrypt`/`pwdlib`.
- [ ] **Frontend has no tests, lint or typecheck step** — and three oversized
  components (`OwnerBoard.tsx`, `BuildingCanvas.tsx`, `BooksPage.tsx`).

## P3 — Maintainability

- [ ] **Stale docs after the scheduler work** — README known gap 11, `docs/DEPLOY.md`
  caveat row, "Not yet done" bullet, and the "35 database-backed tests" figure.
- [ ] **`docs/ROADMAP.md` counts are outdated** (says 132 tests / 70 paths).
- [ ] **Tenant isolation relies on hand-written `business_id` filters** — consider a
  scoped repository/session wrapper or RLS.
- [ ] **`scripts/seed_user.py` attaches to `select(Business).limit(1)`** — should take
  a slug.
