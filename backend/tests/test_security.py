"""
Security core tests: JWT issuance/validation and password hashing.

These run without a database — they exercise the code paths that authenticate
every request, plus the regressions found in the security audit.
"""

from __future__ import annotations

import base64
import importlib
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.core import security
from app.core.config import settings


def _encode(sub="user-1", secret=None, algorithm=None, exp_delta=60, typ="access", extra=None):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + timedelta(seconds=exp_delta),
        "type": typ,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        secret if secret is not None else settings.effective_jwt_secret,
        algorithm=algorithm or settings.ALGORITHM,
    )


# ── JWT ──────────────────────────────────────────────────────────

def test_access_token_round_trip():
    token = security.create_access_token("user-abc")
    payload = security.decode_token(token)
    assert payload["sub"] == "user-abc"
    assert payload["type"] == "access"


def test_refresh_token_round_trip():
    token = security.create_refresh_token("user-abc")
    payload = security.decode_token(token)
    assert payload["sub"] == "user-abc"
    assert payload["type"] == "refresh"


def test_extra_claims_survive_round_trip():
    token = security.create_access_token("u1", extra_claims={"role": "owner"})
    assert security.decode_token(token)["role"] == "owner"


def test_encode_and_decode_use_the_same_secret(monkeypatch):
    """
    Regression: tokens were signed with effective_jwt_secret (JWT_SECRET or
    SECRET_KEY) but verified with SECRET_KEY alone, so every issued token was
    rejected whenever JWT_SECRET differed from SECRET_KEY.
    """
    monkeypatch.setattr(settings, "SECRET_KEY", "secret-key-value")
    monkeypatch.setattr(settings, "JWT_SECRET", "different-jwt-secret")

    token = security.create_access_token("user-1")
    assert security.decode_token(token)["sub"] == "user-1"


def test_jwt_secret_falls_back_to_secret_key(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "only-secret")
    monkeypatch.setattr(settings, "JWT_SECRET", None)

    token = security.create_access_token("user-1")
    assert security.decode_token(token)["sub"] == "user-1"


def test_tampered_signature_is_rejected():
    forged = _encode(secret="not-the-real-secret")
    with pytest.raises(JWTError):
        security.decode_token(forged)


def test_tampered_payload_is_rejected():
    token = security.create_access_token("user-1")
    header, payload, signature = token.split(".")
    swap = base64.urlsafe_b64encode(
        json.dumps({"sub": "admin", "exp": int(time.time()) + 600}).encode()
    ).rstrip(b"=").decode()
    with pytest.raises(JWTError):
        security.decode_token(f"{header}.{swap}.{signature}")


def test_alg_none_is_rejected():
    """A token claiming 'alg: none' must never be accepted."""
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = b64(json.dumps({"sub": "attacker", "exp": int(time.time()) + 600}).encode())
    with pytest.raises(JWTError):
        security.decode_token(f"{header}.{body}.")


def test_expired_token_is_rejected():
    expired = _encode(exp_delta=-60)
    with pytest.raises(JWTError):
        security.decode_token(expired)


def test_token_without_subject_is_rejected():
    no_sub = jwt.encode(
        {"exp": int(time.time()) + 600},
        settings.effective_jwt_secret,
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(JWTError):
        security.decode_token(no_sub)


def test_garbage_token_is_rejected():
    with pytest.raises(JWTError):
        security.decode_token("not.a.jwt")


# ── Password hashing ────────────────────────────────────────────

def test_password_hash_round_trip():
    hashed = security.hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", hashed)
    assert not security.verify_password("wrong password", hashed)


def test_hashes_are_salted():
    assert security.hash_password("same") != security.hash_password("same")


def test_bcrypt_rounds_come_from_config():
    """
    Regression: BCRYPT_ROUNDS was declared in config but never passed to
    CryptContext, so tuning it had no effect.
    """
    monkeypatched = importlib.reload(security)
    original = settings.BCRYPT_ROUNDS
    try:
        settings.BCRYPT_ROUNDS = 5
        reloaded = importlib.reload(monkeypatched)
        cost = int(reloaded.hash_password("pw").split("$")[2])
        assert cost == 5
    finally:
        settings.BCRYPT_ROUNDS = original
        importlib.reload(security)
