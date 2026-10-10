"""App-level smoke tests that need no database."""

from __future__ import annotations

import httpx

from app.main import app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def test_health_endpoint():
    async with _client() as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "up"
    assert "version" in body and "uptime" in body


async def test_api_info_endpoint():
    """Metadata lives under the API prefix, where the SPA cannot occupy it.

    `/` belongs to the built frontend once one is deployed, so asserting on the
    root would make this suite depend on whether a build happens to be present.
    """
    async with _client() as client:
        response = await client.get("/api/v1/info")
    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "/api/v1"
    assert body["name"] and body["version"]


def test_the_spa_is_mounted_only_when_asked_for_and_built(monkeypatch):
    """The frontend mount is explicit, so tests and API-only deploys are stable."""
    from app.core.config import settings
    from app.main import create_app

    def catch_all_present() -> bool:
        return "/{full_path:path}" in {
            getattr(route, "path", "") for route in create_app().routes
        }

    monkeypatch.setattr(settings, "SERVE_FRONTEND", False)
    assert not catch_all_present(), "SERVE_FRONTEND=false must leave the API alone"

    monkeypatch.setattr(settings, "SERVE_FRONTEND", True)
    from app.main import _frontend_built

    assert catch_all_present() is _frontend_built()


async def test_an_unknown_api_path_is_never_the_spa(monkeypatch):
    """A bad API path must 404, not hand a client a page of HTML."""
    from app.core.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "SERVE_FRONTEND", True)
    app_with_spa = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_with_spa), base_url="http://test"
    ) as client:
        for path in ("/api/v1/nope", "/api", "/health/nope"):
            response = await client.get(path)
            assert response.status_code == 404, path
            assert "text/html" not in response.headers.get("content-type", ""), path


async def test_unknown_route_is_404():
    async with _client() as client:
        response = await client.get("/api/v1/definitely-not-a-route")
    assert response.status_code == 404


async def test_protected_route_requires_a_token():
    async with _client() as client:
        response = await client.get("/api/v1/properties")
    assert response.status_code == 401


async def test_protected_route_rejects_garbage_token():
    async with _client() as client:
        response = await client.get(
            "/api/v1/properties", headers={"Authorization": "Bearer not.a.jwt"}
        )
    assert response.status_code == 401


def test_money_moving_routes_are_rate_limited():
    """
    Regression: payment_limiter and callback_limiter were defined but never
    attached, leaving the unauthenticated M-PESA callback unthrottled.
    """
    from app.core.ratelimit import RateLimiter
    from app.payments.router import callback_router, router

    checked = {
        "/payments/mpesa/stk",
        "/payments/mpesa/stk-direct",
        "/payments/record",
        "/payments/simulate",
        "/payments/mpesa/callback",
    }
    guarded = {
        route.path
        for route in list(router.routes) + list(callback_router.routes)
        if any(isinstance(dep.dependency, RateLimiter) for dep in route.dependencies)
    }
    assert checked <= guarded, f"missing rate limiter on {checked - guarded}"


def test_openapi_schema_builds():
    """Guards against duplicate operation ids / broken response models."""
    spec = app.openapi()
    assert len(spec["paths"]) > 50
