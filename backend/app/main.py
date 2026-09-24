"""
Rental OS — Application Entry Point
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import require_owner
from app.api.errors import register_error_handlers
from app.auth.router import router as auth_router
from app.core.config import settings
from app.dashboard.router import router as dashboard_router
from app.payments.router import callback_router as mpesa_callback_router
from app.payments.router import router as payments_router
from app.billing.router import router as billing_router
from app.properties.router import router as properties_router
from app.tenants.router import router as tenants_router
from app.maintenance.router import router as maintenance_router
from app.expenses.router import router as expenses_router
from app.reports.router import router as reports_router
from app.accounting.router import router as accounting_router
from app.portal.router import router as portal_router
from app.notifications.router import router as notifications_router
from app.notifications.webhook_router import router as whatsapp_webhook_router
from app.documents.router import router as documents_router
from app.reconciliation.router import router as reconciliation_router
from app.analytics.router import router as analytics_router
from app.social.bot import router as social_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"  Environment: {settings.ENVIRONMENT}")
    print(f"  Database: {str(settings.DATABASE_URL).split('@')[1]}")
    yield
    from app.core.database import close_db

    await close_db()
    print("  Database connections closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Rental OS — hostel/property management with M-Pesa payments and an owner business console",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    api = settings.API_PREFIX
    owner_only = [Depends(require_owner)]

    # Public routes (no auth — login, external webhooks)
    app.include_router(auth_router, prefix=api)
    app.include_router(mpesa_callback_router, prefix=api)
    app.include_router(whatsapp_webhook_router)
    app.include_router(social_router)

    # Owner-only web dashboard routes
    app.include_router(properties_router, prefix=api, dependencies=owner_only)
    app.include_router(tenants_router, prefix=api, dependencies=owner_only)
    app.include_router(dashboard_router, prefix=api, dependencies=owner_only)
    app.include_router(payments_router, prefix=api, dependencies=owner_only)
    app.include_router(billing_router, prefix=api, dependencies=owner_only)
    app.include_router(maintenance_router, prefix=api, dependencies=owner_only)
    app.include_router(expenses_router, prefix=api, dependencies=owner_only)
    app.include_router(reports_router, prefix=api, dependencies=owner_only)
    app.include_router(accounting_router, prefix=api, dependencies=owner_only)
    app.include_router(portal_router, prefix=api, dependencies=owner_only)
    app.include_router(notifications_router, prefix=api, dependencies=owner_only)
    app.include_router(documents_router, prefix=api, dependencies=owner_only)
    app.include_router(reconciliation_router, prefix=api, dependencies=owner_only)
    app.include_router(analytics_router, prefix=api, dependencies=owner_only)

    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "status": "up",
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": round(time.time() - START_TIME, 3),
        }

    @app.get("/", tags=["System"])
    async def root():
        return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs", "api": api}

    return app


START_TIME = time.time()
app = create_app()
