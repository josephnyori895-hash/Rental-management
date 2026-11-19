"""
Every payment must produce a receipt.

`apply_payment` called `send_payment_receipt`, a name the notifications service
never defined. The `ImportError` happened inside a best-effort `try/except`,
which is the shape of failure that looks like success: the payment posted, the
invoice flipped to paid, and no receipt was sent — nothing anywhere said so.

These tests drive the real endpoints and assert the `NotificationLog` row. A
mocked sender would have passed with the import still missing.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from tests.conftest import enroll_tenant, requires_db

RECEIPT_TEMPLATES = ("wa_payment_receipt", "payment_receipt")


async def _receipt_logs(session, tenant_id):
    from app.notifications.models import NotificationLog

    logs = (
        await session.scalars(
            select(NotificationLog).where(NotificationLog.tenant_id == tenant_id)
        )
    ).all()
    return [log for log in logs if log.template_name in RECEIPT_TEMPLATES]


@requires_db
async def test_recording_a_payment_sends_a_receipt(client, businesses, db_session):
    """The defect end to end: money recorded, receipt logged and sent."""
    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000", deposit="0")
    tenant_id = uuid.UUID(enrolled["body"]["tenant_id"])

    response = await client.post(
        "/api/v1/payments/record",
        headers=first.bearer,
        json={
            "invoice_id": enrolled["body"]["invoice_id"],
            "amount": 12000,
            "method": "cash",
        },
    )
    assert response.status_code == 200, response.text

    receipts = await _receipt_logs(db_session, tenant_id)
    assert len(receipts) == 1, "a payment must send exactly one receipt"
    receipt = receipts[0]
    assert receipt.status == "sent"
    # The tenant was enrolled with a WhatsApp number, so WhatsApp wins.
    assert receipt.channel == "whatsapp"
    assert "12,000" in receipt.body


@requires_db
async def test_the_whatsapp_receipt_command_reports_the_latest_payment(
    client, businesses, db_session
):
    """`RECEIPT` used to read `.reference` off an Invoice and pass None as the
    payment; it errored instead of replying."""
    from app.models.tenant import Tenant
    from app.notifications.inbound_tenant import _cmd_tenant_receipt

    first, _ = businesses
    enrolled = await enroll_tenant(db_session, client, first, rent="12000", deposit="0")

    await client.post(
        "/api/v1/payments/record",
        headers=first.bearer,
        json={
            "invoice_id": enrolled["body"]["invoice_id"],
            "amount": 5000,
            "method": "mpesa",
        },
    )

    tenant = await db_session.get(Tenant, uuid.UUID(enrolled["body"]["tenant_id"]))
    reply = await _cmd_tenant_receipt(db_session, tenant, first.business.id)

    assert reply["to"] == tenant.whatsapp_phone
    assert "5,000" in reply["message"]
