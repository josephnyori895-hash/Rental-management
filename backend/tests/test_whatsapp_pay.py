"""
WhatsApp `PAY` must charge a specific invoice.

The command used `stk_push_direct` — phone + amount with no invoice behind it.
Daraja echoes back only a CheckoutRequestID, and the callback resolves it
through `Invoice.mpesa_checkout_request_id`, which a direct push never sets. So
the tenant paid, Safaricom took the money, and the ledger recorded nothing.

The push now names the oldest unpaid invoice, and the message says what is left
on the others.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from tests.conftest import enroll_tenant, requires_db


async def _unpaid(session, lease_id):
    from app.models.billing import Invoice

    return (
        await session.scalars(
            select(Invoice).where(
                Invoice.lease_id == lease_id, Invoice.balance > 0
            )
        )
    ).all()


@requires_db
async def test_pay_pushes_the_oldest_unpaid_invoice(
    client, businesses, db_session, monkeypatch
):
    from app.core.config import settings
    from app.models.tenant import Tenant
    from app.notifications.inbound_tenant import _cmd_tenant_pay
    from app.payments import service as pay_svc

    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000", deposit="15000")
    lease_id = uuid.UUID(enrolled["body"]["lease_id"])
    tenant = await db_session.get(Tenant, uuid.UUID(enrolled["body"]["tenant_id"]))

    invoices = await _unpaid(db_session, lease_id)
    rent_invoice = next(i for i in invoices if i.invoice_type == "rent")
    deposit_invoice = next(i for i in invoices if i.invoice_type == "deposit")
    # Move the deposit out of the way so "oldest" is not a tie.
    deposit_invoice.due_date = date.today() + timedelta(days=10)
    await db_session.flush()

    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "test-secret", raising=False)

    pushed: dict = {}

    async def fake_stk_push(session, invoice_id, phone):
        pushed["invoice_id"] = invoice_id
        pushed["phone"] = phone
        return "ws_CO_TEST"

    monkeypatch.setattr(pay_svc, "stk_push", fake_stk_push)

    reply = await _cmd_tenant_pay(db_session, tenant, first.business.id)

    assert pushed["invoice_id"] == str(rent_invoice.id), (
        "the push must name the invoice the callback will credit"
    )
    assert "STK Push" in reply["message"]
    assert "12,000" in reply["message"]
    assert "15,000" in reply["message"], "the tenant is told what remains on other invoices"


@requires_db
async def test_pay_falls_back_to_paybill_without_daraja(
    client, businesses, db_session, monkeypatch
):
    """No credentials is not a failed payment — it is instructions."""
    from app.core.config import settings
    from app.models.tenant import Tenant
    from app.notifications.inbound_tenant import _cmd_tenant_pay

    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000", deposit="0")
    tenant = await db_session.get(Tenant, uuid.UUID(enrolled["body"]["tenant_id"]))

    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "", raising=False)
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "", raising=False)
    # The owner has a Paybill, even though Daraja STK is not set up.
    monkeypatch.setattr(settings, "MPESA_SHORTCODE", "600600", raising=False)
    monkeypatch.setattr(settings, "MPESA_PASSKEY", "", raising=False)

    reply = await _cmd_tenant_pay(db_session, tenant, first.business.id)

    assert "Paybill" in reply["message"]
    assert "600600" in reply["message"]
    assert "12,000" in reply["message"]
