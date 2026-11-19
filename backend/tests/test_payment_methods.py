"""
Additional payment rails.

Every rail converges on `apply_payment`, so these tests focus on what is
specific to each one: the reference that identifies the invoice, the callback
that settles it, idempotency under provider retries, and the rule that a
self-declared bank transfer is never treated as settled money.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from tests.conftest import requires_db


def test_the_help_menu_only_offers_rails_that_are_actually_configured(monkeypatch):
    from app.core.config import settings
    from app.notifications.templates import _build_wa_help
    from app.payments.availability import available_methods

    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "")
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "")
    monkeypatch.setattr(settings, "MPESA_SHORTCODE", "")
    monkeypatch.setattr(settings, "MPESA_PASSKEY", "")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "")

    menu = _build_wa_help(available_methods(None))
    assert "PAY" not in menu
    assert "AIRTEL" not in menu
    assert "CARD" not in menu
    assert "DONE <ref>" in menu  # a bank claim always works

    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "key")
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "secret")
    monkeypatch.setattr(settings, "MPESA_SHORTCODE", "600600")
    monkeypatch.setattr(settings, "MPESA_PASSKEY", "passkey")
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "sk_test")

    menu = _build_wa_help(available_methods(None))
    assert "PAY" in menu
    assert "CARD" in menu
    assert "AIRTEL" not in menu


def test_gateway_references_round_trip_through_the_invoice_id():
    import uuid

    from app.payments import airtel, flutterwave

    invoice_id = uuid.uuid4()
    assert airtel.invoice_id_from_reference(airtel.reference_for(invoice_id)) == str(invoice_id)
    assert flutterwave.invoice_id_from_tx_ref(flutterwave.tx_ref_for(invoice_id)) == str(invoice_id)
    assert airtel.invoice_id_from_reference("rent-not-a-uuid") is None
    assert flutterwave.invoice_id_from_tx_ref(None) is None


def test_enabled_methods_intersects_the_landlords_choice_with_what_is_configured(
    monkeypatch,
):
    from types import SimpleNamespace

    from app.core.config import settings
    from app.payments.availability import enabled_methods

    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "")
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "")
    monkeypatch.setattr(settings, "MPESA_SHORTCODE", "")
    monkeypatch.setattr(settings, "MPESA_PASSKEY", "")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "")

    business = SimpleNamespace(
        settings={"business": {"payment_methods": ["card", "bank", "airtel"]}},
        mpesa_shortcode=None,
    )
    # Only the bank claim is possible until a rail is configured.
    assert enabled_methods(business) == ["bank"]

    business.mpesa_shortcode = "600600"
    assert enabled_methods(business) == ["bank"], "M-Pesa was not selected"

    business.settings = {"business": {"payment_methods": ["mpesa", "bank"]}}
    assert enabled_methods(business) == ["mpesa", "bank"]

    # Businesses saved before the multi-rail setting keep working.
    business.settings = {"business": {"payment_method": "bank"}}
    assert enabled_methods(business) == ["bank"]


def test_business_config_rejects_an_unknown_payment_rail():
    from pydantic import ValidationError

    from app.notifications.router import BusinessConfigRequest

    with pytest.raises(ValidationError):
        BusinessConfigRequest(business_name="Alpha", payment_method="cash")


@requires_db
async def test_pay_follows_the_rail_the_landlord_selected(businesses, db_session, monkeypatch):
    from app.core.config import settings
    from app.notifications.inbound_tenant import _cmd_tenant_pay
    from app.payments import flutterwave

    first, _ = businesses

    # Airtel selected, but not configured on this deployment: PAY must say so
    # instead of falling back to M-Pesa instructions.
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_SECRET", "")
    first.business.settings = {"business": {"payment_method": "airtel"}}
    await db_session.flush()

    reply = await _cmd_tenant_pay(db_session, first.tenant, first.business.id)
    assert "Airtel Money" in reply["message"]
    assert "Paybill" not in reply["message"]

    # Card selected: PAY hands back the hosted checkout link.
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "sk_test")

    async def fake_checkout(session, invoice_id):
        return {"checkout_url": "https://checkout.example/pay", "tx_ref": "rent-test"}

    monkeypatch.setattr(flutterwave, "create_checkout", fake_checkout)
    first.business.settings = {"business": {"payment_method": "card"}}
    await db_session.flush()

    reply = await _cmd_tenant_pay(db_session, first.tenant, first.business.id)
    assert "https://checkout.example/pay" in reply["message"]


@requires_db
async def test_saving_an_unconfigured_rail_is_rejected(
    client, businesses, db_session, monkeypatch
):
    from app.core.config import settings

    first, _ = businesses
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_SECRET", "")

    response = await client.put(
        "/api/v1/notifications/business-config",
        json={
            "business_name": first.business.name,
            "payment_methods": ["airtel"],
            "payment_method": "airtel",
        },
        headers=first.bearer,
    )

    assert response.status_code == 400
    assert "Airtel Money" in response.json()["detail"]
    await db_session.refresh(first.business)
    assert (first.business.settings or {}).get("business", {}).get(
        "payment_methods"
    ) is None, "a rejected save must not persist"


@requires_db
async def test_saving_a_paybill_makes_mpesa_usable(client, businesses, db_session, monkeypatch):
    from app.core.config import settings

    first, _ = businesses
    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "")
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "")
    monkeypatch.setattr(settings, "MPESA_SHORTCODE", "")
    monkeypatch.setattr(settings, "MPESA_PASSKEY", "")
    first.business.mpesa_shortcode = None
    await db_session.flush()

    response = await client.put(
        "/api/v1/notifications/business-config",
        json={
            "business_name": first.business.name,
            "payment_methods": ["mpesa"],
            "payment_method": "mpesa",
            "mpesa_paybill": "600600",
        },
        headers=first.bearer,
    )

    assert response.status_code == 200
    await db_session.refresh(first.business)
    assert first.business.mpesa_shortcode == "600600"
    assert first.business.settings["business"]["payment_methods"] == ["mpesa"]


@requires_db
async def test_balance_shows_the_enabled_rails_and_bank_details(
    businesses, db_session
):
    from app.notifications.inbound_tenant import _cmd_tenant_balance

    first, _ = businesses
    first.business.settings = {
        "business": {
            "payment_methods": ["bank"],
            "bank_name": "Equity Bank",
            "bank_account": "1220123456789",
            "bank_account_name": "Alpha Homes",
        }
    }
    await db_session.flush()

    reply = await _cmd_tenant_balance(db_session, first.tenant, first.business.id)
    msg = reply["message"]

    assert "Outstanding: KES 15,000" in msg
    assert "Equity Bank" in msg
    assert "1220123456789" in msg
    assert "Alpha Homes" in msg
    assert "DONE <reference>" in msg
    # A rail that is not enabled must not be advertised.
    assert "M-Pesa" not in msg


@requires_db
async def test_pay_offers_every_enabled_rail_and_routes_the_choice(
    businesses, db_session, monkeypatch
):
    from app.core.config import settings
    from app.notifications.inbound_tenant import _cmd_tenant_pay
    from app.payments import flutterwave

    first, _ = businesses
    first.business.mpesa_shortcode = "600600"
    monkeypatch.setattr(settings, "MPESA_CONSUMER_KEY", "")
    monkeypatch.setattr(settings, "MPESA_CONSUMER_SECRET", "")
    monkeypatch.setattr(settings, "MPESA_SHORTCODE", "600600")
    monkeypatch.setattr(settings, "MPESA_PASSKEY", "")
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "sk_test")
    first.business.settings = {
        "business": {"payment_methods": ["mpesa", "card", "airtel"]}
    }
    await db_session.flush()

    # Airtel is selected but not configured here, so PAY must not offer it.
    reply = await _cmd_tenant_pay(db_session, first.tenant, first.business.id)
    assert "PAY MPESA" in reply["message"]
    assert "PAY CARD" in reply["message"]
    assert "PAY AIRTEL" not in reply["message"]

    # Asking for a rail that is not available explains instead of guessing.
    reply = await _cmd_tenant_pay(
        db_session, first.tenant, first.business.id, "airtel"
    )
    assert "not enabled" in reply["message"]

    async def fake_checkout(session, invoice_id):
        return {
            "checkout_url": "https://checkout.example/multi",
            "tx_ref": "rent-multi",
        }

    monkeypatch.setattr(flutterwave, "create_checkout", fake_checkout)
    reply = await _cmd_tenant_pay(db_session, first.tenant, first.business.id, "card")
    assert "https://checkout.example/multi" in reply["message"]

    reply = await _cmd_tenant_pay(db_session, first.tenant, first.business.id, "mpesa")
    assert "Paybill" in reply["message"]


@requires_db
async def test_card_command_points_to_a_working_rail_when_flutterwave_is_off(
    businesses, db_session, monkeypatch
):
    from app.core.config import settings
    from app.notifications.inbound_tenant import _cmd_tenant_card

    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "")
    first, _ = businesses
    first.business.mpesa_shortcode = None
    await db_session.flush()

    reply = await _cmd_tenant_card(db_session, first.tenant, first.business.id)

    assert "not enabled" in reply["message"]
    assert "http" not in reply["message"]
    assert "DONE <reference>" in reply["message"]


@requires_db
async def test_a_paybill_confirmation_settles_the_invoice_exactly_once(
    businesses, db_session
):
    from app.models.billing import Payment
    from app.payments.c2b import record_c2b_payment

    first, _ = businesses
    first.business.mpesa_shortcode = "600600"
    await db_session.flush()

    payload = {
        "TransID": "C2B-TEST-0001",
        "TransAmount": "15000",
        "BusinessShortCode": "600600",
        "BillRefNumber": first.invoice.invoice_number,
        "MSISDN": first.tenant.mpesa_phone,
        "TransactionType": "Pay Bill",
    }

    assert await record_c2b_payment(db_session, payload) is True
    await db_session.refresh(first.invoice)
    assert first.invoice.status == "paid"
    assert first.invoice.balance == 0

    # Daraja retries confirmations; the second delivery must not double-credit.
    assert await record_c2b_payment(db_session, payload) is True
    payments = (
        await db_session.scalars(
            select(Payment).where(Payment.reference == "C2B-TEST-0001")
        )
    ).all()
    assert len(payments) == 1
    await db_session.refresh(first.invoice)
    assert first.invoice.balance == 0


@requires_db
async def test_an_airtel_callback_settles_the_invoice_named_in_the_reference(
    businesses, db_session
):
    from app.models.billing import Payment
    from app.payments.airtel import handle_callback

    first, _ = businesses
    payload = {
        "transaction": {
            "id": "AT-TX-0001",
            "status_code": "TS",
            "airtel_money_id": "AT-MONEY-0001",
            "amount": "15000",
            "reference": f"rent-{first.invoice.id}",
        },
        "country": "KE",
        "currency": "KES",
    }

    settled = await handle_callback(db_session, payload)
    assert settled is not None
    await db_session.refresh(first.invoice)
    assert first.invoice.status == "paid"

    payment = await db_session.scalar(
        select(Payment).where(Payment.reference == "AT-MONEY-0001")
    )
    assert payment is not None
    assert payment.method == "airtel"

    # A retried callback is not a second payment.
    await handle_callback(db_session, payload)
    payments = (
        await db_session.scalars(
            select(Payment).where(Payment.reference == "AT-MONEY-0001")
        )
    ).all()
    assert len(payments) == 1


@requires_db
async def test_done_records_a_pending_bank_claim_without_marking_paid(
    businesses, db_session
):
    from app.models.billing import Payment
    from app.notifications.inbound_tenant import _cmd_tenant_done
    from app.notifications.models import NotificationLog

    first, _ = businesses
    first.user.phone = "254700900123"
    await db_session.flush()

    reply = await _cmd_tenant_done(
        db_session, first.tenant, first.business.id, "BANKREF-123"
    )

    assert "BANKREF-123" in reply["message"]
    payment = await db_session.scalar(
        select(Payment).where(Payment.reference == "BANKREF-123")
    )
    assert payment is not None
    assert payment.method == "bank"
    assert payment.status == "pending"
    assert payment.invoice_id is None
    assert payment.amount == Decimal(15000)

    # Money is not confirmed until the owner checks the bank.
    await db_session.refresh(first.invoice)
    assert first.invoice.status == "pending"

    claim = await db_session.scalar(
        select(NotificationLog).where(
            NotificationLog.template_name == "bank_transfer_claim"
        )
    )
    assert claim is not None
    assert claim.recipient == "254700900123"


@requires_db
async def test_the_owner_can_match_a_bank_claim_to_an_invoice(businesses, db_session):
    from app.models.billing import Payment
    from app.notifications.inbound_tenant import _cmd_tenant_done
    from app.reconciliation.service import match_payment

    first, _ = businesses
    await _cmd_tenant_done(db_session, first.tenant, first.business.id, "BANKREF-456")
    payment = await db_session.scalar(
        select(Payment).where(Payment.reference == "BANKREF-456")
    )

    result = await match_payment(
        db_session, first.business.id, payment.id, first.invoice.id
    )

    await db_session.refresh(first.invoice)
    await db_session.refresh(payment)
    assert result["invoice_status"] == "paid"
    assert first.invoice.status == "paid"
    assert payment.invoice_id == first.invoice.id
    assert payment.status == "reconciled"


@requires_db
async def test_reconciliation_never_recredits_an_already_matched_payment(
    businesses, db_session
):
    """Second runs used to re-match linked payments and double-credit them."""
    from app.models.billing import Payment
    from app.reconciliation.service import reconcile_pending

    first, _ = businesses
    db_session.add(
        Payment(
            business_id=first.business.id,
            invoice_id=first.invoice.id,
            lease_id=first.lease.id,
            tenant_id=first.tenant.id,
            amount=Decimal(5000),
            method="mpesa",
            reference="PRE-LINKED-0001",
            status="completed",
            mpesa_raw={"PhoneNumber": first.tenant.mpesa_phone},
        )
    )
    await db_session.flush()

    result = await reconcile_pending(db_session, first.business.id)

    assert result["total_processed"] == 0
    await db_session.refresh(first.invoice)
    assert first.invoice.paid_amount == Decimal(0)


@requires_db
async def test_airtel_collect_sends_the_full_balance_not_a_truncated_one(
    businesses, db_session, monkeypatch
):
    """`int(inv.balance)` floored cents, so a 15,000.75 balance asked for 15,000."""
    from app.core.config import settings
    from app.payments import airtel

    first, _ = businesses
    first.invoice.balance = Decimal("15000.75")
    await db_session.flush()

    sent: list[dict] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            sent.append({"url": url, **kwargs})
            if url.endswith("/auth/oauth2/token"):
                return FakeResponse({"access_token": "token"})
            return FakeResponse({"status": {"success": True}})

    monkeypatch.setattr(settings, "AIRTEL_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "AIRTEL_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(airtel.httpx, "AsyncClient", FakeClient)

    await airtel.collect(db_session, str(first.invoice.id), "254700000000")

    payment_request = sent[-1]["json"]
    assert payment_request["transaction"]["amount"] == 15000.75
    assert payment_request["transaction"]["amount"] != 15000
