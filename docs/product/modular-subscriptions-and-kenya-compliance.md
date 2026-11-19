# Rental OS modular subscriptions and Kenya operating boundaries

**Status:** Design baseline for implementation and Kenyan legal review  
**Repository baseline:** `main` at `138b12b52f970df4da59a43b01973a2b417f7c87`  
**Scope:** Product, subscription billing, payment separation, and compliance. This document does not authorize production deployment or legal practice as an estate agent.

## 1. Decisions to preserve

1. Rental OS sells property-management software and related technology services. Public marketing promotes Rental OS, its capabilities, support and subscription packages—not individual properties, vacancies or tenant opportunities.
2. Landlords/owners retain their rental income. A tenant's rent, deposit or property charge must settle to the relevant landlord's own verified provider account and destination.
3. Rental OS earns revenue from its own subscriptions and only other explicitly agreed, disclosed platform charges.
4. Rental OS must not receive, pool, hold, redirect, net off or disburse landlord rental funds.
5. Landlord payment credentials, webhook secrets, payment references, settlement destinations and rental transactions are isolated by landlord/business.
6. Rental OS subscription checkout uses a separate provider account, webhook configuration, ledger, invoice series and payment records. It must never reuse the landlord rent-collection flow or the tenant `Payment` / `Invoice` tables.
7. New work extends the existing application. Existing rent billing, payments, accounting, properties, tenants, leases, reports and authentication must not be replaced or silently removed.

## 2. Current-code observations

The reviewed `main` baseline already has:
- A `Business.subscription_tier` string with legacy BASIC/PRO/ENTERPRISE values and `trial_ends_at`.
- Landlord/tenant billing models `Invoice`, `Payment` and `DepositRefund`.
- Rent billing and utility billing routers.
- A tenant/business ownership model and owner-only dashboard route mounting.
- Business-level M-Pesa credential columns on `Business`.

The baseline does **not** yet provide a configurable subscription catalogue, selectable add-ons, a pricing-rule engine, platform subscription invoices/payments, subscription lifecycle management, or server-enforced feature entitlements. The legacy `subscription_tier` field must remain compatible during migration; do not repurpose it as the complete subscription system.

The payment implementation also has material gaps against the agreed owner-controlled model:
- The `Business` model exposes M-Pesa credential columns as ordinary SQLAlchemy `Text` / `String` fields. The reviewed model path does not apply an encrypted type or encryption/decryption service; the comment saying "encrypted at rest" is not proof of encryption.
- The current M-Pesa STK service reads process-wide `settings.MPESA_*` credentials and shortcode, rather than resolving the authenticated business's own provider configuration. Business-level credential columns therefore do not, by themselves, establish per-landlord credential isolation.
- The existing landlord payment service and callbacks must be hardened and verified independently before any tenant-facing live payment activation. Subscription billing must be a separate new domain, not an extension of these tenant payment routes.

## 3. Product and package model

### 3.1 Landlord-facing purchase experience

Every new subscription starts with one mandatory **Basic** foundation. The landlord then selects optional capabilities. The quote must update immediately and show:
- Basic recurring price.
- Every selected add-on and its price.
- Billable unit count and unit-price calculation, where applicable.
- Usage charges, if enabled.
- Discounts and their expiry/eligibility.
- Applicable tax treatment and tax amount.
- Billing frequency, next billing date and total payable now.
- What is included, excluded, limited or dependent on another add-on.

No paid option is preselected unless it is explicitly part of Basic. No add-on may be activated or charged without an affirmative selection and confirmation. The landlord must receive a durable copy of the order and subscription terms.

### 3.2 Catalogue is admin-configurable

Platform administrators should be able to configure, without a code deployment:
- Basic package name, description, included capabilities, limits and price.
- Add-on name, description, category, feature key, availability and dependencies.
- Pricing method, currency, amount, billing interval and effective date.
- Unit allowances, minimum charges, tier brackets and usage allowances.
- Promotional discounts, trial eligibility and annual billing discounts.
- Whether an item is available to new subscribers, existing subscribers or both.

Use typed pricing strategies, not arbitrary expressions, SQL, Python, JavaScript or `eval` supplied by an administrator.

### 3.3 Supported pricing methods

Implement pricing as explicit, versioned strategies:
- `flat_recurring`: fixed amount per billing interval.
- `per_billable_unit`: rate multiplied by the measured billable unit count, with optional included units and minimum charge.
- `tiered_units`: configured brackets with deterministic marginal or whole-tier pricing; the chosen interpretation must be visible in the catalogue.
- `usage_metered`: measured usage multiplied by a configured rate, with optional included allowance and cap.
- `one_time`: explicitly disclosed one-off charge, not silently recurring.

Use Decimal arithmetic and KES as the initial currency. Reject negative, non-finite, unsupported or ambiguous pricing inputs. Never calculate money with binary floating-point.

Define billable units as active, non-archived rental units belonging to the subscribing business, including both occupied and available units; exclude soft-deleted/archived units. Display the count and rule before checkout. This definition is a proposed default and must be configurable only through an explicit product decision, not inferred differently by different endpoints.

### 3.4 Pricing equation

`Recurring subtotal = Basic recurring fee + selected recurring add-ons + unit charges + metered usage`

`Amount due = recurring subtotal + one-time charges + applicable taxes - valid discounts/credits`

The server is the source of truth. The browser may preview a quote, but checkout must recalculate it from persisted catalogue versions and current business entitlements.

### 3.5 Price changes and subscription lifecycle

- Catalogue price changes apply prospectively on a disclosed effective date.
- Existing subscriptions retain their agreed price until the disclosed renewal/change rule applies; do not silently reprice an active term.
- Save immutable price/configuration snapshots on every subscription item and invoice line.
- Support trialing, active, past-due, grace-period, suspended, cancelled and expired states.
- Support monthly and annual terms, renewals, failed-payment retries, receipts, credit notes, refunds, upgrades and downgrades.
- Make upgrade proration policy explicit before enabling it. Initial release may apply upgrades immediately with a clearly shown prorated amount, and downgrades at the next renewal.
- Provide notices before renewal, failed-payment consequences, grace-period end and feature suspension.
- Never delete landlord data because a subscription expires. Preserve read-only access/export and a clear reactivation path.
- Cancellation must stop future renewals and preserve access through the paid-through date unless the customer explicitly requests otherwise and law permits.

## 4. Recommended data model

Implement additively, in a new subscription domain. Exact table names may follow repository conventions, but the boundaries must remain:

- `subscription_catalog_items`: Basic package and add-on definitions, descriptions, status, feature key, dependencies and display order.
- `subscription_price_versions`: immutable, effective-dated price rules (currency, interval, strategy, validated configuration, tax category).
- `business_subscriptions`: business, status, trial dates, current term, renewal/cancellation dates and catalogue version references.
- `business_subscription_items`: selected package/add-ons, quantity, feature key and immutable price/configuration snapshot.
- `subscription_usage_records`: idempotent usage measurements by business, feature and period.
- `subscription_invoices` and `subscription_invoice_lines`: platform receivables, totals, tax and immutable calculation snapshots.
- `subscription_payments`: payments to Rental OS only, with provider, provider account, verified reference, status and idempotency key.
- `subscription_events`: auditable lifecycle, selection, price, payment and entitlement changes.

All business-owned subscription rows must be scoped to the authenticated business. Catalogue administration must be restricted to platform administrators, not ordinary landlord owners.

Do not store subscription charges in the existing landlord `invoices` or `payments` tables. Do not store landlord rent receipts in the platform subscription tables. Give both flows distinct webhook routes/secrets, provider account configuration, reconciliation and ledger accounts.

## 5. Entitlements and feature enforcement

The selected subscription must produce a server-side entitlement set. API authorization must enforce entitlements on every protected capability; hiding a navigation item in React is not security.

- Basic capabilities are always available while the subscription is entitled to Basic.
- Add-on capabilities are available only when the subscription item is active and paid/within its allowed grace period.
- Enforce limits on the server (units, users, properties, messages, storage, reports, integrations).
- Check dependencies and prevent invalid combinations at selection and at quote/checkout time.
- Record entitlement changes and the reason/source.
- When a feature is removed, retain its underlying data. Block new use where appropriate, but preserve records and export.
- Existing users and businesses must receive a safe compatibility mapping from legacy `subscription_tier`; do not abruptly lock existing functionality during migration.

## 6. Payment separation — non-negotiable

### Landlord rental collection
- Each business configures its own provider credentials and settlement destination.
- Credentials are encrypted at rest, masked in responses, never logged, and only readable by the integration service that needs them.
- A provider integration is not marked active until ownership/configuration and callback verification are tested.
- Every callback is authenticated using that landlord's expected provider configuration and tied to that landlord's merchant/account identity, transaction reference and invoice/business.
- Provider reference idempotency must prevent duplicate credits; concurrency controls must protect invoice balances.
- The integration must use the provider's direct-to-landlord settlement capability. A successful API response alone is not proof of settlement.
- Rental OS records and reconciles the provider transaction but does not custody or redirect the rent.

### Rental OS subscription collection
- Uses Rental OS's own merchant/payment-provider account.
- Has a distinct callback endpoint and secret, transaction namespace, invoice series, reconciliation and ledger.
- Only subscription checkout, renewal and explicitly agreed Rental OS fees use this flow.
- A subscription payment must never update a tenant rent invoice or landlord ledger.
- A landlord rent callback must never mark a Rental OS subscription paid.

Before production, obtain a Kenyan payments-law opinion on whether the precise software, callback and payment-instruction role is outside payment-service-provider authorisation. Do not assume that direct settlement or API-key ownership alone resolves the National Payment System Act analysis.

## 7. Kenya legal and regulatory operating boundary

This is a product-risk baseline, not a legal opinion. Obtain written advice from a Kenyan advocate and, where appropriate, written regulator clarification before launching regulated activities.

### 7.1 Estate agency — Estate Agents Act, Cap. 533

The Act's definition of practising as an estate agent covers specified acts connected with selling, mortgaging, charging, letting or managing immovable property, including bringing prospective parties together or negotiating terms as an intermediary. Section 18 restricts practising as an estate agent to registered persons and imposes requirements on partnerships and bodies corporate.

The product should therefore remain a technology platform:
- Market Rental OS software, workflow automation, reporting, integrations, training and support.
- Let landlords control their own property decisions, tenant selection, lease terms, notices and agent appointments.
- Do not operate a rental marketplace or publish vacancy/property listings as Rental OS marketing.
- Do not match tenants to properties, solicit prospective tenants for landlords, negotiate leases, collect letting commissions or hold ourselves out as the landlord's letting agent.
- Do not make Rental OS staff perform regulated letting/agency functions on a landlord's behalf.
- Keep software features as tools for landlord-authorised users, with clear responsibility and audit trails.

The boundary around ongoing property-management services is fact-sensitive. EARB's public description is broader than the Act's specific statutory definition. Obtain a written EARB/advocate view on whether any planned operational service, not merely software, constitutes estate agency or property management requiring registration. Do not assume a "software" label alone is decisive.

### 7.2 Data protection — Data Protection Act, 2019 and 2021 Regulations

Rental OS processes tenant and landlord personal data. It will commonly act as:
- a processor for personal data a landlord uploads and uses in the platform on the landlord's instructions; and
- a controller for its own subscriber accounts, billing, support, security, website and marketing data.

ODPC FAQ identifies property management as a non-exempt mandatory-registration category regardless of turnover and headcount, and says entities acting as both controller and processor submit separate applications. Since Rental OS processes personal data in support of property-management activity, take the conservative position that controller and processor registration must be assessed and likely completed before live tenant-data processing. Seek written ODPC confirmation of the precise SaaS-only classification rather than assuming a small-business exemption applies.

Required product work:
- Data-processing agreement with each landlord/business.
- Clear privacy notices allocating landlord and Rental OS responsibilities.
- Documented lawful bases, purpose limitation, minimisation and retention schedules.
- Tenant rights workflows for access, correction, objection, deletion where applicable and complaints.
- Role-based access, tenant/business isolation, encryption, secrets management and audit logs.
- Subprocessor register and contractual safeguards for hosting, email, SMS, WhatsApp and payment providers.
- Cross-border transfer assessment and safeguards where data is hosted or accessed outside Kenya.
- Incident response, breach assessment and statutory notification workflow.
- DPIA screening before high-risk processing (identity documents, biometrics, CCTV integrations, extensive monitoring or automated decisions).
- No use of tenant data for Rental OS advertising or unrelated model training without a lawful basis and proper disclosures.

### 7.3 Payments — National Payment System Act and CBK rules

The Act requires authorisation to conduct the business of a payment service provider. Keep Rental OS out of custody, pooling, onward transfer and settlement of landlord funds. Use each landlord's own provider/merchant configuration and direct settlement. Use a separate authorised provider arrangement for Rental OS subscription payments. Have counsel assess the actual transaction and callback flow and obtain CBK guidance if the role is uncertain.

### 7.4 Consumer and competition rules

The Consumer Protection Act and Competition Act require careful, non-misleading representations and transparent online contracting/pricing. Therefore:
- Show every recurring fee, add-on, usage charge, tax, renewal date and cancellation term before consent.
- No pre-ticked paid add-ons or hidden recurring charges.
- Record affirmative acceptance and preserve the version of terms accepted.
- Provide a durable order confirmation, invoice and accessible cancellation process.
- Clearly disclose trial conversion, annual discounts, price changes, grace periods and consequences of non-payment.
- Do not claim "free", "unlimited", "guaranteed savings" or competitor superiority unless the claim is accurate and substantiated.
- Provide a complaint/contact route and refund/credit policy.

### 7.5 Tax and invoicing — KRA

KRA states that taxable supplies of KES 5 million or more annually trigger VAT registration (subject to the precise VAT rules and exemptions) and that VAT-registered persons must onboard eTIMS. KRA also says persons engaged in business are generally required to onboard eTIMS and issue electronic tax invoices. Confirm the treatment of Rental OS SaaS subscriptions, add-ons, discounts, refunds and any cross-border supplies with a Kenyan tax adviser. Do not hard-code the current VAT rate as an immutable constant; maintain effective-dated tax configuration and issue compliant invoices/credit notes.

## 8. Marketing policy — services only

Allowed public marketing:
- Rental OS product, dashboard demonstrations and screenshots using synthetic data.
- Property/unit/tenant management capabilities as software features.
- Automated invoicing, landlord-owned payment integration, reconciliation, accounting, reporting, maintenance, document and tenant portal capabilities.
- Subscription packages, transparent pricing, support, training and product updates.
- Case studies only with documented consent and anonymisation where required.

Out of scope until separately approved and legally reviewed:
- Individual property advertisements, vacancies, rental prices, landlord contact details or tenant leads.
- Public property marketplace, property search or tenant-to-landlord matching.
- Social media posts that advertise a landlord's available units.
- Bot responses that expose global vacancy lists, rents, addresses or another business's records.
- Negotiation, viewing arrangements or lease brokerage by Rental OS.

Facebook/Instagram integrations must be used to promote Rental OS services and respond to Rental OS product enquiries only. Disable or remove vacancy queries and any hard-coded sample rental listings before enabling the social bot in production.

## 9. Delivery sequence and acceptance gates

1. **Stabilise baseline:** review and resolve the open CI, payment-security and portal/social branches independently; do not merge a branch with known payment or data-isolation gaps.
2. **Catalogue and quote engine:** build admin-managed Basic/add-on catalogue, typed pricing strategies, quote preview and deterministic server-side calculation. Unit and usage measurement must be testable.
3. **Subscription persistence:** add subscription, item, usage, invoice, line, payment and event tables via additive Alembic migrations. Preserve all existing tenant invoices/payments and legacy subscription fields.
4. **Checkout and lifecycle:** integrate a separate Rental OS subscription merchant account, verified callbacks, idempotency, renewals, reminders, cancellation and refunds.
5. **Entitlements:** enforce features and limits server-side, with backward-compatible migration for existing businesses.
6. **Landlord payment hardening:** finish provider-specific direct-settlement verification, credential encryption/isolation, callback verification, duplicate and concurrency controls.
7. **Marketing and compliance:** disable rental-listing social/public endpoints, add legal pages and subscription disclosures, complete ODPC/EA​​RB/CBK/legal/tax review.
8. **Release gates:** tests for pricing boundaries, tier brackets, tax rounding, stale quotes, duplicate callbacks, cross-business access, lifecycle transitions, data retention, and separation between platform and landlord ledgers; hosted CI green; independent code review; staging verification. Production deployment/migration requires separate explicit approval.

## 10. Required test cases for the subscription engine

- Basic only; Basic plus one add-on; multiple add-ons; no duplicate add-on selection.
- Flat, per-unit, tiered and metered calculations at boundary values.
- Deleted/archived units excluded; occupied and available units counted consistently.
- Invalid/negative/non-finite prices rejected.
- Decimal rounding and tax calculation deterministic.
- Catalogue price changes do not mutate historical invoice lines.
- Client-supplied price/discount/total is ignored; server recalculates.
- Business A cannot read/change Business B subscription, quote, usage, invoice, payment or credentials.
- Landlord rent payments cannot settle platform invoices and platform subscription payments cannot alter rent balances.
- Duplicate subscription callback is idempotent.
- Failed renewal, grace period, suspension, cancellation, upgrade and downgrade transitions.
- Feature access enforced by backend, not merely hidden in frontend.
- Expired subscription does not delete property, tenant, lease, invoice or payment records.
- Existing BASIC/PRO/ENTERPRISE businesses retain current access until explicitly migrated.

## 11. Primary official sources

- Estate Agents Act, Cap. 533: https://new.kenyalaw.org/akn/ke/act/1984/17/eng@2022-12-31/source.pdf
- Estate Agents Registration Board: https://estateagentsboard.or.ke/
- Data Protection Act and subsidiary regulations: https://www.odpc.go.ke/data-protection-laws-kenya/index.html
- ODPC registration FAQ (including property management and dual controller/processor registration): https://www.odpc.go.ke/faqs/
- National Payment System Act, Cap. 491A: https://new.kenyalaw.org/akn/ke/act/2011/39/eng@2023-09-15/source.pdf
- KRA VAT guidance: https://www.kra.go.ke/individual/filing-paying/types-of-taxes/value-added-tax
- KRA eTIMS guidance: https://www.kra.go.ke/business/etims-electronic-tax-invoice-management-system/learn-about-etims

**No production deployment, database migration, live payment configuration or production data change is authorised by this design document.**
