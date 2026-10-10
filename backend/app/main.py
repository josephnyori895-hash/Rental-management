"""
Rental OS — Application Entry Point
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import require_owner
from app.api.errors import register_error_handlers
from app.auth.router import router as auth_router
from app.core.config import settings
from app.dashboard.router import router as dashboard_router
from app.payments.router import callback_router as mpesa_callback_router
from app.payments.router import router as payments_router
from app.billing.router import router as billing_router
from app.billing.utilities_router import router as utilities_router
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


# The built frontend, when one has been produced (`npm run build`).
#
# The product is written same-origin: `frontend/src/lib/api.ts` fetches
# relative `/api/...` paths and Vite proxies them during development. So in
# production the API serves the SPA itself rather than a second service. One
# origin means no CORS configuration to get wrong, no build-time API URL to
# keep in sync, and the whole product runs as a single free instance.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# Paths that must never fall through to the SPA. An unknown API path has to be
# a 404 — returning index.html instead would hand a client a page of HTML to
# parse as JSON.
RESERVED_SEGMENTS = {"api", "docs", "redoc", "openapi.json", "health", "storage"}


def _frontend_built() -> bool:
    """Whether a production frontend build is present on disk."""
    return (FRONTEND_DIST / "index.html").is_file()


def _mount_frontend(app: FastAPI) -> bool:
    """Serve the built SPA, with client-side routing fallback.

    Call this *after* every router is registered: routes match in registration
    order, so the catch-all would otherwise shadow the entire API. Returns
    whether a build was mounted — with none, the caller keeps its JSON root and
    the API still starts on its own, which is what keeps the test suite and the
    Tauri dev loop working without a frontend build.
    """
    if not settings.SERVE_FRONTEND:
        return False

    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        return False

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    build_root = FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        normalised = full_path.strip("/")
        if normalised.split("/", 1)[0] in RESERVED_SEGMENTS:
            raise HTTPException(status_code=404, detail="Not found")

        # A real file, when one exists — guarded so that a crafted path cannot
        # escape the build directory.
        if normalised:
            candidate = (FRONTEND_DIST / normalised).resolve()
            if candidate.is_file() and build_root in candidate.parents:
                return FileResponse(candidate)
        return FileResponse(index)

    return True


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
    app.include_router(utilities_router, prefix=api, dependencies=owner_only)
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

    @app.get(f"{api}/info", tags=["System"])
    async def api_info():
        """API metadata at a path the SPA can never occupy.

        `/` belongs to the frontend whenever a build is deployed, so this is
        the stable thing for clients and health tooling to read.
        """
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "api": api,
            "frontend_served": bool(settings.SERVE_FRONTEND and _frontend_built()),
        }

    # After every API route, so only unmatched paths can reach the SPA — and
    # before the JSON root, because the SPA owns `/` when a build exists.
    if not _mount_frontend(app):
        @app.get("/", tags=["System"])
        async def root():
            return {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "api": api,
            }

    return app


START_TIME = time.time()
app = create_app()
