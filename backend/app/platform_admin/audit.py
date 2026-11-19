"""Audit helpers for privileged platform operations."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_admin import PlatformAdmin
from app.models.platform_admin_event import PlatformAdminEvent


def record_platform_admin_event(
    session: AsyncSession,
    admin: PlatformAdmin,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
    request: Request | None = None,
) -> None:
    """Append an audit record; database trigger prevents later mutation/deletion."""
    # Do not trust arbitrary proxy chains; record only the direct peer address.
    peer = request.client.host if request and request.client else None
    session.add(PlatformAdminEvent(
        admin_id=admin.id,
        email_snapshot=admin.email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        event_metadata=metadata or {},
        ip_address=peer,
        user_agent=request.headers.get("user-agent", "")[:512] if request else None,
    ))
