"""Platform-admin authentication; landlord JWTs are never accepted here."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_token
from app.models.platform_admin import PlatformAdmin

platform_admin_bearer = OAuth2PasswordBearer(
    tokenUrl="/api/v1/platform-admin/auth/login", auto_error=False
)
PlatformAdminSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_platform_admin(
    token: str | None = Depends(platform_admin_bearer),
    session: PlatformAdminSession = None,
) -> PlatformAdmin:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Platform administrator authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    try:
        claims = decode_token(token)
    except Exception:
        raise unauthorized
    if claims.get("type") != "platform_admin_access" or claims.get("principal_type") != "platform_admin":
        raise unauthorized
    try:
        admin_id = UUID(claims.get("sub"))
    except (TypeError, ValueError):
        raise unauthorized
    admin = await session.get(PlatformAdmin, admin_id)
    if not admin or not admin.is_active:
        raise unauthorized
    return admin


PlatformAdminDep = Annotated[PlatformAdmin, Depends(get_current_platform_admin)]



async def get_current_superadmin(admin: PlatformAdminDep) -> PlatformAdmin:
    if not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadministrator access required",
        )
    return admin


SuperAdminDep = Annotated[PlatformAdmin, Depends(get_current_superadmin)]
