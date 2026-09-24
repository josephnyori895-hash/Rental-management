"""
RENTAL OS — Auth Router
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, get_current_user, require_roles
from app.core.ratelimit import login_limiter
from app.core.security import decode_token
from app.models.business import User
from app.models.business import Business
from app.auth import service
from app.auth.schemas import (
    BusinessOut,
    LoginRequest,
    PinLoginRequest,
    RefreshRequest,
    RegisterBusinessRequest,
    StaffCreate,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterBusinessRequest, session: SessionDep):
    """Register a new rental business and its owner. Public endpoint."""
    existing = await session.scalar(select(User).where(User.email == data.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    business, owner = await service.register_business(session, data)
    # Seed the default chart of accounts for this business.
    from app.accounting.service import ensure_system_accounts

    await ensure_system_accounts(session, business.id)
    await session.commit()
    return business


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter)])
async def login(data: LoginRequest, session: SessionDep):
    """Email + password login for owners/managers."""
    user = await service.authenticate(session, data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access, refresh = service.create_tokens(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/pin-login", response_model=TokenResponse, dependencies=[Depends(login_limiter)])
async def pin_login(data: PinLoginRequest, session: SessionDep):
    """Business slug + PIN login for agents/caretakers on the floor."""
    user = await service.authenticate_pin(session, data.slug, data.pin)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid slug or PIN")
    access, refresh = service.create_tokens(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, session: SessionDep):
    """Exchange a refresh token for a new access token."""
    try:
        payload = decode_token(data.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user = await session.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    access, refresh = service.create_tokens(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Current authenticated user profile."""
    return current_user


@router.post("/staff", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_staff(
    data: StaffCreate,
    session: SessionDep,
    actor: User = Depends(require_roles("owner", "manager")),
):
    """Provision a staff member (manager/agent). Owner or manager only."""
    existing = await session.scalar(select(User).where(User.email == data.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    staff = await service.create_staff(session, actor.business_id, data, actor)
    await session.commit()
    return staff
