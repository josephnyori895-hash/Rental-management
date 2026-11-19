"""
RENTAL OS — Who is responsible for a property

A business can run many buildings with a different caretaker on each. The
assignment lives on `Property.manager_id`; anything that says it notifies "the
caretaker" must resolve that link, because picking the first active agent in
the business sends one building's leak to another building's caretaker.

The fallback is the owner, never an unrelated caretaker: a message sent to the
wrong person is worse than a message sent to the person accountable.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import User, UserRole
from app.models.property import Property


async def property_recipient_phones(
    session: AsyncSession,
    business_id: uuid.UUID,
    property_id: uuid.UUID | None,
) -> list[str]:
    """Phones to notify about one property: its caretaker, else the owner(s)."""
    if property_id is not None:
        prop = await session.get(Property, property_id)
        if prop is not None and prop.business_id == business_id and prop.manager_id:
            caretaker = await session.scalar(
                select(User).where(
                    User.id == prop.manager_id,
                    User.business_id == business_id,
                    User.is_active.is_(True),
                )
            )
            if caretaker is not None and caretaker.phone:
                return [caretaker.phone]

    owners = (
        await session.scalars(
            select(User).where(
                User.business_id == business_id,
                User.role == UserRole.OWNER.value,
                User.is_active.is_(True),
            )
        )
    ).all()
    return [owner.phone for owner in owners if owner.phone]


def role_scoped_properties(properties: list, user: User) -> list:
    """The properties a user may act on.

    Owners and managers run the whole portfolio. An agent gets exactly the
    buildings assigned to them — and if none are, none. The previous version
    fell back to *every* property for an unassigned caretaker, which let any
    agent add tenants or log meters anywhere in the business.
    """
    if user.role in (UserRole.OWNER.value, UserRole.MANAGER.value):
        return list(properties)
    return [prop for prop in properties if prop.manager_id == user.id]
