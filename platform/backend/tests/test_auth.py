"""
Unit tests for the authentication & authorization module.

Covers:
  - JWT creation and validation
  - Bearer token extraction
  - guard_admin (the replacement for the old query-param hack)
  - AuthMiddleware path protection
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.platform.auth import (
    _create_jwt,
    _decode_jwt,
    _extract_bearer_token,
    create_admin_token,
    create_agent_key,
    guard_admin,
    require_admin_auth,
    AuthMiddleware,
)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

class TestJwtCreation:
    """JWT tokens must be round-trippable and contain the right claims."""

    def test_create_and_decode_round_trip(self):
        token = _create_jwt("user_123", role="user")
        payload = _decode_jwt(token)
        assert payload["sub"] == "user_123"
        assert payload["role"] == "user"
        assert "iat" in payload
        assert "exp" in payload

    def test_expired_token_raises(self):
        token = _create_jwt("user_123", expires_minutes=-1)  # already expired
        with pytest.raises(jwt.ExpiredSignatureError):
            _decode_jwt(token)

    def test_tampered_token_raises(self):
        token = _create_jwt("user_123")
        # flip a character in the payload section
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B") + "." + parts[2]
        with pytest.raises(jwt.PyJWTError):
            _decode_jwt(tampered)

    def test_admin_token_has_admin_role(self):
        token = create_admin_token()
        payload = _decode_jwt(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"


class TestBearerExtraction:
    """Bearer tokens must be correctly extracted from Authorization headers."""

    def test_extracts_bearer_token(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer my-token-123"}
        assert _extract_bearer_token(request) == "my-token-123"

    def test_returns_none_for_missing_header(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        assert _extract_bearer_token(request) is None

    def test_returns_none_for_non_bearer(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Basic abc123"}
        assert _extract_bearer_token(request) is None

    def test_handles_empty_bearer(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer "}
        assert _extract_bearer_token(request) == ""


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

class TestRequireAdminAuth:
    """The admin guard must reject requests without valid admin JWT."""

    @pytest.mark.anyio
    async def test_rejects_missing_token(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": ""}
        with pytest.raises(HTTPException) as exc_info:
            await require_admin_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.anyio
    async def test_rejects_non_admin_token(self):
        token = _create_jwt("user_123", role="user")
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}
        with pytest.raises(HTTPException) as exc_info:
            await require_admin_auth(request)
        assert exc_info.value.status_code == 403


class TestGuardAdmin:
    """guard_admin provides backward-compat with the old query-param approach
    while enforcing JWT for new code."""

    @pytest.mark.anyio
    async def test_accepts_valid_admin_jwt(self):
        token = create_admin_token()
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}
        request.query_params = {}
        result = await guard_admin(request)
        assert result == "admin"

    @pytest.mark.anyio
    async def test_backward_compat_query_param(self, caplog):
        """The old ?user_id=admin query param with a demo token still works but logs a warning.

        guard_admin expects a Bearer token. When the query param is used
        alone (no token), it raises 401 — the backward compat path requires
        a token field set to 'demo'.
        """
        import logging
        caplog.set_level(logging.WARNING)

        # The backward-compat path requires token == "demo" (or empty with admin user_id)
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer demo"}
        request.query_params = {"user_id": "admin"}
        result = await guard_admin(request)
        assert result == "admin"
        assert "deprecated" in caplog.text.lower()

    @pytest.mark.anyio
    async def test_rejects_invalid_user_id(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": ""}
        request.query_params = {"user_id": "hacker"}
        with pytest.raises(HTTPException) as exc_info:
            await guard_admin(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Agent key generation
# ---------------------------------------------------------------------------

class TestAgentKey:
    def test_key_has_correct_prefix(self):
        key = create_agent_key("com.test.agent@1.0.0")
        assert key.startswith("ait_")

    def test_same_agent_same_key(self):
        """Deterministic: same agent ID always produces the same key."""
        k1 = create_agent_key("com.test.agent@1.0.0")
        k2 = create_agent_key("com.test.agent@1.0.0")
        assert k1 == k2

    def test_different_agents_different_keys(self):
        k1 = create_agent_key("com.test.agent-a@1.0.0")
        k2 = create_agent_key("com.test.agent-b@1.0.0")
        assert k1 != k2


# ---------------------------------------------------------------------------
# AuthMiddleware
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    """Middleware must protect admin/user/agent prefixes while allowing public paths."""

    @pytest.fixture
    def middleware(self):
        return AuthMiddleware(app=MagicMock())

    @pytest.fixture
    def admin_token(self):
        return create_admin_token()

    @pytest.fixture
    def user_token(self):
        return _create_jwt("user_demo", role="user")

    @pytest.fixture
    def agent_token(self):
        return create_agent_key("com.test.agent@1.0.0")

    async def _make_request(self, path: str, token: str | None = None) -> Request:
        """Build a mock Starlette request."""
        request = MagicMock(spec=Request)
        request.url.path = path
        request.headers = {"Authorization": f"Bearer {token}" if token else ""}
        return request

    async def _call_middleware(self, middleware, request) -> JSONResponse | None:
        """Simulate middleware dispatch. Returns None if pass-through, JSONResponse if blocked."""
        next_fn = AsyncMock(return_value=JSONResponse({"ok": True}, status_code=200))
        result = await middleware.dispatch(request, next_fn)
        # If it's the 200 from next_fn, auth passed; otherwise check the status
        return result

    @pytest.mark.anyio
    async def test_public_paths_pass_through(self, middleware):
        for path in ["/health", "/docs", "/openapi.json"]:
            request = await self._make_request(path)
            result = await self._call_middleware(middleware, request)
            assert result.status_code == 200, f"Path {path} should be public"

    @pytest.mark.anyio
    async def test_admin_path_rejects_no_token(self, middleware):
        request = await self._make_request("/api/v1/admin/overview", token=None)
        result = await self._call_middleware(middleware, request)
        assert result.status_code == 401

    @pytest.mark.anyio
    async def test_admin_path_rejects_user_token(self, middleware, user_token):
        request = await self._make_request("/api/v1/admin/overview", token=user_token)
        result = await self._call_middleware(middleware, request)
        assert result.status_code == 403

    @pytest.mark.anyio
    async def test_admin_path_accepts_admin_token(self, middleware, admin_token):
        request = await self._make_request("/api/v1/admin/overview", token=admin_token)
        result = await self._call_middleware(middleware, request)
        assert result.status_code == 200

    @pytest.mark.anyio
    async def test_user_path_rejects_no_token(self, middleware):
        request = await self._make_request("/api/v1/billing/account", token=None)
        result = await self._call_middleware(middleware, request)
        assert result.status_code == 401

    @pytest.mark.anyio
    async def test_user_path_accepts_user_token(self, middleware, user_token):
        request = await self._make_request("/api/v1/billing/account", token=user_token)
        result = await self._call_middleware(middleware, request)
        assert result.status_code == 200

    @pytest.mark.anyio
    async def test_agent_path_accepts_agent_token(self, middleware, agent_token):
        request = await self._make_request("/api/v1/agents/register", token=agent_token)
        result = await self._call_middleware(middleware, request)
        assert result.status_code == 200

    @pytest.mark.anyio
    async def test_agent_path_rejects_user_token(self, middleware, user_token):
        request = await self._make_request("/api/v1/agents/register", token=user_token)
        result = await self._call_middleware(middleware, request)
        # Agent endpoints accept agent Bearer tokens; user JWTs are not agent tokens
        assert result.status_code == 401
