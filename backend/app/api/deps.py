"""
RENTAL OS — API Dependencies

Module:
    Shared FastAPI dependencies: DB session, current user, current
    business (tenant scope) and role enforcement.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_token
from app.models.business import User
from app.models.business import Business

SessionDep = Annotated[AsyncSession, Depends(get_session)]

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: SessionDep = None,
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if not token:
        raise _CREDENTIALS_ERROR
    try:
        payload = decode_token(token)
    except Exception:
        raise _CREDENTIALS_ERROR
    user_id = payload.get("sub")
    if not user_id:
        raise _CREDENTIALS_ERROR
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user


async def get_current_business(
    session: SessionDep,
    user: User = Depends(get_current_user),
) -> Business:
    """Resolve the tenant (business) the current user belongs to."""
    business = await session.get(Business, user.business_id)
    if not business or not business.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Business inactive"
        )
    return business


async def require_owner(user: User = Depends(get_current_user)) -> User:
    """Enforce that the current user has the owner role."""
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can access this resource",
        )
    return user


OwnerDep = Annotated[User, Depends(require_owner)]


def require_roles(*roles: str):
    """Dependency factory enforcing one of the allowed roles."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _checker
