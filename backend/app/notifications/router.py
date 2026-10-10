"""
RENTAL OS — Notifications Router

Endpoints for sending messages, viewing notification logs, and managing
provider configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_business
from app.core.config import settings
from app.models.business import Business
from app.notifications.models import NotificationLog
from app.notifications.service import (
    process_due_reminders,
    send_notification,
)
from app.models.tenant import Tenant
from app.models.business import User
from sqlalchemy import select, func

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SendNotificationRequest(BaseModel):
    tenant_id: str
    channel: str = "sms"  # sms | whatsapp
    template_name: str = "custom"  # rent_reminder | payment_receipt | lease_expiry | custom
    message: str
    phone: str | None = None


class NotificationSettingsResponse(BaseModel):
    sms_provider: str
    sms_provider_configured: bool
    sms_sender_id: str
    whatsapp_provider: str
    whatsapp_provider_configured: bool
    default_channel: str
    daily_reminders_enabled: bool


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings():
    """Return current SMS + WhatsApp provider configuration status."""
    at_configured = bool(settings.AT_API_KEY and settings.AT_USERNAME)
    wa_configured = bool(settings.AT_API_KEY and settings.AT_USERNAME and settings.AT_WHATSAPP_NUMBER)
    return {
        "sms_provider": "africastalking" if at_configured else "console",
        "sms_provider_configured": at_configured,
        "sms_sender_id": settings.AT_SENDER_ID or "Rental OS",
        "whatsapp_provider": "africastalking" if wa_configured else "console",
        "whatsapp_provider_configured": wa_configured,
        "default_channel": "whatsapp" if wa_configured else "sms",
        "daily_reminders_enabled": True,
    }


class EnrollmentConfigRequest(BaseModel):
    require_deposit: bool = True
    deposit_type: str = "one_month"  # one_month | two_months | fixed
    deposit_fixed_amount: float | None = None
    require_first_rent: bool = True
    allow_partial: bool = False
    grace_hours: int = 24


@router.get("/enrollment-config")
async def get_enrollment_config(
    business: Business = Depends(get_current_business),
):
    """Get enrollment payment requirements for this business."""
    cfg = (business.settings or {}).get("enrollment", {})
    return {
        "require_deposit": cfg.get("require_deposit", True),
        "deposit_type": cfg.get("deposit_type", "one_month"),
        "deposit_fixed_amount": cfg.get("deposit_fixed_amount"),
        "require_first_rent": cfg.get("require_first_rent", True),
        "allow_partial": cfg.get("allow_partial", False),
        "grace_hours": cfg.get("grace_hours", 24),
    }


@router.put("/enrollment-config")
async def update_enrollment_config(
    data: EnrollmentConfigRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Update enrollment payment requirements."""
    settings_json = dict(business.settings or {})
    settings_json["enrollment"] = data.model_dump()
    business.settings = settings_json
    session.add(business)
    await session.commit()
    return {"status": "ok", "enrollment": data.model_dump()}


class BusinessConfigRequest(BaseModel):
    business_name: str
    kra_pin: str | None = None
    mpesa_paybill: str | None = None
    county: str | None = None
    rent_due_day: int = 5
    payment_method: str = "mpesa"  # mpesa | bank
    bank_name: str | None = None
    bank_account: str | None = None
    bank_account_name: str | None = None


@router.get("/business-config")
async def get_business_config(
    business: Business = Depends(get_current_business),
):
    """Get general business and payment configurations."""
    cfg = (business.settings or {}).get("business", {})
    return {
        "business_name": cfg.get("business_name", business.name),
        "kra_pin": cfg.get("kra_pin", "P051234567K"),
        "mpesa_paybill": cfg.get("mpesa_paybill", business.mpesa_shortcode or "400200"),
        "county": cfg.get("county", "Nairobi"),
        "rent_due_day": cfg.get("rent_due_day", 5),
        "payment_method": cfg.get("payment_method", "mpesa"),
        "bank_name": cfg.get("bank_name", "Equity Bank"),
        "bank_account": cfg.get("bank_account", "1220123456789"),
        "bank_account_name": cfg.get("bank_account_name", business.name),
    }


@router.put("/business-config")
async def update_business_config(
    data: BusinessConfigRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Update general business details and payment options."""
    settings_json = dict(business.settings or {})
    settings_json["business"] = data.model_dump()
    business.name = data.business_name
    business.settings = settings_json
    session.add(business)
    await session.commit()
    return {"status": "ok", "business": data.model_dump()}


@router.post("/send")
async def send_custom_notification(
    data: SendNotificationRequest,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Manually send an SMS notification to a tenant."""
    from app.models.tenant import Tenant

    tenant = await session.get(Tenant, data.tenant_id)
    if not tenant or tenant.business_id != business.id:
        raise HTTPException(status_code=404, detail="Tenant not found")

    phone = data.phone or tenant.mpesa_phone or tenant.phone
    if not phone:
        raise HTTPException(status_code=400, detail="Tenant has no phone number")

    log = await send_notification(
        session=session,
        business_id=business.id,
        tenant_id=tenant.id,
        channel=data.channel,
        recipient=phone,
        template_name=data.template_name,
        body=data.message,
        sender_id=settings.AT_SENDER_ID or None,
    )

    return {
        "id": str(log.id),
        "status": log.status,
        "recipient": log.recipient,
        "sent_at": str(log.sent_at) if log.sent_at else None,
        "error": log.error,
    }


@router.post("/process-reminders")
async def trigger_reminders(
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Manually trigger the rent reminder sweep for all unpaid tenants."""
    sent = await process_due_reminders(session, business.id)
    return {"reminders_sent": sent, "business_id": str(business.id)}


@router.get("/log")
async def get_notification_log(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, pattern="^(sent|failed|simulated)$"),
):
    """View notification history for the business."""
    q = select(NotificationLog).where(
        NotificationLog.business_id == business.id
    )
    if status:
        q = q.where(NotificationLog.status == status)
    q = q.order_by(NotificationLog.created_at.desc()).offset(offset).limit(limit)

    logs = (await session.scalars(q)).all()
    total = await session.scalar(
        select(func.count(NotificationLog.id)).where(
            NotificationLog.business_id == business.id,
            *(NotificationLog.status == status if status else []),
        )
    )

    return {
        "total": total or 0,
        "notifications": [
            {
                "id": str(log.id),
                "channel": log.channel,
                "recipient": log.recipient,
                "template_name": log.template_name,
                "body": log.body,
                "status": log.status,
                "provider": log.provider,
                "error": log.error,
                "sent_at": str(log.sent_at) if log.sent_at else None,
                "created_at": str(log.created_at) if log.created_at else str(log.created_at),
            }
            for log in logs
        ],
    }



