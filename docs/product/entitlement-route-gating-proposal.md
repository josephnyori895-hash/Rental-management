# Rental OS entitlement and route-gating proposal

Status: proposal for product review. This matrix is not yet enforced in backend routes.

## Product rule

The Basic package must remain a useful, complete rental-operations product. Optional add-ons extend capability; they must not make ordinary rent collection, tenant records, property/unit management, maintenance, or the landlord's ability to receive their own money dependent on an upgrade.

Security controls, tenant isolation, auditability, backups, data export, and legally required privacy controls are platform-wide obligations, not paid add-ons.

## Proposed package boundary

### Basic package — core rental operations

- Properties, buildings, units and occupancy.
- Tenants, leases, move-in/move-out and deposits.
- Rent schedules, rent invoices, tenant payment records and receipts.
- Landlord-configured payment rails and direct settlement to the landlord's own provider account.
- Basic receivables, rent roll and standard operational dashboard.
- Maintenance requests and work tracking.
- Expense recording and basic operating reports.
- Tenant portal for each landlord's own tenants.
- Essential notifications and payment status.

### Optional add-ons — proposed keys

| Add-on | Entitlement keys | Candidate route groups |
|---|---|---|
| Advanced finance | advanced_accounting, books_of_accounts | /accounts/*, /reports/books/*, advanced exports |
| Utility management | utility_billing, meter_readings | /billing/utilities/* |
| Business intelligence | advanced_analytics | /analytics/insights and future forecasting |
| Communications automation | automated_reminders, bulk_communications, whatsapp_channel | reminder scheduling and bulk notification workflows |
| Document vault | document_management, document_storage_limit | /documents/* and storage quotas |
| Team operations | staff_seats, role_based_access | staff provisioning and advanced staff permissions |
| Integrations | api_access, webhook_integrations | future public API and outbound webhook routes |

These are candidate commercial boundaries, not a claim that all route groups are currently optional. Some may be included in Basic or bundled together after pricing and competitor review.

## Enforcement requirements

1. Keep feature checks on the backend route that performs the protected operation. Hiding a frontend button is not authorization.
2. Use explicit numeric limit enforcement for values such as staff_seats and document_storage_limit; a boolean require_feature check is insufficient.
3. Resolve the business from the authenticated user on every request. Never accept a client-supplied business ID as entitlement scope.
4. Do not gate landlord rent payment recording, provider credentials, settlement reconciliation, or access to historical rent receipts behind add-ons.
5. Preserve access to existing data after downgrade. Block new use/creation above downgraded limits without deleting historical records.
6. Add-on removal and plan downgrade must be effective-dated and must not rewrite past invoices or snapshots.
7. Record entitlement decisions and admin overrides for support and audit.

## Legacy-account rollout — required before enabling guards

The current product has a legacy Business.subscription_tier value and a trial date, but no historical catalogue selection or price snapshot. Applying the current require_feature helper immediately would treat legacy accounts with no new subscription row as having no paid features.

Therefore:
- Do not attach new route guards until the Basic/add-on matrix is approved.
- Create an explicit, reviewed mapping from each legacy tier and active trial to equivalent entitlements.
- Backfill or create grandfathered subscription snapshots with a documented effective date; do not invent historical prices or rewrite rent invoices.
- Run a report-only entitlement audit first, showing which current businesses would lose access.
- Enable route enforcement only after the owner approves the mapping and regression tests prove core workflows remain available.

## Acceptance tests before enforcement

- Basic account can create a property/unit, tenant/lease, rent invoice, record a rent payment and view the receipt.
- Basic account can manage maintenance and ordinary expenses.
- A business without an add-on receives 403 with stable FEATURE_NOT_INCLUDED details on the exact optional endpoint.
- Purchasing an add-on activates only its documented keys after verified Rental OS subscription payment.
- Downgrading does not delete data or alter landlord payment history.
- Business A cannot use Business B's entitlement or reach its records.
- Staff-seat and storage limits are checked atomically under concurrent requests.