"""
Agent runtime — embedded FastAPI server lifecycle management.

Per sdk-guide.md, ``serve()`` does:
  1. Build ADL card from Agent config
  2. Register with Registry
  3. Start FastAPI server on configured port
  4. Expose /api/v1/task, /api/v1/a2a, /api/v1/health
  5. Start heartbeat loop (30 s interval)
  6. Deregister on graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status

from agent_internet_protocol import AIP_VERSION
from .paths import (
    AGENTS_REGISTER, AGENTS_DEREGISTER, AGENTS_HEARTBEAT,
    AGENT_TASK, AGENT_HEALTH, AGENT_A2A,
)

logger = logging.getLogger("agent-internet.runtime")

HEARTBEAT_INTERVAL = 30  # seconds
STARTUP_DELAY = 5  # seconds


def build_adl_card(config, host: str, port: int) -> dict[str, Any]:
    """Build an ADL JSON card from AgentConfig."""
    base_url = f"http://{host}:{port}"
    provider_name = config.provider.get("name", "unknown")
    provider_slug = provider_name.lower().replace(" ", "-")
    name_slug = config.name.lower().replace(" ", "-")

    return {
        "id": f"{provider_slug}.{name_slug}@{config.version}",
        "name": config.name,
        "version": config.version,
        "description": config.description,
        "provider": config.provider,
        "capabilities": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "input_schema": s.input_schema,
                "output_schema": s.output_schema,
                "domains": s.domains,
                "execution_type": s.execution_type,
                "estimated_cost": s.estimated_cost,
                "estimated_duration": s.estimated_duration,
            }
            for s in config.skills
        ],
        "endpoints": {
            "task": f"{base_url}{AGENT_TASK}",
            "health": f"{base_url}{AGENT_HEALTH}",
            "a2a": f"{base_url}{AGENT_A2A}",
        },
        "pricing": config.pricing,
        "authentication": config.authentication,
        "tags": config.tags,
    }


def _validate_against_schema(
    data: Any, schema: dict[str, Any], path: str = ""
) -> list[str]:
    """Minimal JSON Schema validation for ADL skill schemas."""
    from .agent import _validate_against_schema as _validate

    return _validate(data, schema, path)


def _get_agent_api_key() -> str | None:
    """Get the agent API key from environment variable."""
    return os.getenv("AGENT_API_KEY")


async def _verify_bearer_token(request: Request) -> None:
    """Verify Bearer token for protected endpoints."""
    api_key = _get_agent_api_key()
    if not api_key:
        # No API key configured, skip authentication
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:].strip()
    if token != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def serve(
    agent_fn: Callable | None = None,
    agent: Any | None = None,
    host: str | None = None,
    port: int | None = None,
    registry_url: str | None = None,
) -> None:
    """
    Start the Agent runtime.

    Args:
        agent_fn: A function decorated with @Agent (Mode A).
        agent: An AgentBase instance (Mode B).
        host: Bind address. Defaults to AGENT_HOST env var, or "0.0.0.0".
        port: Bind port. Required — set via AGENT_PORT env var or pass explicitly.
        registry_url: URL of the Registry / API Gateway. Required — set via REGISTRY_URL env var or pass explicitly.
    """
    # ── resolve config from env vars ────────────────────────────────────
    if host is None:
        host = os.environ.get("AGENT_HOST", "0.0.0.0")
    if port is None:
        _port = os.environ.get("AGENT_PORT")
        if not _port:
            raise ValueError("port is required: pass explicitly or set AGENT_PORT env var")
        port = int(_port)
    if registry_url is None:
        registry_url = os.environ.get("REGISTRY_URL")
        if not registry_url:
            raise ValueError("registry_url is required: pass explicitly or set REGISTRY_URL env var")

    # ── resolve config and handler ──────────────────────────────────────
    if agent_fn is not None and hasattr(agent_fn, "_agent_config"):
        config = agent_fn._agent_config
        handler = agent_fn
        is_class_mode = False
    elif agent is not None and isinstance(agent, object):
        from .agent import AgentBase as _AgentBase

        if isinstance(agent, _AgentBase):
            config = agent.config
            handler = agent
            is_class_mode = True
        else:
            raise TypeError("agent must be an AgentBase instance")
    else:
        raise ValueError(
            "Either agent_fn (decorated) or agent (AgentBase) must be provided"
        )

    adl_card = build_adl_card(config, host, port)
    agent_id = adl_card["id"]

    # Add authentication info to ADL card if API key is configured
    api_key = _get_agent_api_key()
    if api_key:
        import hashlib
        adl_card["authentication"] = {
            "type": "bearer_token",
            "token_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8],
        }

    # ── Lifespan context manager (startup / shutdown) ───────────────────
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup: register + launch heartbeat.  Shutdown: cancel + deregister."""
        # ---- startup ----
        registered = False
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            ) as client:
                resp = await client.post(
                    f"{registry_url}{AGENTS_REGISTER}",
                    json=adl_card,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    actual_id = data.get("agent_id", agent_id)
                    logger.info("Registration successful → agent_id: %s", actual_id)
                    registered = True
                elif resp.status_code == 409:
                    logger.info(
                        "Agent already registered (409) — using existing registration for %s",
                        agent_id,
                    )
                    registered = True  # treat 409 as success: agent is usable
                else:
                    logger.warning(
                        "Registration returned %d: %s", resp.status_code, resp.text[:200]
                    )
        except httpx.ConnectError:
            logger.error("Cannot connect to Registry at %s", registry_url)
            logger.error("Start the Registry first, then restart this agent.")

        if not registered:
            logger.warning(
                "Continuing without registration (heartbeat will be skipped)."
            )

        # heartbeat task
        heartbeat_task = asyncio.create_task(_heartbeat_loop(agent_id, registry_url))

        logger.info("HTTP server → http://%s:%d", host, port)
        logger.info("Heartbeat started (interval %ds)", HEARTBEAT_INTERVAL)
        logger.info("Agent online, waiting for tasks and collaboration invitations...")

        yield  # server runs here

        # ---- shutdown ----
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            ) as client:
                await client.delete(
                    f"{registry_url}{AGENTS_DEREGISTER.format(agent_id=agent_id)}",
                )
                logger.info("Deregistered: %s", agent_id)
        except Exception:
            pass

    # ── FastAPI app ────────────────────────────────────────────────────
    app = FastAPI(title=config.name, version=config.version, lifespan=lifespan)

    @app.post(AGENT_TASK)
    async def handle_task(request: Request, payload: dict[str, Any]):
        """Single-agent task endpoint — validate, execute, validate output."""
        # Verify Bearer token
        await _verify_bearer_token(request)
        # Validate input against the first skill's input_schema
        if config.skills:
            in_schema = config.skills[0].input_schema
            if in_schema:
                errs = _validate_against_schema(payload, in_schema)
                if errs:
                    return {"status": "validation_error", "errors": errs}

        try:
            if is_class_mode:
                result = await handler.handle_single_task(payload)
            else:
                result = handler(payload)

            # Validate output against the first skill's output_schema
            if config.skills:
                out_schema = config.skills[0].output_schema
                if out_schema:
                    errs = _validate_against_schema(result, out_schema)
                    if errs:
                        return {
                            "status": "output_validation_error",
                            "errors": errs,
                            "result": result,
                        }

            return {"status": "completed", "result": result}
        except Exception as exc:
            logger.exception("Task handler raised")
            return {"status": "error", "error": str(exc)}

    @app.post(AGENT_A2A)
    async def handle_a2a(request: Request, payload: dict[str, Any]):
        """Agent-to-agent collaboration message endpoint.

        Receives a forwarded message from the Session Manager, processes it
        via the agent's handler, then posts the response back to the session.

        This is the key mechanism that enables autonomous multi-turn
        negotiation between agents.
        """
        # Verify Bearer token
        await _verify_bearer_token(request)

        if not is_class_mode:
            return {
                "status": "error",
                "error": "Decorated agents do not support collaboration mode",
            }

        session_id = payload.get("session_id", "")
        try:
            from .models.protocol import CollaborationSession, L2Message

            l2_msg = L2Message(**payload)
            session = CollaborationSession(
                id=l2_msg.session_id,
                goal="",
                status="negotiating",
            )
            result = await handler.handle_collaboration_message(session, payload)

            # ── Post response back to the session ──────────────────────
            # Only respond if the handler returned a message_type (i.e. the
            # agent actually has something to say).  No message_type means
            # the agent chose to stay silent.
            if isinstance(result, dict) and result.get("message_type"):
                import uuid
                from .collaboration import CollaborationClient

                client = CollaborationClient(registry_url)
                await client.send_message(session_id, {
                    "aip_version": AIP_VERSION,
                    "protocol_layer": "collaboration",
                    "message_id": f"resp_{uuid.uuid4().hex[:12]}",
                    "session_id": session_id,
                    "sender": {"agent_id": agent_id, "role": "participant"},
                    "message_type": result["message_type"],
                    "body": result.get("body", {}),
                    "session_context_update": result.get(
                        "session_context_update", {}
                    ),
                    "references": [payload.get("message_id", "")],
                })
            return {"status": "ok", "result": result}
        except Exception as exc:
            logger.exception("A2A handler raised")
            return {"status": "error", "error": str(exc)}

    @app.get(AGENT_HEALTH)
    async def health():
        return {"status": "healthy", "agent_id": agent_id}

    # ── Fire up the server ─────────────────────────────────────────────
    uvicorn.run(app, host=host, port=port, log_level="warning")


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------
async def _heartbeat_loop(agent_id: str, registry_url: str) -> None:
    """Send heartbeat to Registry every HEARTBEAT_INTERVAL seconds."""
    await asyncio.sleep(STARTUP_DELAY)  # initial delay for server startup
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    ) as client:
        while True:
            try:
                await client.post(
                    f"{registry_url}{AGENTS_HEARTBEAT.format(agent_id=agent_id)}",
                    json={"status": "healthy", "load": 0.0},
                )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Heartbeat failed (registry: %s)", registry_url)
            await asyncio.sleep(HEARTBEAT_INTERVAL)
