"""
RENTAL OS — WhatsApp Notification Providers

Two implementations of the NotificationProvider interface for WhatsApp:
  1. AfricaStalkingWhatsAppProvider — real API via Africa's Talking
  2. ConsoleWhatsAppProvider — simulated mode (logs to console)

AT WhatsApp API docs: https://build.africastalking.com/docs/wa/overview
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.notifications.providers.base import NotificationProvider


class AfricaStalkingWhatsAppProvider(NotificationProvider):
    """Africa's Talking WhatsApp Business API sender."""

    BASE_URL = "https://api.africastalking.com/version1/messaging"

    async def send(
        self,
        recipient: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        api_key = settings.AT_API_KEY
        username = settings.AT_USERNAME
        if not api_key or not username:
            return {
                "success": False,
                "provider_message_id": None,
                "error": "Africa's Talking not configured (missing AT_API_KEY or AT_USERNAME)",
            }

        formatted = self._format_phone(recipient)
        payload = {
            "username": username,
            "to": formatted,
            "message": message,
        }
        if sender_id:
            payload["from"] = sender_id

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    self.BASE_URL,
                    headers={
                        "apiKey": api_key,
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data=payload,
                )
                data = r.json()
                resp_data = data.get("SMSMessageData", {})
                recipients = resp_data.get("Recipients", [])
                if recipients:
                    first = recipients[0]
                    status = first.get("status", "Unknown")
                    msg_id = first.get("messageId")
                    success = status.upper() in ("SUCCESS", "QUEUED", "SENT")
                    return {
                        "success": success,
                        "provider_message_id": msg_id,
                        "error": None if success else f"AT status: {status}",
                    }
                return {
                    "success": False,
                    "provider_message_id": None,
                    "error": f"AT response: {data}",
                }
        except Exception as e:
            return {
                "success": False,
                "provider_message_id": None,
                "error": str(e),
            }

    @staticmethod
    def _format_phone(phone: str) -> str:
        cleaned = phone.strip().replace(" ", "").replace("-", "")
        if cleaned.startswith("0"):
            cleaned = "254" + cleaned[1:]
        elif cleaned.startswith("+"):
            cleaned = cleaned[1:]
        elif cleaned.startswith("254"):
            pass
        return cleaned


class ConsoleWhatsAppProvider(NotificationProvider):
    """Logs WhatsApp messages to console — used when AT keys absent."""

    async def send(
        self,
        recipient: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        print(f"[WHATSAPP][SIMULATED] To: {recipient}")
        print(f"[WHATSAPP][SIMULATED] From: {sender_id or 'Rental OS'}")
        print(f"[WHATSAPP][SIMULATED] Body: {message[:300]}")
        return {
            "success": True,
            "provider_message_id": None,
            "error": None,
        }
