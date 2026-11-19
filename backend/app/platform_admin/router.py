"""Authentication and self-service profile for Rental OS platform staff.

There is deliberately no public registration endpoint. Initial accounts must be
provisioned by a trusted operator through the deployment's controlled process.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select

from app.core.config import settings
from app.core.ratelimit import login_limiter
from app.core.security import create_access_token, verify_password
from app.models.platform_admin import PlatformAdmin
from app.models.platform_admin_event import PlatformAdminEvent
from app.platform_admin.audit import record_platform_admin_event
from app.platform_admin.dependencies import PlatformAdminDep, PlatformAdminSession

router = APIRouter(prefix="/platform-admin", tags=["platform administration"])


class PlatformAdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login", dependencies=[Depends(login_limiter)])
async def platform_admin_login(data: PlatformAdminLogin, session: PlatformAdminSession, request: Request):
    admin = await session.scalar(
        select(PlatformAdmin).where(PlatformAdmin.email == data.email.lower())
    )
    # Same response for unknown, inactive and incorrect-password accounts.
    if not admin or not admin.is_active or not verify_password(data.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    record_platform_admin_event(session, admin, "auth.login.succeeded", request=request)
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


@router.get("/events")
async def platform_admin_events(
    admin: PlatformAdminDep,
    session: PlatformAdminSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not admin.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadministrator access required")
    events = (await session.scalars(
        select(PlatformAdminEvent)
        .order_by(desc(PlatformAdminEvent.created_at))
        .limit(limit).offset(offset)
    )).all()
    return {
        "events": [{
            "id": str(event.id), "admin_email": event.email_snapshot,
            "action": event.action, "target_type": event.target_type,
            "target_id": event.target_id, "metadata": event.event_metadata,
            "ip_address": event.ip_address, "user_agent": event.user_agent,
            "created_at": event.created_at.isoformat(),
        } for event in events],
        "limit": limit, "offset": offset,
    }
