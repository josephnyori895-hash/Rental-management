"""
Add a test user: mothernature@rental.dev / MotherNature@254
"""
from __future__ import annotations

import asyncio
from sqlalchemy import text, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.business import Business, User, UserRole


async def main() -> None:
    async with async_session_factory() as s:
        biz = await s.scalar(select(Business).limit(1))
        if not biz:
            print("No business found. Run seed.py first.")
            return

        # Check if user already exists
        existing = await s.scalar(
            select(User).where(User.email == "mothernature@rental.dev").limit(1)
        )
        if existing:
            print("User mothernature@rental.dev already exists.")
            return

        user = User(
            business_id=biz.id,
            email="mothernature@rental.dev",
            password_hash=hash_password("MotherNature@254"),
            full_name="Mother Nature",
            phone="254700000001",
            role=UserRole.OWNER.value,
            is_active=True,
        )
        s.add(user)
        await s.commit()
        print("Created: mothernature@rental.dev / MotherNature@254")


if __name__ == "__main__":
    asyncio.run(main())
