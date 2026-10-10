"""
IMANI Business OS

Module:
    Security Core

Author:
    OpenAI + Your Team

Purpose:
    JWT token creation/verification and password hashing.

Note:
    Route authorisation is enforced by the ``require_owner`` dependency in
    ``app/api/deps.py``. A separate role/permission catalogue used to live here
    but was never referenced by any route and has been removed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password Hashing (bcrypt) ───────────────────────────────────
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT Tokens ──────────────────────────────────────────────────

def create_access_token(
    subject: str,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        subject: Unique user identifier (UUID).
        extra_claims: Optional additional claims (e.g. role, business_id).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + settings.access_token_expiry,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.effective_jwt_secret, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """
    Create a long-lived JWT refresh token.

    Args:
        subject: Unique user identifier (UUID).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + settings.refresh_token_expiry,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.effective_jwt_secret, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Hardened validation — must reject every known forgery class:
      * ``alg: none`` (no signature)            → rejected (algorithm pinned)
      * tampered / wrong-key signature          → rejected (signature verified)
      * expired token                           → rejected (exp verified)
      * missing required claims (sub, exp)       → rejected (claim required)

    Args:
        token: The JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        JWTError: If the token is invalid, expired, or missing required claims.
    """
    # Must match the key used by create_access_token/create_refresh_token above.
    # Reading SECRET_KEY here while signing with effective_jwt_secret silently
    # broke every token whenever JWT_SECRET was set to a different value.
    payload = jwt.decode(
        token,
        settings.effective_jwt_secret,
        algorithms=[settings.ALGORITHM],
        options={
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "require_exp": True,
            "require_sub": True,
        },
    )

    # Defence-in-depth: never trust a token without a subject.
    if not payload.get("sub"):
        raise JWTError("Token missing required 'sub' claim")

    return payload
