"""
Facebook & Instagram Bot for Rental Business Management

Handles:
- Messenger webhook: tenant inquiries, unit availability, payment reminders
- Instagram Graph API: post property listings, stories
- Cross-platform: WhatsApp ↔ Messenger ↔ Instagram

Routes:
  GET  /webhook/facebook  — webhook verification
  POST /webhook/facebook  — incoming messages
  POST /api/v1/social/post — post to Instagram/Facebook feed
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings

log = logging.getLogger("rental.facebook_bot")

router = APIRouter(tags=["social"])

FB_GRAPH = "https://graph.facebook.com/v19.0"
IG_GRAPH = "https://graph.facebook.com/v19.0"


# ─── Webhook Verification ─────────────────────────────────────────

@router.get("/webhook/facebook")
async def verify_facebook_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    if hub_mode == "subscribe" and hub_verify_token == settings.FB_WEBHOOK_SECRET:
        log.info("Facebook webhook verified")
        return int(hub_challenge) if hub_challenge else ""
    raise HTTPException(status_code=403, detail="Verification failed")


# ─── Incoming Message Handler ────────────────────────────────────

class WebhookPayload(BaseModel):
    object: str | None = None
    entry: list[dict] = []


@router.post("/webhook/facebook")
async def receive_facebook_message(payload: WebhookPayload):
    for entry in payload.entry:
        for change in entry.get("messaging", []):
            sender_id = change.get("sender", {}).get("id")
            message = change.get("message", {})

            if message.get("text"):
                text = message["text"].lower().strip()
                reply = await process_inquiry(text, sender_id)
                await send_messenger_message(sender_id, reply)

            elif message.get("attachments"):
                # Photo from tenant (e.g. maintenance issue)
                await send_messenger_message(sender_id, {
                    "text": "📸 Photo received. Our team will review and respond shortly."
                })

    return {"status": "ok"}


# ─── Rental Inquiry Processor ────────────────────────────────────

async def process_inquiry(text: str, sender_id: str) -> dict:
    """Process natural language rental inquiries."""

    # Greetings
    if any(w in text for w in ["hi", "hello", "hey", "start", "begin"]):
        return {
            "text": (
                "👋 Hello! I'm the Kimathi Apartments bot.\n\n"
                "I can help you with:\n"
                "• Available rooms — type 'rooms' or 'available'\n"
                "• Rent info — type 'rent' or 'pricing'\n"
                "• Payment — type 'pay' or 'mpesa'\n"
                "• Maintenance — type 'fix' or 'repair'\n"
                "• Visit — type 'book' or 'tour'"
            )
        }

    # Available rooms
    if any(w in text for w in ["rooms", "available", "vacant", "unit", "empty"]):
        from app.core.database import async_session_factory
        from sqlalchemy import text as sql_text
        async with async_session_factory() as s:
            rows = await s.execute(sql_text(
                "SELECT unit_number, monthly_rent FROM units "
                "WHERE status = 'vacant' AND is_deleted = false "
                "ORDER BY unit_number LIMIT 10"
            ))
            vacant = rows.fetchall()
        if vacant:
            unit_list = "\n".join(f"  • Unit {r[0]} — KES {r[1]:,}/mo" for r in vacant)
            return {
                "text": f"✅ Available Units:\n{unit_list}\n\nType 'book <unit>' to schedule a viewing."
            }
        return {"text": "📭 All units are currently occupied. Join the waitlist — type 'waitlist'."}

    # Rent info
    if any(w in text for w in ["rent", "price", "cost", "pricing", "rate"]):
        return {
            "text": (
                "💰 Rent Schedule:\n"
                "  • Standard room: KES 4,500/month\n"
                "  • All-inclusive: KES 5,500/month\n"
                "  • Security deposit: 1 month's rent\n\n"
                "Payments via M-Pesa, Bank, or Cash.\n"
                "Type 'pay' for payment instructions."
            )
        }

    # Payment
    if any(w in text for w in ["pay", "mpesa", "payment", "bill"]):
        return {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": "💳 Pay your rent via M-Pesa STK Push:",
                    "buttons": [
                        {
                            "type": "web_url",
                            "url": "https://rental.imani.co.ke/pay",
                            "title": "Pay Now",
                        },
                        {
                            "type": "phone_number",
                            "title": "Call Support",
                            "payload": "+254705364231",
                        },
                    ],
                },
            }
        }

    # Maintenance
    if any(w in text for w in ["fix", "repair", "maintenance", "broken", "leak"]):
        return {
            "text": (
                "🔧 Maintenance Request\n\n"
                "Please describe the issue and your unit number.\n"
                "Example: 'Unit K03 — leaking tap in bathroom'\n\n"
                "Our team responds within 2 hours."
            )
        }

    # Book viewing
    if any(w in text for w in ["book", "tour", "visit", "view", "schedule"]):
        return {
            "text": (
                "📅 Schedule a Viewing\n\n"
                "Available slots:\n"
                "  • Today 2:00 PM\n"
                "  • Today 4:00 PM\n"
                "  • Tomorrow 10:00 AM\n\n"
                "Reply with your preferred slot and we'll confirm."
            )
        }

    # Default
    return {
        "text": (
            "🤔 I didn't understand that.\n\n"
            "Try: rooms, rent, pay, fix, or book."
        )
    }


# ─── Messenger API ────────────────────────────────────────────────

async def send_messenger_message(recipient_id: str, message: dict):
    """Send a message via Facebook Messenger."""
    if not settings.FB_PAGE_ACCESS_TOKEN:
        log.warning("FB_PAGE_ACCESS_TOKEN not set — skipping send")
        return

    url = f"{FB_GRAPH}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": message,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                params={"access_token": settings.FB_PAGE_ACCESS_TOKEN},
                json=payload,
            )
            if resp.status_code != 200:
                log.error(f"Messenger send failed: {resp.status_code} {resp.text}")
            else:
                log.info(f"Message sent to {recipient_id}")
    except Exception as e:
        log.error(f"Messenger send error: {e}")


# ─── Instagram Graph API ─────────────────────────────────────────

class InstagramPost(BaseModel):
    caption: str
    image_url: str | None = None
    is_story: bool = False


@router.post("/api/v1/social/post")
async def post_to_instagram(post: InstagramPost):
    """Post to Instagram Feed or Story via Graph API."""
    if not settings.IG_ACCESS_TOKEN or not settings.IG_BUSINESS_ID:
        raise HTTPException(
            status_code=400,
            detail="Instagram credentials not configured. Set IG_BUSINESS_ID and IG_ACCESS_TOKEN.",
        )

    creation_id = None

    # Step 1: Create media container
    media_payload: dict[str, Any] = {
        "caption": post.caption,
        "access_token": settings.IG_ACCESS_TOKEN,
    }
    if post.image_url:
        media_payload["image_url"] = post.image_url

    media_url = f"{IG_GRAPH}/{settings.IG_BUSINESS_ID}/media"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(media_url, params=media_payload)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Instagram media creation failed: {resp.text}",
                )
            creation_id = resp.json().get("id")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Instagram API timeout")

    if not creation_id:
        raise HTTPException(status_code=502, detail="No creation_id from Instagram")

    # Step 2: Publish
    publish_url = f"{IG_GRAPH}/{settings.IG_BUSINESS_ID}/media_publish"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                publish_url,
                params={
                    "creation_id": creation_id,
                    "access_token": settings.IG_ACCESS_TOKEN,
                },
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Instagram publish failed: {resp.text}",
                )
            result = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Instagram publish timeout")

    log.info(f"Instagram post published: {result.get('id')}")
    return {
        "success": True,
        "ig_id": result.get("id"),
        "caption": post.caption,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/v1/social/instagram")
async def get_instagram_feed():
    """Fetch recent Instagram posts for the business."""
    if not settings.IG_ACCESS_TOKEN or not settings.IG_BUSINESS_ID:
        raise HTTPException(
            status_code=400,
            detail="Instagram credentials not configured.",
        )

    url = f"{IG_GRAPH}/{settings.IG_BUSINESS_ID}/media"
    params = {
        "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
        "access_token": settings.IG_ACCESS_TOKEN,
        "limit": 10,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Instagram API error: {resp.text}",
                )
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Instagram API timeout")


# ─── Payment Reminder via Messenger ──────────────────────────────

@router.post("/api/v1/social/send-reminder")
async def send_payment_reminder(recipient_id: str, amount: float, unit: str):
    """Send a payment reminder to a tenant via Messenger."""
    message = {
        "text": (
            f"💸 Payment Reminder\n\n"
            f"Unit {unit} — KES {amount:,.0f} due.\n\n"
            f"Pay via M-Pesa STK Push: https://rental.imani.co.ke/pay\n"
            f"Questions? Reply 'help'."
        )
    }
    await send_messenger_message(recipient_id, message)
    return {"status": "sent", "recipient": recipient_id}


# ─── Webhook Signature Verification ──────────────────────────────

def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Facebook webhook signature using HMAC-SHA256."""
    if not settings.FB_WEBHOOK_SECRET:
        return True  # Skip in dev mode
    expected = hmac.new(
        settings.FB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
