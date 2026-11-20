from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token
from app.platform_admin.dependencies import get_current_platform_admin, get_current_superadmin
from app.api.deps import get_current_user


@pytest.mark.asyncio
async def test_platform_admin_token_resolves_only_platform_admin_record():
    admin = SimpleNamespace(id="8b4d7f2a-5c11-4e8f-9b5f-2a8f6d1e7c30", is_active=True)
    session = AsyncMock()
    session.get.return_value = admin
    token = create_access_token(
        str(admin.id),
        extra_claims={"type": "platform_admin_access", "principal_type": "platform_admin"},
    )

    result = await get_current_platform_admin(token=token, session=session)

    assert result is admin
    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_landlord_access_token_is_not_a_platform_admin_token():
    session = AsyncMock()
    token = create_access_token("8b4d7f2a-5c11-4e8f-9b5f-2a8f6d1e7c30")

    with pytest.raises(HTTPException) as exc:
        await get_current_platform_admin(token=token, session=session)

    assert exc.value.status_code == 401
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_business_role_claim_cannot_be_used_as_platform_admin():
    session = AsyncMock()
    token = create_access_token(
        "8b4d7f2a-5c11-4e8f-9b5f-2a8f6d1e7c30",
        extra_claims={"role": "owner", "principal_type": "business_user"},
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_platform_admin(token=token, session=session)

    assert exc.value.status_code == 401
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_platform_admin_is_rejected():
    admin = SimpleNamespace(id="8b4d7f2a-5c11-4e8f-9b5f-2a8f6d1e7c30", is_active=False)
    session = AsyncMock()
    session.get.return_value = admin
    token = create_access_token(
        str(admin.id),
        extra_claims={"type": "platform_admin_access", "principal_type": "platform_admin"},
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_platform_admin(token=token, session=session)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_platform_admin_token_is_rejected_by_landlord_authentication():
    session = AsyncMock()
    token = create_access_token(
        "8b4d7f2a-5c11-4e8f-9b5f-2a8f6d1e7c30",
        extra_claims={"type": "platform_admin_access", "principal_type": "platform_admin"},
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, session=session)

    assert exc.value.status_code == 401
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_superadmin_cannot_manage_platform_catalogue():
    admin = SimpleNamespace(is_superadmin=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_superadmin(admin=admin)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_passes_privileged_dependency():
    admin = SimpleNamespace(is_superadmin=True)
    assert await get_current_superadmin(admin=admin) is admin
