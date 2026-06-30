"""
Rate-limiting middleware using a sliding-window token-bucket algorithm.

Fixes the gap where ``config.settings.rate_limit_requests_per_minute`` was
defined but never enforced, leaving the API open to abuse.

Implementation uses an in-process token bucket per IP address.
For multi-process deployments, swap the store for Redis.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings

logger = logging.getLogger(__name__)

# ── Sliding-window buckets ────────────────────────────────────────────
#   bucket_key → list[float]  (list of timestamps in the current window)
#   Auto-cleaned every CLEANUP_INTERVAL accesses.

_WINDOW_SECONDS: float = settings.rate_limit_window
_CLEANUP_INTERVAL: int = settings.rate_limit_cleanup_interval
_buckets: dict[str, list[float]] = defaultdict(list)
_access_count: int = 0
_MAX_BUCKETS: int = settings.rate_limit_max_buckets


def _check_rate_limit(key: str, max_requests: int) -> bool:
    """Return True if the request is allowed, False if rate-limited.

    Uses a sliding-window: timestamps older than ``_WINDOW_SECONDS`` are
    evicted on each check.
    """
    global _access_count

    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    bucket = _buckets[key]

    # Evict stale entries
    while bucket and bucket[0] < window_start:
        bucket.pop(0)

    if len(bucket) >= max_requests:
        return False

    bucket.append(now)

    # Periodic cleanup of idle buckets to bound memory
    _access_count += 1
    if _access_count >= _CLEANUP_INTERVAL:
        _access_count = 0
        _purge_stale_buckets(now)

    # Safety cap: if we have too many tracked IPs, evict least recently used
    if len(_buckets) > _MAX_BUCKETS:
        _evict_lru()

    return True


def _purge_stale_buckets(now: float) -> None:
    """Remove buckets that have had no activity in the last window."""
    cutoff = now - _WINDOW_SECONDS
    stale = [
        k for k, v in _buckets.items()
        if not v or v[-1] < cutoff
    ]
    for k in stale:
        del _buckets[k]


def _evict_lru() -> None:
    """Drop the least-recently-used bucket to stay under memory cap."""
    if not _buckets:
        return
    lru_key = min(_buckets, key=lambda k: _buckets[k][-1] if _buckets[k] else 0)
    del _buckets[lru_key]


def _client_key(request: Request) -> str:
    """Derive a rate-limit key from the client.

    Prefers X-Forwarded-For (for reverse-proxy setups), falls back to
    the direct client IP.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    host = request.client.host if request.client else "unknown"
    return host


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter.

    Configuration (from :mod:`config.settings`):
      - ``rate_limit_requests_per_minute`` — max requests per window (default 60)

    Skips rate-limiting for these paths:
      - ``/health``
      - ``/docs``, ``/openapi.json``, ``/redoc``
    """

    SKIP_PREFIXES: tuple[str, ...] = ("/docs", "/openapi.json", "/redoc")
    SKIP_PATHS: set[str] = {"/health"}

    def __init__(self, app, max_requests: int | None = None):
        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_requests_per_minute

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        path = request.url.path

        # Skip rate-limiting for health/docs
        if path in self.SKIP_PATHS or path.startswith(self.SKIP_PREFIXES):
            return await call_next(request)

        key = _client_key(request)

        if not _check_rate_limit(key, self.max_requests):
            logger.warning("Rate limit exceeded for %s (path=%s)", key, path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests",
                    "detail": f"Limit: {self.max_requests} requests per minute",
                    "code": "RATE_LIMITED",
                    "retry_after_seconds": int(_WINDOW_SECONDS),
                },
                headers={"Retry-After": str(int(_WINDOW_SECONDS))},
            )

        return await call_next(request)
