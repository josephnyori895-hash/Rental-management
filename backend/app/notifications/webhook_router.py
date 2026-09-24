"""
RENTAL OS — WhatsApp Webhook Router (Public)

This router has NO auth — called by Africa's Talking with inbound WhatsApp messages.
Must remain public. Only contains the webhook endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import SessionDep
from app.models.tenant import Tenant
from app.models.business import User
from app.notifications.service import send_notification
from sqlalchemy import select

router = APIRouter(tags=["whatsapp"])


def _format_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("0"):
        cleaned = "254" + cleaned[1:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned


@router.post("/api/v1/notifications/wa-webhook")
async def whatsapp_webhook(
    request: Request,
    session: SessionDep,
):
    """
    Africa's Talking WhatsApp webhook endpoint.
    
    AT sends: {'from': '2547...', 'text': 'BALANCE', 'id': 'ATXid...'}
    This endpoint is PUBLIC — no auth required.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    from_number = body.get("from") or body.get("phoneNumber", "")
    text = body.get("text") or body.get("content", "")
    msg_id = body.get("id") or body.get("messageId")

    if not from_number or not text:
        return {"status": "ignored", "reason": "missing from or text"}

    from app.notifications.inbound import parse_and_handle
    reply = await parse_and_handle(session, from_number, text, msg_id)

    if reply and reply.get("message"):
        business_id = None
        tenant = await session.scalar(
            select(Tenant).where(Tenant.whatsapp_phone == _format_phone(from_number), Tenant.is_deleted.is_(False)).limit(1)
        )
        if tenant:
            business_id = tenant.business_id
        else:
            user = await session.scalar(
                select(User).where(User.phone == _format_phone(from_number), User.is_active.is_(True)).limit(1)
            )
            if user:
                business_id = user.business_id

        if business_id:
            await send_notification(
                session=session, business_id=business_id, tenant_id=None,
                channel="whatsapp", recipient=reply["to"],
                template_name="wa_reply", body=reply["message"],
            )

    return {"status": "ok", "reply_sent": bool(reply)}
