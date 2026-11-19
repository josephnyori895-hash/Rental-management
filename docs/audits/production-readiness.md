# Rental OS — Production-Readiness Audit

Audited revision: `138b12b` (merge of `review/properties-merge`).

Scope: authentication, authorization, business ownership, financial integrity,
migrations, backups and recovery. Frontend and user experience are deferred to a
later pass.

Method: static review of 15 routers and 68 endpoints, targeted probes against a
disposable scratch database, and inspection of configuration, schema and
deployment artefacts. No production data was read or modified.

Severity: **P0** blocks production; **P1** must be fixed before real money moves;
**P2** correctness and hygiene.

---

## P0 — blocks production

### P0-1 Cross-tenant payment write

`POST /payments/record`, `/simulate`, `/mpesa/stk`, `/airtel/stk` and
`/flutterwave/checkout` accept any `invoice_id` and resolve it by primary key
with no business check. `apply_payment` then writes a Payment row carrying the
victim's `business_id` and mutates the victim's invoice.

`app/payments/router.py:86-126`, `app/payments/service.py:63-129`

Observed: an owner of business A posting `{"invoice_id": <business B invoice>,
"amount": 100}` received `200 {"status":"partial","balance":14900}`; the invoice
of business B moved from `paid_amount 0` to `100` and `balance 15000` to `14900`,
with an additional payment row attached to it. One business wrote to another's
ledger and can mark their rent as collected.

### P0-2 Negative and over-balance amounts accepted

Payment request models take `amount: float` with no sign check and no balance
check; the invoice is then updated as `balance = amount - paid_amount`.

Observed: `amount = -5000` returned `200` and moved the invoice balance from
15000 to 20000 — a "payment" of minus five thousand credits the payer and
inflates their debt. An amount larger than the balance produces a negative
balance and status `paid`, silently absorbing the excess. The reconciliation
module handles this correctly; the payments module does not.

`app/payments/service.py:76-93`

### P0-3 Settled invoice silently swallows money

`apply_payment` returns immediately when the invoice is already `paid`, before
the Payment row is constructed. A payment recorded against a settled invoice
therefore reports success and leaves no trace: no payment row, no receipt, no
ledger entry.

Observed: after settling, a further `3000` returned
`200 {"status":"paid","balance":0}` while the payment row count on that invoice
was unchanged.

`app/payments/service.py:74-75`

### P0-4 Payment callbacks are unauthenticated in production

Both the M-Pesa STK callback and the C2B confirmation endpoints skip
verification when their shared secret is unset or still a placeholder, logging a
warning instead. A production configuration was observed with the STK callback
secret still a placeholder and the C2B secret unset, so forged callbacks were
accepted.

- `/payments/mpesa/callback` marks the invoice carrying a named
  `CheckoutRequestID` as paid.
- `/payments/mpesa/c2b/confirmation` records a payment attributed by the
  `BusinessShortCode` in the payload, falling back to "the only active business"
  when the shortcode is unknown. Shortcodes are public knowledge — they are
  printed on every payment prompt.

`app/payments/router.py:332-355`, `390-400`, `app/payments/c2b.py:36-57`

`validate_production_secrets` validates only `SECRET_KEY`, the JWT secret and
`ENCRYPTION_KEY`; it does not know about the payment webhook secrets.

`app/core/config.py:199-223`

### P0-5 CI cannot run the database suite

The scratch-database guard refuses any target whose database *name* equals the
production database name. The CI workflow sets both `DATABASE_URL` and
`TEST_DATABASE_URL` to the same `_test` database, so the guard fires at
collection time:

```
RuntimeError: refusing to run tests: the scratch database is named like the
production database
```

Every job that touches the database fails before a single test runs. Separately,
CI invokes `pytest` directly and never `scripts/verify.sh`, so the JUnit counts,
the skip refusal and the database-identity print are not part of the pipeline at
all.

`.github/workflows/verify.yml`

### P0-6 Unauthenticated social endpoints

The social router is mounted with no dependencies:

- `POST /api/v1/social/post` publishes to the business Instagram account.
- `POST /api/v1/social/send-reminder` sends a Messenger message to any recipient
  named in the query string.
- `GET /api/v1/social/instagram` returns the account feed using the platform
  token.

A webhook signature helper exists in the module and is never called.

`app/main.py:159`, `app/social/bot.py`

---

## P1 — fix before real money moves

### P1-1 Tenant portal is non-functional and unscoped

`GET /portal/my-data` reads `Invoice.is_deleted`, a column that does not exist on
the model, so every call raises `AttributeError` and returns 500. When a
`tenant_id` is supplied it is loaded by primary key with no business filter; with
no id it returns the first tenant in the business. There is no tenant
authentication: the route is owner-only, and the branch intended for tenant roles
is empty.

`app/portal/router.py:22-64`

### P1-2 No idempotency and no row lock

`payments.reference` is indexed but not unique. Provider callbacks retry, so the
same transaction can be applied twice, double-crediting the invoice and
double-posting the ledger. The balance is read without row-level locking, so two
concurrent callbacks race. The rent run is idempotent by overlap but checks for
an existing invoice and inserts in separate statements, so concurrent runs can
double-bill.

`app/payments/service.py:71-94`, `app/billing/rent_run.py`

### P1-3 Ledger divergence is only logged

Ledger posting is best-effort by design, wrapped in a bare `except Exception`
that logs a warning. The money moves and the journal does not. There is no report
reconciling invoice and payment totals against the trial balance, so divergence
is invisible until someone reads the logs.

`app/accounting/service.py:316-435`

### P1-4 No audit trail

The `audit_logs` table exists in the schema and is never written. Cash payments,
manual journal entries, deposit refunds and role changes have no attributable
record.

### P1-5 Rate limiting is advisory

The limiter is an in-process window per worker and trusts the
`X-Forwarded-For` header from any client, so a spoofed header resets the bucket.
`/auth/register` and `/auth/refresh` are not limited. Horizontally, each worker
gets its own budget.

`app/core/ratelimit.py`

### P1-6 Transport and exposure

The supplied nginx configuration serves plain HTTP with no TLS, no security
headers and no request limits. FastAPI disables the documentation routes in
production but leaves `/openapi.json` served.

`deploy/nginx-rental.conf`, `app/main.py`

### P1-7 Refresh tokens cannot be revoked

Refresh tokens carry no identifier, are not stored server-side, and are not
rotated with reuse detection. A stolen refresh token is valid for its full
lifetime and refreshing issues a new one.

`app/auth/service.py`, `app/core/security.py`

### P1-8 Document upload is unbounded

No size cap, no MIME allowlist, and the whole file is read into memory before
being written. Storage is the container filesystem, which is ephemeral on the
documented deployment target, so uploads are lost on redeploy and are not
covered by any backup.

`app/documents/service.py`

---

## P2 — correctness and hygiene

| # | Finding | Location |
|---|---------|----------|
| P2-1 | CORS origins parse into strings retaining literal JSON quotes, so no origin ever matches. Same-origin traffic is unaffected; cross-origin CORS is silently dead. | `app/core/config.py:87-98` |
| P2-2 | Malformed UUIDs in path or body raise `ValueError` and return 500 instead of 400. | `billing/router.py:171`, `documents/router.py`, `tenants/router.py:131` |
| P2-3 | The direct STK path pushes a payment request to any phone and amount using platform-wide Daraja credentials rather than the business's own. | `app/payments/service.py:212` |
| P2-4 | No invoice void, credit note or reversal. The `cancelled` and `refunded` statuses are never set by any code path. | `app/models/billing.py`, `app/billing/` |
| P2-5 | `invoice_number` is nullable and non-unique; there is no `CHECK (balance >= 0)`; there is no uniqueness constraint on `(lease_id, period_start)`. | `migrations/versions/8f53e6620282_initial_rental_schema.py` |
| P2-6 | Money crosses the API boundary as `float` in request models while internally `Decimal`. | `app/payments/router.py`, `app/billing/router.py` |

Modules without meaningful test coverage: portal, social, reconciliation,
accounting journal, documents, analytics, the notifications router, report
exports, and deposit refunds end to end.

---

## Migrations, backups and recovery

Migrations are the healthiest area: eight revisions, a single head, additive
changes with foreign keys and working downgrades. The container entrypoint runs
`alembic upgrade head` before accepting traffic, and the runtime user is
non-root.

Gaps:

- No backup automation: no schedule, no retention policy, no offsite copy, no
  encrypted backup, no restore rehearsal.
- No point-in-time recovery; WAL archiving is not configured.
- No pre-migration snapshot, so a failed upgrade has no data rollback path, and
  downgrades are untested against real data.
- Uploaded documents live on the container filesystem and are excluded from any
  backup story.
- `docs/RECOVERY.md` documents recovery of the source tree, not of the database.
  There is no runbook for restoring a dump into a clean instance.
- No monitoring beyond `/health`, and no alerting on failed ledger postings,
  failed callbacks or runaway scheduler tasks.
- The scheduler is in-process. With more than one worker, reminder sweeps
  duplicate, and rent runs depend on the check-then-insert behaviour above.

---

## What is already sound

- Token handling: the algorithm is pinned, the signature is verified, `exp` and
  `sub` are required, and business scope is resolved from the user row rather
  than from token claims.
- Business scoping in properties, tenants, maintenance, expenses, dashboard,
  analytics, accounting, reports, reconciliation, documents and notifications is
  present and tested.
- The property-level ownership helper returns 404 rather than 403, so a foreign
  id is indistinguishable from a missing one.
- The release gate reads counts from JUnit XML, fails on skips, and refuses a
  test database it cannot positively identify as scratch.
- The frontend build fails the container image on a type error.

---

## Recommended order

1. One ownership helper for invoices, applied to every payment path.
2. One settlement function: `Decimal`, strictly positive, no more than the
   balance or explicitly banked as a credit, row lock, idempotency on provider
   reference.
3. Fail-closed webhook configuration, and removal of the C2B attribution
   fallback in production.
4. Repair CI so subsequent fixes are provable.
5. Tenant portal: real tenant authentication, or removal of the route.
6. Social router: owner authorization and signature enforcement, or removal.
7. Audit logging, ledger reconciliation reporting, a shared rate-limit store,
   TLS, refresh-token rotation, upload limits, and a backup and restore runbook.

Each step should land with a test that fails against the behaviour described
here.
