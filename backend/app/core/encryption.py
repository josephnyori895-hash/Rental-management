"""
IMANI — Encryption Utility

AES-256-GCM symmetric encryption for sensitive stored fields.
Uses a master key from environment (ENCRYPTION_KEY) — never hardcoded.
Each field gets a unique nonce per encryption operation.

Usage:
    encrypted = encrypt_field("consumer_key_123")
    decrypted = decrypt_field(encrypted)  # "consumer_key_123"
"""

import os
import base64
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# ── Master Key ───────────────────────────────────────────────

def _get_master_key() -> bytes:
    """Get the master encryption key.

    The key should be a 64-character hex string (32 bytes).
    Generate one with: openssl rand -hex 32
    Sourced from settings.ENCRYPTION_KEY (loaded via .env), with a
    fallback to the raw environment variable for non-pydantic contexts.
    """
    key_hex = None
    try:
        from app.core.config import settings

        key_hex = getattr(settings, "ENCRYPTION_KEY", None)
    except Exception:
        pass
    if not key_hex:
        key_hex = os.getenv("ENCRYPTION_KEY")
    if not key_hex or key_hex == "change-me-in-production":
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: openssl rand -hex 32"
        )
    return bytes.fromhex(key_hex)


# ── Derive a field-specific key ──────────────────────────────

def _derive_key(master_key: bytes, salt: bytes) -> bytes:
    """Derive a 256-bit key using HKDF with a salt per field type."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"imani-field-encryption-v1",
    )
    return hkdf.derive(master_key)


# ── Encrypt ──────────────────────────────────────────────────

def encrypt_field(plaintext: str, field_salt: Optional[bytes] = None) -> str:
    """Encrypt a string field using AES-256-GCM.
    
    Returns a base64-encoded string containing: nonce + ciphertext
    The nonce is randomly generated per call (12 bytes).
    """
    if not plaintext:
        return ""

    master_key = _get_master_key()
    salt = field_salt or b"imani-default-field"
    key = _derive_key(master_key, salt)

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Prepend nonce to ciphertext for storage
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("ascii")


# ── Decrypt ──────────────────────────────────────────────────

def decrypt_field(encrypted: str, field_salt: Optional[bytes] = None) -> str:
    """Decrypt a field encrypted with encrypt_field().
    
    Accepts the base64-encoded string and returns the original plaintext.
    """
    if not encrypted:
        return ""

    master_key = _get_master_key()
    salt = field_salt or b"imani-default-field"
    key = _derive_key(master_key, salt)

    aesgcm = AESGCM(key)
    combined = base64.b64decode(encrypted)

    nonce = combined[:12]
    ciphertext = combined[12:]

    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


# ── Field-specific salts for Daraja credentials ──────────────

DARAJA_CONSUMER_KEY_SALT = b"imani-daraja-consumer-key-v1"
DARAJA_CONSUMER_SECRET_SALT = b"imani-daraja-consumer-secret-v1"
DARAJA_PASSKEY_SALT = b"imani-daraja-passkey-v1"
DARAJA_CALLBACK_SECRET_SALT = b"imani-daraja-callback-secret-v1"
DARAJA_B2C_CONSUMER_KEY_SALT = b"imani-daraja-b2c-consumer-key-v1"
DARAJA_B2C_CONSUMER_SECRET_SALT = b"imani-daraja-b2c-consumer-secret-v1"
DARAJA_B2C_INITIATOR_PASSWORD_SALT = b"imani-daraja-b2c-initiator-password-v1"


def encrypt_daraja_consumer_key(value: str) -> str:
    return encrypt_field(value, DARAJA_CONSUMER_KEY_SALT)


def decrypt_daraja_consumer_key(value: str) -> str:
    return decrypt_field(value, DARAJA_CONSUMER_KEY_SALT)


def encrypt_daraja_consumer_secret(value: str) -> str:
    return encrypt_field(value, DARAJA_CONSUMER_SECRET_SALT)


def decrypt_daraja_consumer_secret(value: str) -> str:
    return decrypt_field(value, DARAJA_CONSUMER_SECRET_SALT)


def encrypt_daraja_passkey(value: str) -> str:
    return encrypt_field(value, DARAJA_PASSKEY_SALT)


def decrypt_daraja_passkey(value: str) -> str:
    return decrypt_field(value, DARAJA_PASSKEY_SALT)


def encrypt_daraja_callback_secret(value: str) -> str:
    return encrypt_field(value, DARAJA_CALLBACK_SECRET_SALT)


def decrypt_daraja_callback_secret(value: str) -> str:
    return decrypt_field(value, DARAJA_CALLBACK_SECRET_SALT)


# ── B2C field encryption ─────────────────────────────────────


def encrypt_daraja_b2c_consumer_key(value: str) -> str:
    return encrypt_field(value, DARAJA_B2C_CONSUMER_KEY_SALT)


def decrypt_daraja_b2c_consumer_key(value: str) -> str:
    return decrypt_field(value, DARAJA_B2C_CONSUMER_KEY_SALT)


def encrypt_daraja_b2c_consumer_secret(value: str) -> str:
    return encrypt_field(value, DARAJA_B2C_CONSUMER_SECRET_SALT)


def decrypt_daraja_b2c_consumer_secret(value: str) -> str:
    return decrypt_field(value, DARAJA_B2C_CONSUMER_SECRET_SALT)


def encrypt_daraja_b2c_initiator_password(value: str) -> str:
    return encrypt_field(value, DARAJA_B2C_INITIATOR_PASSWORD_SALT)


def decrypt_daraja_b2c_initiator_password(value: str) -> str:
    return decrypt_field(value, DARAJA_B2C_INITIATOR_PASSWORD_SALT)
