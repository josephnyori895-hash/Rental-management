"""Authentication and self-service profile for Rental OS platform staff.

There is deliberately no public registration endpoint. Initial accounts must be
provisioned by a trusted operator through the deployment's controlled process.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.ratelimit import login_limiter
from app.core.security import create_access_token, verify_password
from app.models.platform_admin import PlatformAdmin
from app.platform_admin.dependencies import PlatformAdminDep, PlatformAdminSession

router = APIRouter(prefix="/platform-admin", tags=["platform administration"])


class PlatformAdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login", dependencies=[Depends(login_limiter)])
async def platform_admin_login(data: PlatformAdminLogin, session: PlatformAdminSession):
    admin = await session.scalar(
        select(PlatformAdmin).where(PlatformAdmin.email == data.email.lower())
    )
    # Same response for unknown, inactive and incorrect-password accounts.
    if not admin or not admin.is_active or not verify_password(data.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        subject=str(admin.id),
        extra_claims={"type": "platform_admin_access", "principal_type": "platform_admin"},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": int(settings.access_token_expiry.total_seconds()),
        "admin": {"id": str(admin.id), "email": admin.email, "full_name": admin.full_name,
                  "is_superadmin": admin.is_superadmin},
    }


@router.get("/auth/me")
async def platform_admin_me(admin: PlatformAdminDep):
    return {"id": str(admin.id), "email": admin.email, "full_name": admin.full_name,
            "is_superadmin": admin.is_superadmin}
