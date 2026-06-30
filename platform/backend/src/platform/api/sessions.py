"""
Collaboration session management API — per api-spec.md section 4.

Endpoints:
  POST   /api/v1/collaboration/sessions
  GET    /api/v1/collaboration/sessions/{session_id}
  GET    /api/v1/collaboration/sessions
  POST   /api/v1/collaboration/sessions/{session_id}/messages
  GET    /api/v1/collaboration/sessions/{session_id}/messages
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.session_manager import SessionManager
from ..core.messaging import validate_l2_message
from ..database import async_session
from ..schemas import SessionCreateRequest
from ..constants import SessionStatus

router = APIRouter()

# Module-level singleton (lightweight, no DB state held)
session_manager = SessionManager()


async def get_db() -> AsyncSession:
    """Yield an async database session."""
    async with async_session() as db:
        yield db


@router.post("/collaboration/sessions", status_code=201)
async def create_session(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a collaboration session.

    Three initiation paths (per aip-protocol.md):
      1. User-initiated via Dashboard
      2. API Gateway auto-detection (complex tasks)
      3. Agent self-initiated (agent discovers capability gap)

    The initiator auto-joins as a participant with role 'initiator'.
    Discovery runs to find additional participants matching required_domains.
    """
    try:
        session = await session_manager.create_session(
            db=db,
            task_id=body.parent_task_id,
            initiator_agent=body.initiator_agent,
            goal=body.goal,
            discovery_query=body.discovery_query,
            required_domains=body.required_domains,
            shared_context=body.shared_context,
            parent_session_id=None,
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/collaboration/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full session state including shared context, participants, and messages."""
    session = await session_manager.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.get("/collaboration/sessions")
async def list_sessions(
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List sessions with optional filters by agent_id or status."""
    valid_statuses = {s.value for s in SessionStatus}
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )
    return await session_manager.list_sessions(db, agent_id=agent_id, status=status)


@router.post("/collaboration/sessions/{session_id}/messages", status_code=201)
async def send_collaboration_message(
    session_id: str,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Send a collaboration message (L2 envelope) within a session.

    Expected body (per aip-protocol.md L2):
    ```json
    {
      "sender": {"agent_id": "...", "role": "..."},
      "message_type": "propose|critique|clarify|refine|agree|disagree|synthesize",
      "body": { ... },
      "references": ["msg_xxx", "msg_yyy"],
      "session_context_update": { ... }
    }
    ```
    """
    # Validate L2 message format
    errors = validate_l2_message(body)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Validate message type
    valid_types = {
        "propose", "critique", "clarify", "refine",
        "agree", "disagree", "synthesize",
    }
    msg_type = body.get("message_type", "")
    if msg_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"message_type must be one of: {', '.join(sorted(valid_types))}",
        )

    try:
        message = await session_manager.add_message(db, session_id, body)
        return message
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/collaboration/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    since_turn: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get message history for a session, optionally from a given turn number."""
    # Verify session exists
    session = await session_manager.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return await session_manager.get_messages(db, session_id, since_turn=since_turn)
