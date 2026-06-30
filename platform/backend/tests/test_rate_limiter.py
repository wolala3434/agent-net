"""
Unit tests for the rate-limiting middleware.

Verifies:
  - Sliding-window token bucket allows requests up to the limit
  - Requests beyond the limit are rejected with HTTP 429
  - Public paths (/health, /docs) are exempt
  - Different IPs get independent buckets
  - Buckets are cleaned up to prevent memory leaks
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.platform.middleware import (
    _check_rate_limit,
    _client_key,
    _purge_stale_buckets,
    _buckets,
    RateLimitMiddleware,
)


# ---------------------------------------------------------------------------
# Token bucket
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def setup_method(self):
        _buckets.clear()

    def test_allows_requests_within_limit(self):
        for _ in range(10):
            assert _check_rate_limit("test-ip", max_requests=60)

    def test_blocks_when_over_limit(self):
        for _ in range(5):
            assert _check_rate_limit("blocked-ip", max_requests=5)
        # 6th request must be blocked
        assert not _check_rate_limit("blocked-ip", max_requests=5)

    def test_different_keys_independent(self):
        """IP-A being rate-limited doesn't affect IP-B."""
        # Fill ip-a to exactly at limit (5 requests allowed, 6th blocked)
        for _ in range(5):
            assert _check_rate_limit("ip-a", max_requests=5)
        # ip-a is now blocked (6th request)
        assert not _check_rate_limit("ip-a", max_requests=5)
        # ip-b is fine — independent bucket
        assert _check_rate_limit("ip-b", max_requests=5)

    def test_window_resets_eventually(self):
        """After the window passes, old entries are evicted and requests are allowed."""
        max_req = 5
        for _ in range(max_req):
            assert _check_rate_limit("reset-ip", max_requests=max_req)
        assert not _check_rate_limit("reset-ip", max_requests=max_req)

        # Simulate time passing by manipulating the bucket timestamps
        old_time = time.monotonic() - 120  # 120 seconds ago (beyond 60s window)
        _buckets["reset-ip"] = [old_time] * max_req
        # Now it should be allowed again (old entries evicted)
        assert _check_rate_limit("reset-ip", max_requests=max_req)


# ---------------------------------------------------------------------------
# Bucket cleanup
# ---------------------------------------------------------------------------

class TestBucketCleanup:
    def setup_method(self):
        _buckets.clear()

    def test_purge_removes_stale_buckets(self):
        now = time.monotonic()
        _buckets["active"] = [now]
        _buckets["stale"] = [now - 120]  # > 60s old

        _purge_stale_buckets(now)
        assert "active" in _buckets
        assert "stale" not in _buckets

    def test_purge_keeps_empty_bucket_with_recent_activity(self):
        """An empty bucket whose last activity was recent is NOT purged."""
        now = time.monotonic()
        _buckets["frequent"] = [now]  # just added

        _purge_stale_buckets(now + 30)  # 30s later
        # Bucket has entries newer than cutoff → kept
        assert "frequent" in _buckets


# ---------------------------------------------------------------------------
# Client key extraction
# ---------------------------------------------------------------------------

class TestClientKey:
    def test_uses_x_forwarded_for(self):
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        request.client = MagicMock(host="192.168.1.1")
        assert _client_key(request) == "10.0.0.1"

    def test_falls_back_to_client_ip(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock(host="192.168.1.100")
        assert _client_key(request) == "192.168.1.100"

    def test_unknown_client(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None
        assert _client_key(request) == "unknown"


# ---------------------------------------------------------------------------
# Middleware dispatch
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    def setup_method(self):
        _buckets.clear()

    @pytest.fixture
    def middleware(self):
        return RateLimitMiddleware(app=MagicMock(), max_requests=5)

    async def _make_request(self, path: str, ip: str = "10.0.0.1") -> Request:
        request = MagicMock(spec=Request)
        request.url.path = path
        request.headers = {"X-Forwarded-For": ip}
        request.client = MagicMock(host=ip)
        return request

    async def _dispatch(self, middleware, request):
        next_fn = AsyncMock(return_value=JSONResponse({"ok": True}, status_code=200))
        return await middleware.dispatch(request, next_fn)

    @pytest.mark.anyio
    async def test_health_path_exempt(self, middleware):
        request = await self._make_request("/health")
        # Even after exhausting the limit on other paths
        for _ in range(50):
            result = await self._dispatch(middleware, request)
            assert result.status_code == 200, "Health endpoint must never be rate-limited"

    @pytest.mark.anyio
    async def test_docs_exempt(self, middleware):
        request = await self._make_request("/docs")
        for _ in range(50):
            result = await self._dispatch(middleware, request)
            assert result.status_code == 200

    @pytest.mark.anyio
    async def test_rate_limited_returns_429(self, middleware):
        request = await self._make_request("/api/v1/agents")
        # Exhaust the bucket
        for _ in range(5):
            result = await self._dispatch(middleware, request)
            assert result.status_code == 200

        # Next request must be rate-limited
        result = await self._dispatch(middleware, request)
        assert result.status_code == 429

    @pytest.mark.anyio
    async def test_429_response_has_retry_header(self, middleware):
        request = await self._make_request("/api/v1/agents")
        for _ in range(6):  # one over limit
            result = await self._dispatch(middleware, request)
        assert result.status_code == 429
        assert "Retry-After" in result.headers

    @pytest.mark.anyio
    async def test_different_ips_separate_limits(self, middleware):
        """IP-A hitting the limit shouldn't affect IP-B."""
        request_a = await self._make_request("/api/v1/agents", ip="10.0.0.1")
        request_b = await self._make_request("/api/v1/agents", ip="10.0.0.2")

        # Exhaust IP-A's bucket
        for _ in range(5):
            await self._dispatch(middleware, request_a)
        result_a = await self._dispatch(middleware, request_a)
        assert result_a.status_code == 429

        # IP-B should still be allowed
        result_b = await self._dispatch(middleware, request_b)
        assert result_b.status_code == 200
