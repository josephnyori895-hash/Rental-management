"""Rate limiter behaviour and its wiring to config."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.ratelimit import RateLimiter, login_limiter, payment_limiter


class FakeRequest:
    """Minimal stand-in for starlette's Request."""

    def __init__(self, path="/api/v1/x", ip="1.2.3.4", forwarded=None):
        self.headers = {"X-Forwarded-For": forwarded} if forwarded else {}
        self.client = type("Client", (), {"host": ip})()
        self.url = type("URL", (), {"path": path})()


async def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(times=3, seconds=60)
    for _ in range(3):
        assert await limiter(FakeRequest()) is True
    with pytest.raises(HTTPException) as exc:
        await limiter(FakeRequest())
    assert exc.value.status_code == 429


async def test_blocked_response_tells_client_when_to_retry():
    limiter = RateLimiter(times=1, seconds=60)
    await limiter(FakeRequest())
    with pytest.raises(HTTPException) as exc:
        await limiter(FakeRequest())
    assert exc.value.headers["Retry-After"] == "60"


async def test_limit_is_scoped_per_path():
    limiter = RateLimiter(times=1, seconds=60)
    await limiter(FakeRequest(path="/a"))
    # A different route must not be starved by the first one's quota.
    assert await limiter(FakeRequest(path="/b")) is True


async def test_limit_is_scoped_per_client():
    limiter = RateLimiter(times=1, seconds=60)
    await limiter(FakeRequest(ip="10.0.0.1"))
    assert await limiter(FakeRequest(ip="10.0.0.2")) is True


async def test_forwarded_for_is_used_when_present():
    limiter = RateLimiter(times=1, seconds=60)
    await limiter(FakeRequest(ip="10.0.0.1", forwarded="9.9.9.9"))
    # Same proxy IP but a different forwarded client counts separately.
    assert await limiter(FakeRequest(ip="10.0.0.1", forwarded="8.8.8.8")) is True


async def test_window_expiry_allows_new_requests():
    limiter = RateLimiter(times=1, seconds=0)
    await limiter(FakeRequest())
    # A zero-length window means nothing is retained once time advances.
    assert await limiter(FakeRequest()) is True


def test_login_limiter_uses_config():
    """Regression: RATE_LIMIT_* were declared but the literals were hardcoded."""
    assert login_limiter.times == settings.RATE_LIMIT_LOGIN_PER_MINUTE
    assert payment_limiter.times == settings.RATE_LIMIT_PER_MINUTE
