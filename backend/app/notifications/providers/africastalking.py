"""
RENTAL OS — Africa's Talking SMS Provider

Sends SMS via Africa's Talking REST API (the most popular SMS gateway in Kenya).

API docs: https://build.africastalking.com/docs/sms/sending
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.notifications.providers.base import NotificationProvider


class AfricaStalkingProvider(NotificationProvider):
    """Africa's Talking SMS gateway."""

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
                    cost = first.get("cost", "0")
                    success = status.upper() in ("SUCCESS", "QUEUED", "SENT")
                    return {
                        "success": success,
                        "provider_message_id": msg_id,
                        "error": None if success else f"AT status: {status}",
                        "cost": cost,
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
        """Normalize to international format: 2547XXXXXXXX."""
        cleaned = phone.strip().replace(" ", "").replace("-", "")
        if cleaned.startswith("0"):
            cleaned = "254" + cleaned[1:]
        elif cleaned.startswith("+"):
            cleaned = cleaned[1:]
        elif cleaned.startswith("254"):
            pass
        return cleaned
