"""
Lightweight rate limiting for IMANI (P0-1 Security Hardening).

In-process fixed-window limiter, dependency-injectable into FastAPI routes.
No external service required (single-instance launch safe). For multi-worker
deployments, swap the store for Redis — the interface is intentionally small.

Usage:
    limiter = RateLimiter(times=20, seconds=60)
    @router.post("/x", dependencies=[Depends(limiter)])
    async def x(): ...
"""

import time
from collections import defaultdict, deque
from typing import Dict, Deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


class RateLimiter:
    """
    Fixed-window rate limiter keyed by (client IP + route path).

    Args:
        times: Maximum number of requests allowed within the window.
        seconds: Window length in seconds.
    """

    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._window = seconds

    def _client_key(self, request: Request) -> str:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            ip = fwd.split(",")[0].strip()
        elif request.client is not None:
            ip = request.client.host
        else:
            ip = "unknown"
        # Scope per-route so one hot endpoint can't starve others.
        return f"{ip}:{request.url.path}"

    async def __call__(self, request: Request) -> bool:
        key = self._client_key(request)
        now = time.monotonic()
        cutoff = now - self._window

        dq = self._hits[key]
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Slow down and retry shortly.",
                headers={"Retry-After": str(self._window)},
            )

        dq.append(now)
        return True


# ── Shared limiters ──────────────────────────────────────────────
# Limits come from config (RATE_LIMIT_*), which was previously declared but
# ignored in favour of the literals below.
login_limiter = RateLimiter(
    times=settings.RATE_LIMIT_LOGIN_PER_MINUTE, seconds=60
)                                                        # brute-force protection
payment_limiter = RateLimiter(
    times=settings.RATE_LIMIT_PER_MINUTE, seconds=60
)                                                        # money-movement protection
callback_limiter = RateLimiter(
    times=settings.RATE_LIMIT_PER_MINUTE * 2, seconds=60
)                                                        # Safaricom retries
