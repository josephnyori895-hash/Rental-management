"""Notification providers — pluggable senders."""

from app.notifications.providers.base import NotificationProvider
from app.notifications.providers.africastalking import AfricaStalkingProvider
from app.notifications.providers.console import ConsoleProvider
from app.notifications.providers.whatsapp import (
    AfricaStalkingWhatsAppProvider,
    ConsoleWhatsAppProvider,
)

__all__ = [
    "NotificationProvider",
    "AfricaStalkingProvider",
    "ConsoleProvider",
    "AfricaStalkingWhatsAppProvider",
    "ConsoleWhatsAppProvider",
]
