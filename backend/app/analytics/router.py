"""
RENTAL OS — Analytics Router

AI-powered insights for the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.analytics.service import get_insights
from app.api.deps import SessionDep, get_current_business
from app.models.business import Business

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/insights")
async def analytics_insights(
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    """Get AI-powered business insights and predictions."""
    return await get_insights(session, business.id)
