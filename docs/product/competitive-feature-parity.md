# Rental OS competitive feature parity baseline

**Status:** Research baseline; proposed roadmap, not a claim that features are implemented.  
**Compared:** Public product materials available on 20 November 2026. Vendor marketing pages are not independent product tests; verify capability, country availability, pricing and contractual limits before procurement decisions.

## 1. Strategic position

Rental OS should compete on the quality and depth of property-management operations, not by becoming a property marketplace or letting intermediary.

The product should market Rental OS software, onboarding, support and integrations. It must not market individual landlord properties, vacancies, public rents, tenant leads or property listings. Features that competitors use to generate tenant leads (listing syndication, public vacancy pages, listing marketplaces and lead routing) are intentionally outside this product's scope.

The differentiator should be a Kenya-first, landlord-controlled operating system:
- Each landlord owns and controls their provider credentials and settlement destination.
- Rent, deposits and property charges settle directly to that landlord's provider account.
- Rental OS subscription billing is a separate platform revenue stream.
- M-Pesa, Paybill/Till, bank imports, reconciliation, KES accounting and local tax workflows are first-class.
- Every property, unit, lease, tenant, expense, maintenance event, payment and report remains linked to a clear business/property record.
- Strong role isolation, auditability, data export and reliable mobile workflows are product features—not optional polish.

## 2. Competitor capability observations

| Capability area | Publicly documented competitor examples | Rental OS target |
|---|---|---|
| Portfolio and unit operations | Buildium describes residential, commercial, community association and student housing portfolios; DoorLoop describes portfolio, unit and operations management. | Multi-property, multi-building, mixed unit types, occupancy, unit history, ownership relationships, configurable property structures and bulk import. |
| Rent, invoices and collections | Buildium Resident Center offers payments, history, autopay and reminders; DoorLoop describes rent collection, reminders and late fees. Kenyan vendors advertise M-Pesa STK, Paybill/Till and automatic matching. | Monthly invoicing, recurring charges, partial payments, overpayments, receipts, arrears aging, payment plans, M-Pesa STK, landlord-owned Paybill/Till and bank/cash recording. |
| Reconciliation and accounting | Buildium promotes property accounting and automatic bank reconciliation; DoorLoop promotes bank sync, bookkeeping and property-level reporting. | Double-entry accounting, transaction matching, unmatched-payment queue, reconciliation controls, audit trail, per-property P&L, cash flow and exportable ledger. |
| Maintenance and vendors | Buildium documents resident requests, work orders, assigned staff/vendors, estimates, recurring work and bill creation. AppFolio documents work orders, inspections, unit turns, vendor coordination and audit history. | Tenant requests, triage, assignment, SLAs, quotes, approval limits, vendor records, work orders, photos, expenses, recurring maintenance and full resolution history. |
| Tenant self-service | Buildium Resident Center and DoorLoop Tenant Portal document payment history, maintenance requests, messages, documents and announcements. | Secure mobile-first tenant portal for balances, invoices, receipts, payment instructions, maintenance, notices, documents, lease details and move-out requests. |
| Owner reporting and access | Buildium Owner Portal documents financial reports, transactions, documents and tasks; DoorLoop Owner Portal documents real-time financials and property-specific reports. | Separate owner/client portal, property-scoped access, statements, expenses, arrears, maintenance, documents, approvals and read-only/auditable access. |
| Leasing and documents | Buildium and DoorLoop describe applications, screening, e-signatures and lease workflows. | Internal tenancy lifecycle: applications received directly by the landlord, landlord-controlled screening decisions, lease templates/e-signing, renewals, deposits, move-in/out inspections and document retention. No public property listings or lead marketplace. |
| Roles and accountability | AppFolio documents audit history and role-specific portals; Kenyan vendors describe caretaker-scoped access. | Least-privilege owner, manager, accountant, caretaker and vendor roles; property-level assignments; approval limits; immutable event history; session and access controls. |
| Analytics and automation | DoorLoop and AppFolio describe custom reporting, workflow automation and AI assistance; Buildium promotes analytics and open integrations. | Portfolio dashboard, occupancy and arrears analytics, forecast/cash flow, scheduled reports, configurable alerts, workflow automation and AI assistance with human approval and attributable actions. |
| Data onboarding and integrations | Buildium promotes open API/integrations; DoorLoop advertises spreadsheet migration and integration support. | Validated CSV/XLSX import, preview/dry-run, duplicate detection, rollback-safe import batches, documented API/webhooks and export at any time. |
| Mobile and communications | Buildium documents mobile Resident Center; DoorLoop and AppFolio describe mobile workflows; Kenyan services emphasize SMS and WhatsApp. | Responsive PWA/mobile experience, reliable low-bandwidth flows, SMS/WhatsApp/email delivery tracking, in-app notices and accessible offline-tolerant drafts. |
| Security and continuity | Vendor pages make claims about encryption, backups, roles and audit logs; these need independent verification. | Encryption at rest/in transit, per-business secret isolation, verified callbacks, tenant isolation tests, rate limits, backups/PITR, tested restore, monitoring, incident response and exportability. |

## 3. Kenya-first capabilities that should be treated as core

1. **M-Pesa and bank reconciliation:** STK Push, Paybill/Till, manual and bank payments, transaction matching, duplicate detection, unmatched collections and clear landlord settlement proof.
2. **Utilities and service charges:** configurable tariffs, meter readings, shared-utility allocation, recurring service charges, clear invoice lines and audit trails.
3. **KRA workflow support:** maintain tax identifiers and invoice data, support the applicable eTIMS integration path, and provide tax-ready exports. Do not hard-code tax rates or claim compliance without current tax review and a verified integration.
4. **KES-first finance:** decimal-safe calculations, double-entry ledgers, property-level and portfolio-level statements, arrears aging, cash-flow reports and exportable records.
5. **Communication reliability:** SMS/WhatsApp templates, message delivery status, reminders with deduplication, receipts that are not suppressed by a depleted marketing-message balance.
6. **Local operations:** caretaker access, multiple properties, bulk tenant/unit import, Swahili-ready labels, local date/time and phone normalization.

## 4. Subscription packaging implication

Competitor pricing models vary: fixed tiers, per-unit pricing, occupied-unit pricing, and usage/add-on charges are all visible in the market. Rental OS should not copy a competitor's price without testing unit economics.

Keep the agreed structure:
- Basic foundation package.
- Optional, separately priced add-ons.
- Admin-configurable catalogue and effective-dated price versions.
- Explicit included allowances and unit-count rules.
- Immediate quote breakdown and affirmative selection for every paid add-on.
- Backend-enforced entitlements and limits.
- Distinct Rental OS subscription invoices/payments, never mixed with landlord rent receipts.

Potential add-on families to evaluate: advanced accounting, bank reconciliation, owner portal, tenant portal enhancements, maintenance/vendor operations, utilities/metering, SMS/WhatsApp credits, advanced analytics, document/e-signature capacity, API/integrations, AI assistant and multi-branch/team controls. Each must map to a real feature flag, usage meter or service entitlement before it can be sold.

## 5. Delivery priorities

### P0 — trust and money correctness
- Fix and test cross-business payment isolation.
- Encrypt landlord provider credentials at rest and mask them in every response/log.
- Use the authenticated business's own provider account configuration; remove accidental reliance on global merchant credentials for landlord collections.
- Authenticate callbacks, bind each callback to the expected landlord/provider account, and enforce database-backed idempotency and concurrency controls.
- Separate landlord rent records from Rental OS subscription records.
- Add backups, restore tests, audit events and production monitoring.

### P1 — complete daily operating workflows
- Tenant/owner portals with strict property/business scoping.
- Maintenance-to-vendor-to-expense workflow.
- Reliable rent runs, arrears, receipts, reminders and reconciliation.
- Owner statements, property-level accounting and exports.
- Import/export and audit trails.

### P2 — scale and differentiation
- Configurable subscription catalogue and entitlement engine.
- Workflow automation, advanced analytics and approvals.
- AI assistance grounded in the tenant's authorized records, with explicit human approval for financial/legal actions.
- API, webhooks and integrations.
- Portfolio visualization and multi-building operational views.

### P3 — growth without becoming a marketplace
- Rental OS product marketing, demos, onboarding and customer support CRM.
- Service enquiry capture and customer education.
- Partner integrations and referral relationships that market the software service only.
- No vacancy listings, property lead-generation, public rent advertising or tenant matching.

## 6. Current-code caution

This document is a capability target, not a verification report. Existing modules must be audited and tested before marking any row complete. The current `main` branch has legacy business subscription tiers and landlord invoice/payment models, but does not yet have the agreed modular subscription catalogue, price versioning, subscription lifecycle or server-side entitlement system.

The inspected landlord payment path also needs hardening: the Business model exposes provider credential columns as plain text/string fields, and the current M-Pesa STK service reads process-wide settings rather than resolving the authenticated business's own credentials. Do not enable live landlord collections on the strength of column names or comments alone.

## 7. Research sources

Vendor feature claims are summarized, not reproduced. Product availability and plan inclusions differ by market and subscription tier.

- [Buildium — Features](https://www.buildium.com/features/)
- [Buildium — Resident Center](https://www.buildium.com/features/resident-center/)
- [Buildium — Property Owner Portal](https://www.buildium.com/features/property-owner-portal/)
- [Buildium — Maintenance](https://www.buildium.com/features/property-management-maintenance-software/)
- [DoorLoop — Features](https://www.doorloop.com/features)
- [DoorLoop — Tenant Portal](https://support.doorloop.com/en/articles/6337601-tenant-portal-overview)
- [DoorLoop — Owner Portal](https://support.doorloop.com/en/articles/8392701-introduction-to-the-owner-portal)
- [AppFolio — Property Management Software](https://www.appfolio.com/property-management-software)
- [AppFolio — Maintenance](https://www.appfolio.com/property-manager/maintenance)
- [Pangoni — Product overview](https://pangoni.io/about)
- [Nyumba Zetu — Kenya property management](https://www.nyumbazetu.com/)
- [PropMS — Kenya property management](https://propertyms.org/)
- [Rentetta — Kenya property management](https://rentetta.com/)
- [Safaricom — M-PESA Bill Manager for Rent Solution (PDF)](https://www.safaricom.co.ke/images/Downloads/m-pesa-bill-manager-for-rent-solution.pdf)

## 8. Acceptance rule

A feature is not "at parity" merely because a screen or button exists. It is complete only when:
- the workflow works end-to-end for the intended role;
- every read and write is tenant/business/property scoped;
- money, status and ledger effects are correct and idempotent;
- failure, retry, duplicate and concurrency paths are tested;
- mobile and desktop behavior is verified;
- the feature is documented and supportable; and
- no property listing or lead-generation behavior has been introduced contrary to Rental OS's services-only marketing rule.
