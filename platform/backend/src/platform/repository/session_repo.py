"""SessionRepository — CollaborationSession + CollaborationMessage queries."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    CollaborationSession,
    CollaborationMessage,
    Task,
)
from ..constants import TaskStatus


class SessionRepository:

    @staticmethod
    async def create_session(
        db: AsyncSession, **kwargs
    ) -> CollaborationSession:
        session = CollaborationSession(**kwargs)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def get_session(
        db: AsyncSession, session_id: str
    ) -> CollaborationSession | None:
        result = await db.execute(
            select(CollaborationSession).where(
                CollaborationSession.id == session_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        session_id: str,
        since_turn: int = 0,
    ) -> list[CollaborationMessage]:
        query = (
            select(CollaborationMessage)
            .where(CollaborationMessage.session_id == session_id)
            .where(CollaborationMessage.turn_number > since_turn)
            .order_by(CollaborationMessage.turn_number)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def add_message(
        db: AsyncSession, **kwargs
    ) -> CollaborationMessage:
        msg = CollaborationMessage(**kwargs)
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def get_recent_message_types(
        db: AsyncSession,
        session_id: str,
        limit: int = 10,
    ) -> list[str]:
        """Return the most recent message types (newest first).
        Used by deadlock / convergence detection."""
        query = (
            select(CollaborationMessage.message_type)
            .where(CollaborationMessage.session_id == session_id)
            .order_by(desc(CollaborationMessage.turn_number))
            .limit(limit)
        )
        result = await db.execute(query)
        return [row[0] for row in result.fetchall()]

    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[CollaborationSession]:
        query = select(CollaborationSession)
        if status:
            query = query.where(CollaborationSession.status == status)
        query = query.order_by(desc(CollaborationSession.created_at))
        result = await db.execute(query)
        sessions = list(result.scalars().all())

        if agent_id:
            filtered = []
            for s in sessions:
                participants = json.loads(s.participants_json)
                agent_ids = [p["agent_id"] for p in participants]
                if agent_id in agent_ids:
                    filtered.append(s)
            return filtered
        return sessions

    @staticmethod
    async def update_session(
        db: AsyncSession, session_id: str, **kwargs
    ) -> None:
        session = await SessionRepository.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        for key, value in kwargs.items():
            setattr(session, key, value)
        await db.commit()

    @staticmethod
    async def update_shared_context(
        db: AsyncSession, session_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        session = await SessionRepository.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        current = json.loads(session.shared_context or "{}")
        current.update(updates)
        session.shared_context = json.dumps(current)
        await db.commit()
        return json.loads(session.shared_context)

    @staticmethod
    async def update_task_status(
        db: AsyncSession, task_id: str, status: str
    ) -> None:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        if status in (
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        ):
            task.completed_at = datetime.now(timezone.utc)
        await db.commit()
