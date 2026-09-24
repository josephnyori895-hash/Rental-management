"""
RENTAL OS — Auth Schemas
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class MpesaConfig(BaseModel):
    """Daraja credentials — captured at business enrollment, encrypted at rest."""
    consumer_key: str = Field(..., min_length=4)
    consumer_secret: str = Field(..., min_length=4)
    passkey: str = Field(..., min_length=4)
    shortcode: str = Field(..., min_length=4, max_length=20)
    callback_url: str | None = None
    env: str = "sandbox"  # "sandbox" | "production"


class RegisterBusinessRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=160)
    owner_full_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone: str | None = None
    mpesa: MpesaConfig | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PinLoginRequest(BaseModel):
    slug: str
    pin: str = Field(..., min_length=4, max_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class BusinessOut(BaseModel):
    id: UUID
    name: str
    slug: str
    subscription_tier: str
    trial_ends_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class StaffCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone: str | None = None
    role: str = "agent"
    pin: str | None = Field(None, min_length=4, max_length=8)
