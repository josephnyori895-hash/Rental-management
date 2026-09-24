"""
RENTAL OS — Console Notification Provider

Simulates sending by printing to the server log.
Used in development / demo mode when no API credentials are configured.
"""

from __future__ import annotations

from app.notifications.providers.base import NotificationProvider


class ConsoleProvider(NotificationProvider):
    """Logs messages to console instead of sending them."""

    async def send(
        self,
        recipient: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        print(f"[NOTIFICATION][SIMULATED] To: {recipient}")
        print(f"[NOTIFICATION][SIMULATED] From: {sender_id or 'Rental OS'}")
        print(f"[NOTIFICATION][SIMULATED] Body: {message[:200]}")
        return {
            "success": True,
            "provider_message_id": None,
            "error": None,
        }
