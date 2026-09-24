"""
RENTAL OS — Abstract Notification Provider

All providers (SMS, WhatsApp, Email) implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    """Abstract base for notification channels."""

    @abstractmethod
    async def send(
        self,
        recipient: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        """
        Send a message. Returns dict with:
          - success: bool
          - provider_message_id: str | None
          - error: str | None
        """
        ...
