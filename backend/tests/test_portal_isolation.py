from __future__ import annotations

from tests.conftest import requires_db


@requires_db
async def test_portal_renders_a_tenant_in_the_own_business(client, businesses):
    first, _ = businesses

    res = await client.get("/api/v1/portal/my-data", headers=first.bearer)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tenant"]["id"] == str(first.tenant.id)


@requires_db
async def test_portal_rejects_a_tenant_outside_the_callers_business(client, businesses):
    first, second = businesses

    res = await client.get(
        f"/api/v1/portal/my-data?tenant_id={second.tenant.id}", headers=first.bearer
    )
    assert res.status_code == 404, res.text
    assert str(second.tenant.id) not in res.text
    assert second.tenant.full_name not in res.text
    assert second.tenant.phone not in res.text


@requires_db
async def test_portal_rejects_a_malformed_tenant_id(client, businesses):
    first, _ = businesses

    res = await client.get(
        "/api/v1/portal/my-data?tenant_id=not-a-uuid", headers=first.bearer
    )
    assert res.status_code == 404, res.text


@requires_db
async def test_portal_never_serves_a_foreign_invoice(client, businesses, db_session):
    from datetime import date
    from decimal import Decimal

    from app.models.billing import Invoice, InvoiceStatus
    from app.models.lease import LeaseStatus

    first, second = businesses

    cross = Invoice(
        business_id=second.business.id,
        lease_id=second.lease.id,
        tenant_id=first.tenant.id,
        unit_id=second.unit.id,
        property_id=second.property.id,
        invoice_number="ALPHA-INV-FOREIGN-9000",
        invoice_type="rent",
        period_start=date.today().replace(day=1),
        due_date=date.today(),
        amount=Decimal("777"),
        paid_amount=Decimal("0"),
        balance=Decimal("777"),
        status=InvoiceStatus.PENDING.value,
    )
    db_session.add(cross)
    await db_session.commit()

    res = await client.get("/api/v1/portal/my-data", headers=first.bearer)
    assert res.status_code == 200, res.text
    assert str(cross.id) not in res.text
    assert cross.invoice_number not in res.text
