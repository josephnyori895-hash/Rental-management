"""Create the first Rental OS platform administrator from trusted CLI environment.

Required environment: PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_NAME,
PLATFORM_ADMIN_PASSWORD. Run only after the platform_admins migration.
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select
from pydantic import EmailStr, TypeAdapter

from app.core.database import async_session_factory, close_db
from app.core.security import hash_password
from app.models.platform_admin import PlatformAdmin


async def main() -> None:
    raw_email = os.environ.get("PLATFORM_ADMIN_EMAIL", "").strip()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(raw_email)).lower()
    except Exception:
        raise SystemExit("PLATFORM_ADMIN_EMAIL must be a valid email address.")
    name = os.environ.get("PLATFORM_ADMIN_NAME", "").strip()
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "")
    if not name or len(password) < 14 or len(password.encode("utf-8")) > 72:
        raise SystemExit("Set PLATFORM_ADMIN_NAME and a password of 14-72 UTF-8 bytes; set PLATFORM_ADMIN_EMAIL to a valid address.")
    async with async_session_factory() as session:
        exists = await session.scalar(select(PlatformAdmin.id).where(PlatformAdmin.email == email))
        if exists:
            raise SystemExit("That platform administrator already exists; bootstrap never overwrites accounts.")
        session.add(PlatformAdmin(
            email=email, full_name=name, password_hash=hash_password(password),
            is_active=True, is_superadmin=True,
        ))
        await session.commit()
    print("Platform administrator created. Remove the bootstrap password from the environment now.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(close_db())
