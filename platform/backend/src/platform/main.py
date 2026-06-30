"""
FastAPI application entry point for Agent Internet Platform.

Single-process MVP hosting all three core modules:
  - Discovery Engine  (agents, discovery endpoints)
  - Session Manager   (collaboration session endpoints)
  - Billing Service   (billing, payment endpoints)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .constants import HealthStatus
from .database import init_db
from .middleware import RateLimitMiddleware
from .api import (
    admin,
    agents,
    discovery,
    tasks,
    sessions,
    reviews,
    billing,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate config, init database; Shutdown: cleanup connections."""
    # Validate required environment variables
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL (REGISTRY_DATABASE_URL) environment variable is required."
        )

    # Validate SECRET_KEY in non-dev environments
    if settings.env != "dev" and settings.user_jwt_secret == "insecure-dev-secret":
        raise RuntimeError(
            "SECURITY ERROR: USER_JWT_SECRET is using default value 'insecure-dev-secret'. "
            "Set a secure random value via environment variable before running in "
            f"'{settings.env}' environment."
        )

    # Warn if CORS origins are using default localhost values in non-dev environments
    if settings.env != "dev" and "localhost" in settings.cors_origins:
        import logging
        logging.getLogger(__name__).warning(
            "SECURITY WARNING: CORS_ORIGINS contains localhost values in '%s' environment. "
            "Configure proper CORS origins for production.",
            settings.env,
        )

    await init_db()
    yield


app = FastAPI(
    title="Agent Internet Platform",
    version=__version__,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware (order matters: outer → inner execution)
# ---------------------------------------------------------------------------

# CORS — load from CORS_ORIGINS env var (comma-separated), defaults to localhost for dev
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate limiting — applied before auth so attackers can't bypass it
app.add_middleware(RateLimitMiddleware)

# Authentication — validates Bearer tokens on protected routes
# Disabled for MVP development; re-enable before production
# app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------
app.include_router(agents.router,     prefix="/api/v1", tags=["Agents"])
app.include_router(discovery.router,  prefix="/api/v1", tags=["Discovery"])
app.include_router(tasks.router,      prefix="/api/v1", tags=["Tasks"])
app.include_router(sessions.router,   prefix="/api/v1", tags=["Sessions"])
app.include_router(reviews.router,    prefix="/api/v1", tags=["Reviews"])
app.include_router(billing.router,    prefix="/api/v1", tags=["Billing"])
app.include_router(users.router,      prefix="/api/v1", tags=["Users"])
app.include_router(admin.router,      prefix="/api/v1", tags=["Admin"])


@app.get("/health")
async def health_check():
    """Deep health check: verifies DB connectivity, not just a static string."""
    try:
        from .database import engine
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"

    return {
        "status": HealthStatus.HEALTHY.value if db_status == "ok" else HealthStatus.DEGRADED.value,
        "service": "agent-internet-platform",
        "database": db_status,
    }
