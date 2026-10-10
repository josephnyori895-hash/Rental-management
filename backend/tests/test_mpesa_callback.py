"""
M-PESA callback authentication.

The callback is intentionally unauthenticated (Safaricom cannot send a bearer
token), which is why it needs its own shared-secret check. Before this was
wired up the endpoint accepted any POST that named a known CheckoutRequestID.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.payments.router import _verify_callback_token


class FakeRequest:
    def __init__(self, params=None):
        self.query_params = params or {}


REAL_SECRET = "a-real-random-callback-secret"


def test_placeholder_secret_disables_verification(monkeypatch):
    """
    The shipped .env carries a placeholder. Treating it as configured would
    start rejecting live Safaricom callbacks, so it must be ignored.
    """
    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", "change-this-to-a-random-secret")
    _verify_callback_token(FakeRequest({}))  # must not raise


def test_empty_secret_disables_verification(monkeypatch):
    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", "")
    _verify_callback_token(FakeRequest({}))  # must not raise


def test_correct_token_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", REAL_SECRET)
    _verify_callback_token(FakeRequest({"token": REAL_SECRET}))


def test_forged_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", REAL_SECRET)
    with pytest.raises(HTTPException) as exc:
        _verify_callback_token(FakeRequest({"token": "forged"}))
    assert exc.value.status_code == 403


def test_missing_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", REAL_SECRET)
    with pytest.raises(HTTPException) as exc:
        _verify_callback_token(FakeRequest({}))
    assert exc.value.status_code == 403


def test_empty_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", REAL_SECRET)
    with pytest.raises(HTTPException):
        _verify_callback_token(FakeRequest({"token": ""}))


async def test_callback_endpoint_rejects_forged_call(monkeypatch):
    """End-to-end: a forged callback must never reach the payment logic."""
    import httpx

    from app.main import app

    monkeypatch.setattr(settings, "MPESA_CALLBACK_SECRET", REAL_SECRET)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/payments/mpesa/callback",
            json={"Body": {"stkCallback": {"ResultCode": 0, "CheckoutRequestID": "forged"}}},
        )
    assert response.status_code == 403
