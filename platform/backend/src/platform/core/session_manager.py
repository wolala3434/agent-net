"""
Session Manager — collaboration session lifecycle, message routing, deadlock detection.

Manages the state machine:
    initiated -> negotiating <-> converging -> completed
                           -> deadlocked

Fills gaps identified in doc review:
  - converging state entry/exit criteria
  - deadlock threshold (default: 5 consecutive disagrees)
  - nesting depth limit (default: 3)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..constants import TaskStatus, UUID_TRUNCATE_LEN, LOG_ID_TRUNCATE_LEN
from ..models import (
    CollaborationSession as DBSession,
    CollaborationMessage as DBMessage,
    Task,
)
from ..repository import AgentRepository, SessionRepository
from .discovery import discover_agents
from .session.forwarder import _forward_async
from .session.nesting import check_nesting_depth as _check_nesting_depth
from .session.nesting import is_timed_out as _is_timed_out
from .session.state_machine import (
    CONVERGENCE_TYPES as CONVERGENCE_TYPES,
    CONFLICT_TYPES as CONFLICT_TYPES,
    NEUTRAL_TYPES as NEUTRAL_TYPES,
    VALID_TRANSITIONS as VALID_TRANSITIONS,
    SessionState,
    transition,
    evaluate_convergence,
    detect_deadlock,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Collaboration session lifecycle manager.

    Responsibilities (per aip-protocol.md):
      1. Create sessions, invite participants via discovery
      2. Maintain shared context ("whiteboard")
      3. Route messages between participants
      4. Enforce state machine transitions
      5. Record full conversation chain
      6. Deadlock detection
      7. Nested collaboration support (with depth limit)
    """

    def __init__(
        self,
        deadlock_threshold: int | None = None,
        max_nesting_depth: int | None = None,
        max_turns: int | None = None,
        timeout_seconds: int | None = None,
    ):
        self.deadlock_threshold = deadlock_threshold or settings.session_deadlock_threshold
        self.max_nesting_depth = max_nesting_depth or settings.session_max_nesting_depth
        self.max_turns = max_turns or settings.session_max_turns
        self.timeout_seconds = timeout_seconds or settings.session_timeout_seconds

    # ------------------------------------------------------------------
    # State machine (delegated to pure-logic module)
    # ------------------------------------------------------------------

    def transition(
        self,
        current: SessionState,
        target: SessionState,
    ) -> SessionState:
        """Validate and execute a state transition."""
        return transition(current, target)

    def evaluate_convergence(
        self,
        current_state: SessionState,
        recent_message_types: list[str],
    ) -> SessionState:
        """Determine if negotiating should transition to converging."""
        return evaluate_convergence(current_state, recent_message_types)

    def detect_deadlock(
        self,
        recent_message_types: list[str],
    ) -> bool:
        """Check if the session is deadlocked."""
        return detect_deadlock(recent_message_types, self.deadlock_threshold)

    # ------------------------------------------------------------------
    # Nesting depth check (delegated)
    # ------------------------------------------------------------------

    def check_nesting_depth(self, parent_depth: int) -> bool:
        """Refuse nested sessions beyond the configured limit."""
        return _check_nesting_depth(parent_depth, self.max_nesting_depth)

    # ------------------------------------------------------------------
    # Timeout check (delegated)
    # ------------------------------------------------------------------

    def is_timed_out(self, last_activity: float) -> bool:
        """Check if the session has exceeded its timeout."""
        return _is_timed_out(last_activity, self.timeout_seconds)

    # ------------------------------------------------------------------
    # Session CRUD (DB operations)
    # ------------------------------------------------------------------

    async def create_session(
        self,
        db: AsyncSession,
        task_id: str | None,
        initiator_agent: str,
        goal: str,
        required_domains: list[str],
        shared_context: dict[str, Any] | None = None,
        parent_session_id: str | None = None,
        discovery_query: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a collaboration session.

        1. Validate nesting depth if parent_session_id is provided
        2. Run discovery to find suitable participants
        3. Initiator auto-joins as participant
        4. Persist session in DB
        5. Auto-transition to negotiating
        6. Return full session dict
        """
        # Check nesting depth
        nesting_depth = 0
        if parent_session_id:
            parent_result = await self.get_session(db, parent_session_id)
            if parent_result:
                nesting_depth = (parent_result.get("nesting_depth", 0) or 0) + 1
            if not self.check_nesting_depth(nesting_depth):
                raise ValueError(
                    f"Max nesting depth ({self.max_nesting_depth}) exceeded"
                )

        # Run discovery to find participants
        # Use discovery_query (rewritten by the initiator agent) for semantic
        # matching; fall back to goal if not provided.
        discovered = await self._discover_participants(
            db, discovery_query or goal, required_domains, initiator_agent
        )

        # Build participants list (initiator first)
        now = datetime.now(timezone.utc)
        participants_list: list[dict[str, Any]] = [
            {
                "agent_id": initiator_agent,
                "role": "initiator",
                "joined_at": now.isoformat(),
            }
        ]
        for agent in discovered:
            if agent["id"] != initiator_agent:
                participants_list.append({
                    "agent_id": agent["id"],
                    "role": "participant",
                    "joined_at": now.isoformat(),
                })

        session_id = f"sess_{uuid.uuid4().hex[:UUID_TRUNCATE_LEN]}"

        session = DBSession(
            id=session_id,
            task_id=task_id,
            status=SessionState.negotiating.value,  # auto-transition on create
            goal=goal,
            shared_context=json.dumps(shared_context or {}),
            participants_json=json.dumps(participants_list),
            turn_count=0,
            nesting_depth=nesting_depth,
            parent_session_id=parent_session_id,
            created_at=now,
        )
        db.add(session)
        await db.commit()  # single commit for insert + status
        await db.refresh(session)

        return self._session_to_dict(session, participants_list)

    async def get_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> dict[str, Any] | None:
        """Get full session state, including messages."""
        result = await db.execute(
            select(DBSession).where(DBSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        participants = json.loads(session.participants_json)

        # Get messages
        messages_result = await db.execute(
            select(DBMessage)
            .where(DBMessage.session_id == session_id)
            .order_by(DBMessage.turn_number)
        )
        messages = messages_result.scalars().all()

        session_dict = self._session_to_dict(session, participants)
        session_dict["messages"] = [
            {
                "message_id": m.message_id,
                "turn_number": m.turn_number,
                "sender_id": m.sender_id,
                "message_type": m.message_type,
                "references": json.loads(m.references_to or "[]"),
                "body": json.loads(m.body_json),
                "created_at": m.created_at,
            }
            for m in messages
        ]
        return session_dict

    async def add_message(
        self,
        db: AsyncSession,
        session_id: str,
        message_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Add a collaboration message to a session.

        Side effects:
          - Increment turn_number
          - Merge session_context_update into shared_context
          - Evaluate state transitions (converging, deadlocked, completed)
          - Auto-complete if max_turns reached with consensus
        """
        # Validate session exists and is writable
        result = await db.execute(
            select(DBSession).where(DBSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status in (
            SessionState.completed.value,
            SessionState.deadlocked.value,
        ):
            raise ValueError(
                f"Session {session_id} is '{session.status}', cannot add messages"
            )

        # Determine turn number
        turn_number = (session.turn_count or 0) + 1

        sender = message_data.get("sender", {})
        sender_id = (
            sender.get("agent_id", "unknown")
            if isinstance(sender, dict)
            else "unknown"
        )

        message_type = message_data.get("message_type", "propose")
        body = message_data.get("body", {})
        references = message_data.get("references", [])
        context_update = message_data.get("session_context_update")
        message_id = message_data.get(
            "message_id", f"msg_{uuid.uuid4().hex[:LOG_ID_TRUNCATE_LEN]}"
        )

        # Persist the message
        msg = DBMessage(
            message_id=message_id,
            session_id=session_id,
            turn_number=turn_number,
            sender_id=sender_id,
            message_type=message_type,
            references_to=json.dumps(references),
            body_json=json.dumps(body),
        )
        db.add(msg)

        # Update turn count
        session.turn_count = turn_number

        # Merge session context update
        if context_update:
            current_context = json.loads(session.shared_context or "{}")
            current_context.update(context_update)
            session.shared_context = json.dumps(current_context)

        # State machine evaluation
        recent_types = await SessionRepository.get_recent_message_types(db, session_id)
        current_state = SessionState(session.status)

        # Check convergence (negotiating -> converging)
        if current_state == SessionState.negotiating:
            new_state = self.evaluate_convergence(current_state, recent_types)
            if new_state != current_state:
                session.status = new_state.value
                current_state = new_state

        # Check deadlock
        if current_state in (
            SessionState.negotiating,
            SessionState.converging,
        ):
            if self.detect_deadlock(recent_types):
                session.status = SessionState.deadlocked.value

        # Auto-complete: consensus reached naturally
        # Works from both negotiating and converging states.
        # Criteria: synthesize message + majority of recent turns are agreement
        # recent_types is DESC (newest first), so take [:5]
        if session.status in (
            SessionState.negotiating.value,
            SessionState.converging.value,
        ):
            recent = recent_types[:5]
            agree_count = sum(
                1 for t in recent if t in ("agree", "synthesize")
            )
            if message_type == "synthesize" and agree_count >= max(len(recent) - 1, 1):
                session.status = SessionState.completed.value

        # Auto-complete if max turns reached and not deadlocked
        if (
            turn_number >= self.max_turns
            and session.status not in (
                SessionState.deadlocked.value,
                SessionState.completed.value,
            )
        ):
            if session.status == SessionState.converging.value:
                session.status = SessionState.completed.value

        # Record completion timestamp
        if session.status in (
            SessionState.completed.value,
            SessionState.deadlocked.value,
        ):
            session.completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(msg)

        # ── Forward message to all OTHER participants ─────────────────
        # Fire-and-forget: forwarding runs in background so LLM latency
        # doesn't block the /messages POST response.
        participants = json.loads(session.participants_json or "[]")
        other_participants = [
            p for p in participants if p.get("agent_id") != sender_id
        ]
        if other_participants:
            logger.info("[SESSION] Forwarding to %d participants (background)...", len(other_participants))
            import asyncio
            asyncio.create_task(
                _forward_async(session_id, message_id, other_participants, message_data)
            )

        return {
            "message_id": msg.message_id,
            "session_id": msg.session_id,
            "turn_number": msg.turn_number,
            "sender_id": msg.sender_id,
            "message_type": msg.message_type,
            "references": json.loads(msg.references_to or "[]"),
            "body": json.loads(msg.body_json),
            "created_at": msg.created_at,
        }

    async def get_messages(
        self,
        db: AsyncSession,
        session_id: str,
        since_turn: int = 0,
    ) -> list[dict[str, Any]]:
        """Get message history for a session, optionally from a given turn."""
        query = (
            select(DBMessage)
            .where(DBMessage.session_id == session_id)
            .where(DBMessage.turn_number > since_turn)
            .order_by(DBMessage.turn_number)
        )
        result = await db.execute(query)
        messages = result.scalars().all()

        return [
            {
                "message_id": m.message_id,
                "session_id": m.session_id,
                "turn_number": m.turn_number,
                "sender_id": m.sender_id,
                "message_type": m.message_type,
                "references": json.loads(m.references_to or "[]"),
                "body": json.loads(m.body_json),
                "created_at": m.created_at,
            }
            for m in messages
        ]

    async def list_sessions(
        self,
        db: AsyncSession,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List sessions with optional filters."""
        query = select(DBSession)
        if status:
            query = query.where(DBSession.status == status)
        query = query.order_by(desc(DBSession.created_at))

        result = await db.execute(query)
        sessions = result.scalars().all()

        result_list = []
        for session in sessions:
            participants = json.loads(session.participants_json)
            if agent_id:
                agent_ids = [p["agent_id"] for p in participants]
                if agent_id not in agent_ids:
                    continue
            result_list.append(self._session_to_dict(session, participants))

        return result_list

    async def update_shared_context(
        self,
        db: AsyncSession,
        session_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge updates into the session shared context."""
        result = await db.execute(
            select(DBSession).where(DBSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        current = json.loads(session.shared_context or "{}")
        current.update(updates)
        session.shared_context = json.dumps(current)
        await db.commit()

        return json.loads(session.shared_context)

    # ------------------------------------------------------------------
    # Task status helpers
    # ------------------------------------------------------------------

    async def update_task_status(
        self,
        db: AsyncSession,
        task_id: str,
        status: str,
    ) -> None:
        """Update a task's status and timestamps."""
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
            task.completed_at = datetime.now(timezone.utc)
        await db.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _session_to_dict(
        self,
        session: DBSession,
        participants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert a DB session model to a JSON-compatible dict."""
        return {
            "id": session.id,
            "task_id": session.task_id,
            "status": session.status,
            "goal": session.goal,
            "shared_context": json.loads(session.shared_context or "{}"),
            "participants": participants,
            "result": json.loads(session.result_json) if session.result_json else None,
            "turn_count": session.turn_count,
            "nesting_depth": session.nesting_depth or 0,
            "parent_session_id": session.parent_session_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }

    async def _discover_participants(
        self,
        db: AsyncSession,
        goal: str,
        required_domains: list[str],
        initiator_agent: str,
    ) -> list[dict[str, Any]]:
        """
        Run discovery to find suitable participants for a session.

        For MVP, queries active agents from DB, builds dicts for the
        discovery engine, and returns the top matches (excluding initiator).
        Uses a simple text-hash embedding when real embeddings aren't available.
        """
        # Query active agents
        agents = await AgentRepository.get_active_agents(db)

        if not agents:
            return []

        # Build agent dicts using the unified repository method
        agent_dicts: list[dict[str, Any]] = []
        for a in agents:
            agent_dicts.append(
                await AgentRepository.build_discovery_payload(db, a)
            )

        if not agent_dicts:
            return []

        # Use the real embedding function (shares the global model).
        # When the model is unavailable the fallback in embeddings.py
        # produces a deterministic keyword-frequency vector — unlike the
        # previous MD5→np.random hack which was pure noise.
        from .embeddings import compute_embedding

        _embed_fn = compute_embedding  # model or deterministic fallback

        selected, _mode = discover_agents(
            task_description=goal,
            task_domains=required_domains,
            agents=agent_dicts,
            embed_fn=_embed_fn,
            top_k=5,
        )

        return selected
