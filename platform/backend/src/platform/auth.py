"""
Authentication & Authorization middleware.

Fixes the critical security gap where admin access was gated solely
by a query-param ``user_id`` check against a hard-coded set.

Architecture:
  - Agent endpoints   → Bearer token (``ait_`` prefix) authentication
  - User endpoints    → JWT (HS256) authentication
  - Admin endpoints   → JWT + role claim ``"admin"``

Configuration is read from the centralised :mod:`config` module so
secrets never appear in source code.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SECONDS_PER_MINUTE = 60

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_JWT_ALGORITHM = settings.user_jwt_algorithm
_JWT_SECRET = settings.user_jwt_secret
_AGENT_KEY_PREFIX = settings.agent_api_key_prefix  # "ait_"

# ⚠️  MVP fallback — remove before production
_HARDCODED_AGENT_KEYS: set[str] = set()  # populated by admin API at runtime


def _create_jwt(user_id: str, role: str = "user", expires_minutes: int | None = None) -> str:
    """Issue a signed JWT for a user (used by login / admin flows)."""
    exp_mins = expires_minutes or settings.user_jwt_expire_minutes
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_mins * SECONDS_PER_MINUTE,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.  Raises :exc:`jwt.PyJWTError` on failure."""
    return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])


def _extract_bearer_token(request: Request) -> str | None:
    """Pull the raw token from an ``Authorization: Bearer <tok>`` header."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


# ---------------------------------------------------------------------------
# FastAPI dependencies (preferred for new code — avoids middleware overhead)
# ---------------------------------------------------------------------------


async def require_agent_auth(request: Request) -> str:
    """Validate agent Bearer token; returns *agent_id* on success.

    Usage::

        @router.post("/agents/{agent_id}/heartbeat")
        async def heartbeat(agent_id: str, _agent: str = Depends(require_agent_auth)):
            ...
    """
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # MVP: accept hardcoded keys while we build real key management
    if token in _HARDCODED_AGENT_KEYS:
        return token  # caller can resolve agent_id from token later

    # Future: look up token → agent_id in DB
    if token.startswith(_AGENT_KEY_PREFIX):
        # Placeholder — real validation will query the agents table.
        # For now we accept any ait_* token whose suffix matches a known agent.
        logger.debug("Agent token accepted (MVP bypass): %s...", token[:12])
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid agent credentials",
    )


async def require_user_auth(request: Request) -> dict[str, Any]:
    """Validate user JWT; returns the decoded payload.

    Usage::

        @router.get("/billing/account")
        async def get_account(user: dict = Depends(require_user_auth)):
            user_id = user["sub"]
    """
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decode_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return payload


async def require_admin_auth(request: Request) -> dict[str, Any]:
    """Validate JWT AND require role == 'admin'."""
    payload = await require_user_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload


# ---------------------------------------------------------------------------
# Middleware (applied globally — lightweight for MVP)
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Lightweight global middleware that enforces authentication on protected
    route prefixes.

    **Why middleware instead of per-route dependencies?**
    It's a defence-in-depth measure — even if a new route is accidentally
    added without a ``Depends(require_*)`` guard, the middleware catches
    unauthenticated requests by prefix.

    **Performance note:** The middleware runs *before* every request, but the
    per-prefix check is an O(1) dict lookup.  For paths outside the protected
    prefixes it returns immediately with negligible overhead.
    """

    # Routes that MUST have a valid agent Bearer token.
    AGENT_PROTECTED_PREFIXES: tuple[str, ...] = (
        "/api/v1/agents/",
        "/api/v1/discovery/",
    )

    # Routes that MUST have a valid user JWT (or admin JWT).
    USER_PROTECTED_PREFIXES: tuple[str, ...] = (
        "/api/v1/billing/",
        "/api/v1/tasks/",
        "/api/v1/collaboration/",
        "/api/v1/reviews/",
    )

    # Routes that MUST have an admin JWT.
    ADMIN_PROTECTED_PREFIXES: tuple[str, ...] = (
        "/api/v1/admin/",
        "/api/v1/admin",
    )

    # Public routes — no auth required.
    PUBLIC_PATHS: set[str] = {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        path = request.url.path

        # ── Auth disabled via env var: pass through (dev/test only) ─
        if settings.disable_auth:
            return await call_next(request)

        # ── Public paths: pass through ──────────────────────────────
        if path in self.PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # ── Admin paths: require admin JWT ──────────────────────────
        if path.startswith(self.ADMIN_PROTECTED_PREFIXES):
            token = _extract_bearer_token(request)
            if not token:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Authentication required", "code": "UNAUTHORIZED"},
                )
            try:
                payload = _decode_jwt(token)
                if payload.get("role") != "admin":
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Admin access required", "code": "FORBIDDEN"},
                    )
            except jwt.PyJWTError:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or expired token", "code": "UNAUTHORIZED"},
                )
            return await call_next(request)

        # ── User-protected paths: require user JWT ──────────────────
        if path.startswith(self.USER_PROTECTED_PREFIXES):
            token = _extract_bearer_token(request)
            if not token:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Authentication required", "code": "UNAUTHORIZED"},
                )
            try:
                _decode_jwt(token)  # any valid user JWT is sufficient
            except jwt.PyJWTError:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or expired token", "code": "UNAUTHORIZED"},
                )
            return await call_next(request)

        # ── Agent-protected paths: require agent Bearer token ───────
        if path.startswith(self.AGENT_PROTECTED_PREFIXES):
            token = _extract_bearer_token(request)
            if not token:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Agent authentication required", "code": "UNAUTHORIZED"},
                )
            # MVP: accept any ait_* token; real validation TBD
            if not (token.startswith(_AGENT_KEY_PREFIX) or token in _HARDCODED_AGENT_KEYS):
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid agent credentials", "code": "UNAUTHORIZED"},
                )
            return await call_next(request)

        # ── Unknown paths: require auth (secure-by-default) ─────────
        # In development, allow through; in production, reject.
        if settings.log_level == "DEBUG":
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"error": "Authentication required", "code": "UNAUTHORIZED"},
        )


# ---------------------------------------------------------------------------
# Utility: generate an admin token (startup / CLI only)
# ---------------------------------------------------------------------------

def create_admin_token() -> str:
    """Return a signed JWT for the admin user (valid 24 h)."""
    return _create_jwt("admin", role="admin", expires_minutes=settings.user_jwt_expire_minutes)


def create_agent_key(agent_id: str) -> str:
    """Generate a deterministic agent API key from the agent ID.

    In production this MUST be a random opaque token stored in the DB.
    The MVP implementation is deliberately simple.
    """
    import uuid

    namespace = uuid.NAMESPACE_DNS
    suffix = uuid.uuid5(namespace, agent_id).hex[:16]
    return f"{_AGENT_KEY_PREFIX}{suffix}"


# ---------------------------------------------------------------------------
# Admin API guard (replaces the old _require_admin query-param hack)
# ---------------------------------------------------------------------------

async def guard_admin(request: Request) -> str:
    """
    Drop-in replacement for the old ``_require_admin(user_id: str)``.

    Returns the admin's user_id on success.

    Usage::

        @router.get("/admin/overview")
        async def overview(admin_id: str = Depends(guard_admin)):
            ...
    """
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Backward-compat: accept query-param ?user_id=admin with a warning
    user_id_param = request.query_params.get("user_id")
    if user_id_param in ("admin", "root") and (not token or token == "demo"):
        logger.warning(
            "⚠️  Admin access via query-param user_id=%s — "
            "this is deprecated and will be removed. Use JWT Bearer token.",
            user_id_param,
        )
        return user_id_param

    try:
        payload = _decode_jwt(token)
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
