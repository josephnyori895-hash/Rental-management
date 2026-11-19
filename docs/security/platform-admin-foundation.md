# Platform administrator foundation

## Security boundary

Platform administrators are not landlord users and are not members of a landlord
business. They live in `platform_admins`, authenticate through
`/api/v1/platform-admin/auth/login`, and receive a distinct JWT principal type.
The dependency verifies both token type and principal type, then reloads the
administrator from the database and checks that the account remains active.
Disabling an account therefore takes effect without waiting for the JWT expiry.

Landlord tokens (including a landlord whose role is `owner`) are rejected by
platform-admin endpoints. A business user cannot grant themselves platform
privileges by changing a role claim or business record.

There is no public platform-admin registration endpoint. Bootstrap is a
controlled operator action after the migration:

```bash
cd backend
PLATFORM_ADMIN_EMAIL=admin@example.invalid \
PLATFORM_ADMIN_NAME="Rental OS Administrator" \
PLATFORM_ADMIN_PASSWORD='use-a-unique-password-of-at-least-14-characters' \
PYTHONPATH=. python scripts/create_platform_admin.py
```

The script refuses to overwrite an existing account. Supply the password
through a secret manager or protected one-time environment injection, never
commit it, and remove it from the environment after provisioning.

## Included in this foundation

- Separate platform administrator table and Alembic migration.
- Separate login and profile endpoints.
- Login rate limiting using the application's existing limiter.
- Live database lookup on each authenticated request, including active-state
  enforcement.
- Subscription catalogue administration now depends on this separate principal
  rather than the non-existent `platform_admin` landlord role.
- Focused tests for token/principal separation and inactive accounts.

## Additional subscription foundation

The subscription layer now records billing intervals, immutable line snapshots,
owner-issued Rental OS subscription invoices, business-scoped invoice reads,
and append-only lifecycle events. A verified-payment settlement service exists
for a future Rental OS provider webhook adapter; it is not exposed as a public
endpoint and no provider credentials or checkout integration are configured.
A successful verified settlement is designed to activate only the referenced
platform subscription invoice and subscription. It never updates landlord rent
invoices or landlord payment settings.

## Not yet production-ready

This is a foundation, not a complete admin console or full platform security
program. Before enabling platform administration in production, add and verify:

1. MFA or passkey enforcement and step-up authentication for billing/catalogue
   changes.
2. Extend the initial append-only platform audit trail to failed logins, subscription overrides, refunds and administrator lifecycle.
3. Explicit least-privilege permissions (support, billing, catalogue, security)
   rather than granting every administrator every capability.
4. Invitation/rotation/recovery workflows with two-person approval for
   superadmin creation and sensitive account changes.
5. Rate-limit and security tests against the deployed reverse-proxy topology.
6. Frontend platform-admin application and separate session storage/guards.
7. A reviewed backup/restore and migration rollback plan.

The platform subscription records remain separate from landlord rent invoices,
payments, payment credentials and settlement destinations. No payment
collection or subscription activation is introduced by this change.
