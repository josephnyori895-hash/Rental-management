"""Authentication and self-service profile for Rental OS platform staff.

There is deliberately no public registration endpoint. Initial accounts must be
provisioned by a trusted operator through the deployment's controlled process.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, select

from app.core.config import settings
from app.core.ratelimit import login_limiter
from app.core.security import create_access_token, verify_password
from app.models.platform_admin import PlatformAdmin
from app.models.platform_admin_event import PlatformAdminEvent
from app.models.business import Business
from app.models.subscriptions import BusinessSubscription, SubscriptionInvoice, SubscriptionPayment
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
    if (not admin or not admin.is_active or len(data.password.encode("utf-8")) > 72
            or not verify_password(data.password, admin.password_hash)):
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



@router.get("/overview")
async def platform_admin_overview(admin: PlatformAdminDep, session: PlatformAdminSession):
    paid_totals = (await session.execute(
        select(SubscriptionPayment.currency, func.sum(SubscriptionPayment.amount))
        .where(SubscriptionPayment.status == "succeeded")
        .group_by(SubscriptionPayment.currency)
    )).all()
    return {
        "businesses": int(await session.scalar(select(func.count(Business.id))) or 0),
        "active_subscriptions": int(await session.scalar(select(func.count(BusinessSubscription.id)).where(BusinessSubscription.status == "active")) or 0),
        "trialing_subscriptions": int(await session.scalar(select(func.count(BusinessSubscription.id)).where(BusinessSubscription.status == "trialing")) or 0),
        "open_subscription_invoices": int(await session.scalar(select(func.count(SubscriptionInvoice.id)).where(SubscriptionInvoice.status == "open")) or 0),
        "platform_subscription_receipts": [{
            "currency": currency, "amount": str(amount or 0),
        } for currency, amount in paid_totals],
    }


@router.get("/subscriptions")
async def platform_admin_subscriptions(
    admin: PlatformAdminDep,
    session: PlatformAdminSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = (await session.execute(
        select(BusinessSubscription, Business.name, Business.slug)
        .join(Business, Business.id == BusinessSubscription.business_id)
        .order_by(desc(BusinessSubscription.created_at))
        .limit(limit).offset(offset)
    )).all()
    return {"subscriptions": [{
        "id": str(sub.id), "business_id": str(sub.business_id),
        "business_name": name, "business_slug": slug,
        "status": sub.status, "currency": sub.currency,
        "billing_interval": sub.billing_interval,
        "starts_at": sub.starts_at.isoformat() if sub.starts_at else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    } for sub, name, slug in rows], "limit": limit, "offset": offset}


@router.get("/invoices")
async def platform_admin_invoices(
    admin: PlatformAdminDep,
    session: PlatformAdminSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = (await session.execute(
        select(SubscriptionInvoice, Business.name, Business.slug)
        .join(Business, Business.id == SubscriptionInvoice.business_id)
        .order_by(desc(SubscriptionInvoice.created_at))
        .limit(limit).offset(offset)
    )).all()
    return {"invoices": [{
        "id": str(invoice.id), "invoice_number": invoice.invoice_number,
        "business_name": name, "business_slug": slug,
        "status": invoice.status, "currency": invoice.currency,
        "total": str(invoice.total),
        "due_at": invoice.due_at.isoformat() if invoice.due_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
    } for invoice, name, slug in rows], "limit": limit, "offset": offset}


@router.get("/payments")
async def platform_admin_payments(
    admin: PlatformAdminDep,
    session: PlatformAdminSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = (await session.execute(
        select(SubscriptionPayment, Business.name, Business.slug)
        .join(Business, Business.id == SubscriptionPayment.business_id)
        .order_by(desc(SubscriptionPayment.created_at))
        .limit(limit).offset(offset)
    )).all()
    return {"payments": [{
        "id": str(payment.id), "business_name": name, "business_slug": slug,
        "invoice_id": str(payment.invoice_id), "provider": payment.provider,
        "reference_suffix": payment.provider_reference[-4:],
        "status": payment.status, "currency": payment.currency,
        "amount": str(payment.amount),
        "received_at": payment.received_at.isoformat() if payment.received_at else None,
    } for payment, name, slug in rows], "limit": limit, "offset": offset}
