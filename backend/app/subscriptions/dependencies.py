"""Reusable backend entitlement dependency for paid/optional product features."""
from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import SessionDep, get_current_business
from app.models.business import Business
from app.subscriptions.service import get_entitlements


def require_feature(feature: str):
    """Reject access unless the authenticated business has this entitlement.

    Apply this dependency to the backend route that performs the protected
    operation. Hiding a frontend control is never an authorization boundary.
    """
    async def _check(
        session: SessionDep,
        business: Business = Depends(get_current_business),
    ) -> dict:
        entitlements = await get_entitlements(session, business.id)
        if not bool(entitlements.get(feature, False)):
            raise HTTPException(
                status_code=403,
                detail={"code": "FEATURE_NOT_INCLUDED", "feature": feature},
            )
        return entitlements

    return _check
