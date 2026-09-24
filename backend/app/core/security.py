"""
IMANI Business OS

Module:
    Security Core

Author:
    OpenAI + Your Team

Purpose:
    JWT token creation/verification, password hashing,
    permission enforcement, and role-based access control.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password Hashing (bcrypt) ───────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    # Enforce a single, explicit signing algorithm. python-jose will raise if the
    # token's ``alg`` is anything other than the configured value (incl. "none").
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
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


# ── Role Constants ──────────────────────────────────────────────

class Roles:
    """Centralised role definitions for IMANI."""

    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    MANAGER = "manager"
    WAITER = "waiter"

    HIERARCHY = {
        SUPER_ADMIN: 100,
        OWNER: 80,
        MANAGER: 50,
        WAITER: 10,
        "cashier": 10,
    }

    @classmethod
    def has_permission(cls, user_role: str, required_role: str) -> bool:
        """
        Check if a user's role has sufficient permissions.

        Args:
            user_role: The role assigned to the user.
            required_role: The minimum role required.

        Returns:
            True if user_role >= required_role in hierarchy.
        """
        return cls.HIERARCHY.get(user_role, 0) >= cls.HIERARCHY.get(required_role, 0)


# ── Permissions ─────────────────────────────────────────────────

PERMISSIONS = {
    Roles.OWNER: [
        "business:read", "business:write",
        "staff:read", "staff:write", "staff:delete",
        "catalog:read", "catalog:write", "catalog:delete",
        "pos:read", "pos:write",
        "orders:read", "orders:write",
        "reports:read",
        "accounting:read", "accounting:write",
        "inventory:read", "inventory:write",
        "payments:read", "payments:write",
        "settings:read", "settings:write",
        "subscription:read", "subscription:write",
        "cctv:read",
        "ai:read",
    ],
    Roles.MANAGER: [
        "business:read",
        "staff:read",
        "catalog:read", "catalog:write",
        "pos:read", "pos:write",
        "orders:read",
        "reports:read",
        "inventory:read", "inventory:write",
        "payments:read",
        "cctv:read",
    ],
    Roles.WAITER: [
        "pos:read", "pos:write",
        "orders:read",
        "catalog:read",
    ],
}


def permissions_for_role(role: str) -> list[str]:
    """Return the list of permissions granted to a given role."""
    return PERMISSIONS.get(role, [])
