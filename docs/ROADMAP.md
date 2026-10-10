# rental-os — Competitive Roadmap

> **Strategy in one line:** be the only platform that runs **both the rent roll *and* the estate agency**
> on one accounting-grade ledger, with **WhatsApp as the primary operating interface**.

Last reviewed: September 2026. Competitor pricing/features taken from their public pages
(see [Sources](#sources)) — treat as *claimed*, not verified hands-on.

---

## 1. Why this strategy

Two facts about the Kenyan market emerged from the competitive scan:

1. **Everyone is rental-only.** Nyumba Zetu, PMS.co.ke, Rent Manager Kenya, Rent Rahisi, Mkodisha,
   Keja AI, Siteti, Milik — none does property **sales/agency** (listings → viewings → offers →
   mandates → commissions). That is an open field.
2. **Nobody has a real ledger.** Competitors produce rent rolls and cash-basis statements.
   rental-os already ships genuine double-entry books (trial balance, P&L, balance sheet, journal).
   An agency structurally *needs* that ledger — competitors would have to build one first.

That combination (**accounting-grade + WhatsApp-native + caretaker workflows + agency pipeline**)
is defensible because it is not a feature gap competitors can close in a sprint.

### What we already have (verified in-repo, 70 paths / 78 operations)

| Strength | Where |
|---|---|
| Double-entry accounting | `app/accounting/` — `/accounts/trial-balance`, `profit-loss`, `balance-sheet`, `journal` |
| M-Pesa STK push + secured Daraja callback | `app/payments/router.py` (+ token verify, rate limits) |
| WhatsApp **command** bot (tenant + owner + caretaker) | `app/notifications/inbound*.py` |
| Caretaker role & caretaker WhatsApp onboarding | `app/notifications/inbound_user.py` |
| KRA eTIMS export | `app/reports/exports.py` → `/reports/export-etims` |
| Owner statement PDF + monthly dispatch | `app/reports/` |
| Aged receivables (30/60/90) + rent roll | `app/reports/receivables.py` |
| Utility & service-charge billing (tariffs, meter readings, bulk apportionment) | `app/billing/utilities*.py` |
| Payment reconciliation engine | `app/reconciliation/` |
| Documents, expenses, maintenance, leases | `app/documents/`, `app/expenses/`, `app/maintenance/`, `app/tenants/` |
| Multi-business scoping (`business_id` on 69 call sites / 15 routers) | throughout |

**Do not lose these.** They are the moat. Everything below either protects them or extends them.

---

## 2. Phase 0 — Clean the runway *(in flight)*

Nothing here is glamorous; all of it is debt that will slow every later phase.

- [x] Dependency manifests (`requirements.txt`, `requirements-dev.txt`)
- [x] `.env.example` covering every live setting
- [x] README with real setup/ports/known-gaps
- [x] DB-free suite — 132 tests in `backend/tests/`
- [x] Security pass: M-Pesa callback token verification, JWT key fix, rate-limit wiring
- [x] Module split: `notifications/inbound.py` → `inbound.py` + `inbound_tenant.py` + `inbound_user.py`
- [x] Module split: `reports/router.py` → `router.py` + `statement.py` + `books.py` + `exports.py`
- [x] Module split: `notifications/service.py` → `service.py` + `templates.py`
- [ ] Split frontend monster components (`OwnerBoard.tsx` 692, `BuildingCanvas.tsx` 670, `BooksPage.tsx` 637)
      — *blocked until `npm ci` runs; frontend cannot be typechecked today*
- [ ] **Model/migration drift:** `MeterReading`/`UtilityRate` exposed it for the first time —
      `TimestampMixin.created_at` is declared `index=True`, but **no migration in this repo ever
      created those indexes**. Either add them for every table or drop `index=True`; right now the
      models and the live database disagree. `tests/test_utilities.py` pins the current shape so
      the drift cannot grow silently.
- [x] **Postgres-backed tenant isolation tests** — 24 tests in
      `tests/test_tenant_isolation.py` against a scratch database, covering 15 list endpoints
      (leak-checked *and* proven non-vacuous), by-id cross-tenant reads (404), cross-tenant writes
      (404), scalar dashboards/reports, and the token-decides-the-business rule. Each test rolls
      back its own transaction, so the scratch database is left clean.
- [x] `POST /billing/bills` deprecated in favour of `POST /billing/utilities/readings`
      (OpenAPI `deprecated`, `Deprecation` + `Link: rel="successor-version"` headers, behaviour
      unchanged); `/billing/invoices` now returns a real `total` instead of the page size
- [ ] Dead duplicate account model — `app/models/accounting.py::Account` (table `accounts`, 0 rows
      in the live database, created by no migration) and its unused `SYSTEM_ACCOUNTS`. The live
      ledger is `app/accounting/models.py::ChartOfAccount`.
- [x] **Ledger posting audit** — the utility defect was one instance of a pattern, so all three
      posting hooks were audited for the same failure (an unresolvable account returning without a
      sound, inside a caller that swallows the exception). Fixed in `auto_post_payment` and
      `auto_post_expense`; all four `except Exception: pass` blocks wrapping a posting now log with
      `exc_info=True`. `EXPENSE_ACCOUNT_CODES` is a second, *indirect* account table that the
      literal-only source scan could not see, so it is now guarded separately — as is the unguarded
      default that used to be an inline `"5090"`. A duplicated `"total_income"` dict key in
      `profit_and_loss` (a silent overwrite) was removed. Tests in `tests/test_ledger_silent_drops.py`,
      including an `ast` guard that fails if any posting call is wrapped in a bare `pass` — all three
      guards mutation-checked by reintroducing the silencer.
- [x] **Deposit policy decided and the invoice leg implemented.** A deposit is a liability, never
      income. `app/accounting/service.py::credit_account_code` is now the single place that decides
      which account an invoice credits, and it routes `InvoiceType.DEPOSIT` to
      `2100 Security Deposits Payable` whatever `income_code` says. Matching is case-insensitive and
      trimmed, because `bill_type` reaches it as **unvalidated free text** from the deprecated
      `POST /billing/bills` — `bill_type="deposit"` used to book a liability as *rental income*.
      Because `app/tenants/router.py` already assembled a `deposit` object from a deposit invoice and
      a `DepositRefund` that nothing ever created, the UI showed an unpaid deposit that was never
      billed; it now reports the real balance.
      The three legs, in full:
      `invoice raised` Dr 1100 / Cr 2100 · `deposit paid` Dr 1000 / Cr 1100 (already worked —
      `auto_post_payment` is invoice-agnostic) · `deposit refunded` Dr 2100 / Cr 1000.
      Tests in `tests/test_deposits.py`; the rent regression is asserted alongside the deposit rule,
      and the end-to-end test proves the ledger is never touched on `4000`.
- [ ] **Deposit refunds have no write path.** The refund leg (Dr 2100 / Cr 1000) is specified above
      but cannot be wired yet: `DepositRefund` is only ever *read* (`app/tenants/router.py:151`), so
      nothing creates one. `tests/test_deposits.py::test_the_refund_leg_is_still_unbuilt` fails the
      moment a `DepositRefund` is created, to force its posting to land in the same change — a
      refund that moves cash without clearing the liability is worse than no refund flow at all.
- [x] **`bill_type` validated on `POST /billing/bills`.** It was free text stored verbatim as
      `invoice_type`, so a typo invented a new invoice type and `bill_type="water"` posted to
      `4000 Rental Income` while the replacement endpoint posted to `4030` — same word, two accounts.
      It now accepts exactly the `UtilityType` values (case and whitespace normalised, anything else
      422s) and derives its income account from the bill type, so both endpoints agree. Deposits are
      refused here: they are raised by tenant enrollment, which is where they post correctly.
      Safe to tighten because the frontend's `createBill` has no callers.
- [x] **Enrollment now posts its invoices — the largest ledger hole found.** `enroll_tenant` is the
      only path that raises a rent invoice or a deposit invoice, and it raised both, flushed,
      committed, and called no posting hook at all. Every tenancy therefore started with invoices
      the ledger had never heard of: the rent roll and the balance sheet disagreed from day one, for
      every tenant, with nothing anywhere reporting it. Both now post — rent to `4000`, deposit to
      `2100` — inside a logged best-effort guard. `tests/test_enrollment_ledger.py` drives the real
      `POST /tenants/enroll` endpoint rather than inserting invoices, because the defect was in the
      endpoint's posting: inserting an invoice would have passed with the bug present.
- [ ] **There is no recurring rent-invoice generator.** Rent is invoiced once at enrollment and never
      again, so arrears, the aged-receivables buckets and the rent roll all only ever see each
      tenancy's first month. The reports are correct about the data they have; the data is the gap.
      This is the highest-value missing piece for daily use.
- [ ] CI workflow (lint + tests on push) — must run a PostgreSQL service container, or the 26
      isolation tests silently skip and the workflow proves less than it appears to

**Exit criteria:** green CI, ~~Postgres-backed isolation tests~~ ✅, no file over ~450 lines.

---

## 3. Phase 1 — Close table-stakes gaps

Ordered by *competitive impact ÷ effort*. Each item names where it lands.

### 1.1 CRB tenant screening — **highest-impact open goal** `M`
No Kenyan PMS we found offers it. Every global tool does.
- Verify API access with a Kenyan CRB (Metropol, TransUnion Kenya, Creditinfo) — **do this first**;
  it gates the whole item.
- New module `app/screening/` with a provider abstraction (mirror the existing
  `notifications/providers/` pattern — base + concrete providers).
- Endpoint `POST /api/v1/tenants/{tenant_id}/screen`; store report + **explicit consent record**.
- Surface on the enrol flow and OwnerBoard.
- ⚠️ Handle Kenya Data Protection Act 2019 obligations (consent, retention, lawful basis).

### 1.2 Utilities & service-charge billing — ✅ **DONE**
The WhatsApp bot used to reply *"Meter reading logged. (Full integration in v2)"*. That stub is
gone; the caretaker's reading now prices and invoices for real.
- ✅ `app/models/utilities.py` — `UtilityRate` (tariff + split rule, property-wide or per unit) and
  `MeterReading` (unit meter, or `unit_id IS NULL` for a property bulk meter).
- ✅ `POST /billing/utilities/readings` — record a reading; consumed = current − previous, priced
  against the applicable tariff, and invoiced when the unit is occupied.
- ✅ `POST /billing/utilities/bill-shared` — apportion one shared cost across occupied units by
  `equal` / `occupancy` / `rent` / `metered`. A `metered` split **refuses** rather than billing an
  unmetered unit zero.
- ✅ `POST|GET /billing/utilities/rates` — tariff CRUD; a unit-specific rate beats the property default.
- ✅ WhatsApp: `<reading>`, `WATER <unit> <reading>`, `METER A1 348`. A first reading is stored as a
  baseline; a lower reading is rejected instead of silently zeroing consumption.
- ✅ Utility invoices post to their **own revenue account** — `4030 Water Bill Income`,
  `4040 Electricity Income`, `4010 Service Charge Income`, `4050 Other Income` for everything else
  (`auto_post_invoice` now takes an `income_code`, resolved by
  `app.billing.utilities.income_code_for`).
- 🐛 **Fixed:** the first cut of this feature posted to **4200 Utility Reimbursement** — a code that
  only ever existed on a dead duplicate `Account` model and that no business has. `DEFAULT_COA`
  never creates it, so `get_account_id_by_code` returned `None` and `auto_post_invoice` returned
  **silently**: invoices were raised, tenants were billed, and the ledger received no entry at all.
  Two things now stand in the way of a repeat — a test that scans the source for every literal
  account-code lookup and asserts `DEFAULT_COA` provisions it (mutation-checked by reintroducing
  `4200` and confirming it fails), and a database-backed test that follows a real reading into
  `journal_entries` and asserts which account was credited. `auto_post_invoice` also logs a warning
  instead of returning quietly when an account cannot be resolved.
- ✅ Money is `Decimal` and apportionment is remainder-exact, so the per-unit shares always sum to
  the total — verified by test, not by inspection.
- ⚠️ The web endpoints do **not** message tenants (a 40-unit shared bill would fire 40 messages);
  only the WhatsApp flow notifies. Trigger reminders from `app/notifications` when wanted.
- ⚠️ Tariffs have no effective dating — changing a rate does not affect readings already billed.

### 1.3 Owner & tenant portal — **diaspora is the paying segment** `M`
Only `/portal/my-data` exists today; Nyumba Zetu and PMS.co.ke both ship full portals.
- Owner portal: statements, occupancy, arrears, documents, downloadable PDFs.
- Tenant portal: balance, pay, receipts, raise repair with photo, lease view.
- Ship as a **PWA** first — mobile-first market, and it reuses the existing React app.

### 1.4 Digital lease e-signature with audit trail `S–M`
`POST /tenants/{id}/sign-lease` already exists. Make it defensible.
- Consent capture + timestamp + document hash + IP/UA → an auditable trail.

### 1.5 Aged receivables & rent roll as first-class reports `S` — ✅ **DONE**
We had owner-statement and collection-trend but not the two reports every competitor names.
- ✅ `GET /reports/aged-receivables` — buckets outstanding invoices into
  current / 1–30 / 31–60 / 61–90 / 90+ days, with per-invoice detail and a
  per-tenant rollup.
- ✅ `GET /reports/rent-roll` — one row per active lease with rent, deposit,
  payment day and arrears.
- Lives in `app/reports/receivables.py`; query builders are pure and
  DB-free-testable. Covered by 23 new tests in `tests/test_receivables.py`.

---

## 4. Phase 2 — Widen the moat

6. **Multi-bank reconciliation** — extend `app/reconciliation/` beyond M-Pesa to Equity, I&M, Co-op
   (Rent Rahisi already advertises these). `M`
7. **Vendor/contractor dispatch + SLA tracking** on maintenance tickets (PMS.co.ke has it). `M`
8. **Trust/escrow accounting** for agencies holding client money — a natural extension of the
   existing ledger, and a hard requirement for agencies. `L`
9. **Vacancy/listing management** — the bridge into Phase 3. `M`

---

## 5. Phase 3 — Real estate & agency *(the differentiator)*

This is the direction the product is meant to grow into. Nothing here has a Kenyan incumbent.

10. **Sales pipeline** — listings, leads, viewings, offers/counter-offers, mandate agreements. `L`
11. **Commission tracking + agent splits**, payable off the existing accounting ledger. `M`
12. **Kenya-specific calculators** — stamp duty, legal fees, service-charge apportionment,
    Sectional Properties compliance. `S–M` each
13. **Listing syndication** to BuyRentKenya / Property24 Kenya. `M`
14. **Valuation reports** — reuse `app/reports/pdf_service.py`, which already renders branded PDFs. `M`

**Sequencing note:** do 10 and 11 together — a pipeline without commission tracking doesn't
close an agency, and commissions are where the ledger advantage pays off visibly.

---

## 6. Recommended order (next 6 moves)

1. Finish **Phase 0**: stand up CI, **get Postgres up and write isolation tests**, split the frontend
   components, resolve the `created_at` model/migration drift.
2. **CRB screening** (1.1) — confirm vendor API access before writing code.
3. **PWA owner/tenant portal** (1.3) — diaspora is the paying segment, and it reuses the React app.
4. **Digital lease e-signature audit trail** (1.4) — small, and it hardens something already shipped.
5. Begin **Phase 3** (sales pipeline + commissions) — long lead time, start early.

~~Aged receivables + rent roll (1.5)~~ ✅ and ~~utilities billing (1.2)~~ ✅ are both done.

---

## 7. What we should *not* build

Good plans say no.

- ❌ **Our own payment rail.** M-Pesa + banks via existing APIs; never hold float ourselves.
- ❌ **US/enterprise features** — 1099s, HOA, MLS, trust-audit reports for US auditors.
  Wrong market, and Yardi/AppFolio win there regardless.
- ❌ **A native mobile app** before a PWA has proven the demand.
- ❌ **Our own OCR/AI document extraction** until the CRB and utilities work is done.

---

## 8. Metrics to actually track

| Metric | Why |
|---|---|
| Time-to-first-invoice for a new landlord | Onboarding friction is where trials die |
| On-time collection rate | The outcome customers pay for |
| % tenants acting via WhatsApp vs portal | Tells us whether the portal investment is working |
| Arrears aging (30/60/90+) | The report agencies open first |
| Units per business | Expansion revenue proxy |
| Callback/auth failures on M-Pesa | Silent revenue loss |

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| CRB API access unavailable/expensive | Confirm **before** building; keep provider abstraction so an alternative slots in |
| Competitor copies WhatsApp bot | Moat is the ledger + caretaker ops, not the chat surface — keep widening those |
| Postgres not running → isolation bugs ship | Phase 0 exit criterion is Postgres-backed tests |
| Data Protection Act exposure from screening | Consent records, retention limits, documented lawful basis |
| Scope creep into enterprise features | Section 7 is binding |

---

## Sources

Competitor information from their public marketing pages, September 2026:
`nyumbazetu.com`, `pms.co.ke`, `rentmanager.co.ke`, `milikproperty.com`, `rentrahisi.co.ke`,
plus the Saseni "Top 10 Property Management Systems in Kenya" list, and the
AppFolio / Buildium / MRI comparison pages for the global feature baseline.
