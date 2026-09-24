"""
RENTAL OS — Auth Service

Module:
    Business registration, credential / PIN authentication, token
    issuance and staff provisioning.
"""

from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.core.encryption import (
    encrypt_daraja_consumer_key,
    encrypt_daraja_consumer_secret,
    encrypt_daraja_passkey,
)
from app.models.business import User, UserRole
from app.models.business import Business, SubscriptionTier


def _slugify(name: str, salt: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{base}{salt}"


async def _unique_slug(session: AsyncSession, name: str) -> str:
    base = _slugify(name)
    slug = base
    n = 1
    while await session.scalar(select(Business).where(Business.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


async def register_business(
    session: AsyncSession, data
) -> tuple[Business, User]:
    """Create a business tenant and its owner user. Returns (business, user)."""
    mpesa = data.mpesa
    business = Business(
        name=data.business_name,
        slug=await _unique_slug(session, data.business_name),
        owner_id=uuid4(),  # placeholder; overwritten after user insert
        subscription_tier=SubscriptionTier.BASIC.value,
        mpesa_consumer_key=encrypt_daraja_consumer_key(mpesa.consumer_key) if mpesa else None,
        mpesa_consumer_secret=encrypt_daraja_consumer_secret(mpesa.consumer_secret) if mpesa else None,
        mpesa_passkey=encrypt_daraja_passkey(mpesa.passkey) if mpesa else None,
        mpesa_shortcode=mpesa.shortcode if mpesa else None,
        mpesa_callback_url=mpesa.callback_url if mpesa else None,
        mpesa_env=mpesa.env if mpesa else "sandbox",
    )
    session.add(business)
    await session.flush()  # assigns business.id

    owner = User(
        business_id=business.id,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.owner_full_name,
        phone=data.phone,
        role=UserRole.OWNER.value,
        is_active=True,
    )
    session.add(owner)
    await session.flush()
    business.owner_id = owner.id
    return business, owner


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.email == email))
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def authenticate_pin(session: AsyncSession, slug: str, pin: str) -> User | None:
    business = await session.scalar(select(Business).where(Business.slug == slug))
    if not business:
        return None
    user = await session.scalar(
        select(User).where(User.business_id == business.id, User.pin_hash.isnot(None))
    )
    # PIN is keyed to the business; validate against any staff with a matching PIN.
    from app.core.security import verify_password as _vp

    candidates = (
        await session.scalars(
            select(User).where(User.business_id == business.id, User.is_active.is_(True))
        )
    ).all()
    for u in candidates:
        if u.pin_hash and _vp(pin, u.pin_hash):
            return u
    return None


def create_tokens(user: User) -> tuple[str, str]:
    claims = {"role": user.role, "business_id": str(user.business_id)}
    access = create_access_token(str(user.id), extra_claims=claims)
    refresh = create_refresh_token(str(user.id))
    return access, refresh


async def create_staff(session: AsyncSession, business_id, data, actor: User) -> User:
    pin_hash = hash_password(data.pin) if data.pin else None
    staff = User(
        business_id=business_id,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=data.role,
        pin_hash=pin_hash,
        is_active=True,
    )
    session.add(staff)
    await session.flush()
    return staff
