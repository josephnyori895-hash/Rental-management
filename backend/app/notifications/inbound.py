"""
RENTAL OS — WhatsApp Inbound Command Handler

Receives messages from Africa's Talking webhook, parses them as commands,
and routes to the right handler.

Commands:
  Tenant:   BALANCE, PAY, RECEIPT, REPORT <msg>, RENEW, HELP
  Owner:    STATUS, COLLECTIONS, ADD <phone> <unit> <name>
  Caretaker: ADD <phone> <unit> <name>, FIXED, DONE, <meter reading>

Architecture:
  Inbound webhook → identify sender → parse command → execute → reply

Command handling is split by audience:
  - `inbound_tenant.py` — tenant commands
  - `inbound_user.py`   — owner / caretaker commands
  - this module         — sender identification + dispatch
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import User
from app.models.tenant import Tenant
from app.notifications.inbound_tenant import _handle_tenant_command
from app.notifications.inbound_user import _handle_user_command
from app.notifications.service import _format_phone


async def parse_and_handle(
    session: AsyncSession,
    from_number: str,
    message_text: str,
    message_id: str | None = None,
) -> dict:
    """
    Entry point for incoming WhatsApp messages.
    
    Returns reply payload: {'to': ..., 'message': ...} or None.
    """
    # Normalize sender phone
    sender = _format_phone(from_number)
    text = message_text.strip().upper()
    text_lower = message_text.strip()

    # ── Identify sender ──────────────────────────────────────────
    # Check if sender is a tenant
    tenant = await session.scalar(
        select(Tenant).where(Tenant.whatsapp_phone == sender, Tenant.is_deleted.is_(False)).limit(1)
    )

    # Check if sender is a user (owner/caretaker)
    user = await session.scalar(
        select(User).where(User.phone == sender, User.is_active.is_(True)).limit(1)
    )

    if tenant:
        return await _handle_tenant_command(session, tenant, text, text_lower, message_id)
    elif user:
        return await _handle_user_command(session, user, text, text_lower, sender, message_id)
    else:
        # Unknown sender — reply with info
        return {
            "to": sender,
            "message": "Welcome to Rental OS. This number is not registered. Please contact your property manager.",
        }
