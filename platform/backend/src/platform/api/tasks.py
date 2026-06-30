"""
Task submission, tracking, cancellation — per api-spec.md section 3.

State machine: pending -> discovered -> assigned -> running -> completed
                                                     |        |
                                                   failed  cancelled

Endpoints:
  POST   /api/v1/tasks
  GET    /api/v1/tasks/{task_id}
  GET    /api/v1/tasks
  POST   /api/v1/tasks/{task_id}/cancel
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.discovery import is_complex_task as _is_complex
from ..core.session_manager import SessionManager
from ..database import async_session
from ..models import Task
from ..schemas import TaskSubmitRequest, TaskResponse
from ..constants import AgentStatus, TaskStatus, DEFAULT_USER_ID, UUID_TRUNCATE_LEN

router = APIRouter()
session_manager = SessionManager()


async def get_db() -> AsyncSession:
    """Yield an async database session."""
    async with async_session() as db:
        yield db


@router.post("/tasks", status_code=202, response_model=TaskResponse)
async def submit_task(
    body: TaskSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a task.

    Routing decision (per aip-protocol.md):
      - collaboration_mode=True  -> always collaboration
      - is_complex_task(domains) -> collaboration
      - otherwise                -> single agent

    Returns task_id, status, mode ('single' or 'collaboration'),
    and session_id/participants if collaboration mode.
    """
    # Resolve user_id
    user_id = body.user_id or DEFAULT_USER_ID

    # Determine routing mode
    if body.collaboration_mode:
        mode = "collaboration"
    elif _is_complex(body.description, body.domains):
        mode = "collaboration"
    else:
        mode = "single"

    # Create task record
    task_id = f"task_{uuid.uuid4().hex[:UUID_TRUNCATE_LEN]}"
    now = datetime.now(timezone.utc)

    task = Task(
        id=task_id,
        description=body.description,
        input_json=json.dumps(body.input),
        status=TaskStatus.PENDING.value,
        priority=body.priority,
        user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.commit()

    if mode == "collaboration":
        return await _route_collaboration(
            db, task_id, body, user_id,
        )
    else:
        return await _route_single(db, task_id, body, user_id)


async def _route_single(
    db: AsyncSession,
    task_id: str,
    body: TaskSubmitRequest,
    user_id: str,
) -> TaskResponse:
    """
    Route a task to a single agent via discovery.

    1. Update task status -> discovered
    2. Run discovery to find best agent
    3. Update task status -> assigned -> running
    4. Return task response with assigned agent
    """
    from ..core.billing import BillingService
    from ..models import Agent as AgentModel

    # Update status to discovered
    await session_manager.update_task_status(db, task_id, TaskStatus.DISCOVERED.value)

    # Query active agents for discovery
    result = await db.execute(
        select(AgentModel).where(AgentModel.status == AgentStatus.ACTIVE.value)
    )
    agents = result.scalars().all()

    # Build agent dicts
    agent_dicts = []
    for a in agents:
        card = {}
        try:
            card = json.loads(a.card_json) if a.card_json else {}
        except (json.JSONDecodeError, TypeError):
            pass
        pricing = card.get("pricing", {})
        agent_dicts.append({
            "id": a.id,
            "name": a.name,
            "description": a.description or "",
            "avg_rating": a.avg_rating,
            "trial_status": a.trial_status,
            "provider_name": a.provider_name or "",
            "review_count": a.total_tasks,
            "days_since_registration": 0,
            "unit_price": pricing.get("unit_price", 0.0),
            "skills": [],
            "embedding": [],
        })

    # Pick best agent (simplified: top by rating, then by name)
    if agent_dicts:
        # Apply preference for user's pinned agents
        pinned_ids: set[str] = set()
        if body.preferred_agents:
            pinned_ids = set(body.preferred_agents)

        # Sort: pinned first, then by rating descending
        def sort_key(a: dict[str, Any]) -> tuple:
            return (
                0 if a["id"] in pinned_ids else 1,
                -a["avg_rating"],
                a["name"],
            )
        agent_dicts.sort(key=sort_key)
        best_agent = agent_dicts[0]

        # Update task with assigned agent
        task = await _get_task(db, task_id)
        if task:
            task.status = TaskStatus.ASSIGNED.value
            task.assigned_agent_id = best_agent["id"]
            task.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # Update to running for MVP (actual dispatch is async)
            task.status = TaskStatus.RUNNING.value
            task.updated_at = datetime.now(timezone.utc)
            await db.commit()

        # Record billing charge for the agent call
        try:
            billing = BillingService()
            await billing.charge(
                db,
                task_id=task_id,
                session_id=None,
                user_id=user_id if user_id != DEFAULT_USER_ID else None,
                agent_id=best_agent["id"],
                units=1.0,
            )
        except ValueError:
            # Charge failure shouldn't block task creation for MVP
            pass

        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.RUNNING.value,
            mode="single",
            session_id=None,
            participants=[best_agent["id"]],
        )

    # No agents available
    await session_manager.update_task_status(db, task_id, TaskStatus.FAILED.value)
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.FAILED.value,
        mode="single",
        session_id=None,
        participants=[],
    )


async def _route_collaboration(
    db: AsyncSession,
    task_id: str,
    body: TaskSubmitRequest,
    user_id: str,
) -> TaskResponse:
    """
    Route a task to collaboration mode.

    1. Update task status -> discovered
    2. Create collaboration session (session manager handles discovery)
    3. Update task status remains 'discovered' (session is active)
    4. Return task response with session_id and participants
    """
    from ..core.billing import BillingService
    from ..models import Agent as AgentModel

    # Update status to discovered
    await session_manager.update_task_status(db, task_id, TaskStatus.DISCOVERED.value)

    # Find initiator agent (preferred first, else discovery)
    initiator_agent = None
    if body.preferred_agents:
        initiator_agent = body.preferred_agents[0]

    if not initiator_agent:
        # Pick the highest-rated agent available
        result = await db.execute(
            select(AgentModel).where(AgentModel.status == AgentStatus.ACTIVE.value)
            .order_by(desc(AgentModel.avg_rating))
            .limit(1)
        )
        best = result.scalar_one_or_none()
        initiator_agent = best.id if best else "unknown"

    # Create collaboration session
    try:
        session = await session_manager.create_session(
            db=db,
            task_id=task_id,
            initiator_agent=initiator_agent,
            goal=body.description,
            required_domains=body.domains,
            shared_context={"task_input": body.input},
            parent_session_id=None,
        )
    except ValueError:
        # Fallback to single-agent if session creation fails
        return await _route_single(db, task_id, body, user_id)

    participants = [p["agent_id"] for p in session.get("participants", [])]

    # Charge each participant (except initiator, who already paid)
    billing = BillingService()
    for agent_id in participants:
        if agent_id != initiator_agent:
            try:
                await billing.charge(
                    db,
                    task_id=task_id,
                    session_id=session["id"],
                    user_id=user_id if user_id != DEFAULT_USER_ID else None,
                    agent_id=agent_id,
                    units=1.0,
                )
            except ValueError:
                pass

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.DISCOVERED.value,
        mode="collaboration",
        session_id=session["id"],
        participants=participants,
    )


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get task status and result."""
    task = await _get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "task_id": task.id,
        "description": task.description,
        "status": task.status,
        "assigned_agent_id": task.assigned_agent_id,
        "input": json.loads(task.input_json) if task.input_json else {},
        "result": json.loads(task.result_json) if task.result_json else None,
        "error": json.loads(task.error_json) if task.error_json else None,
        "priority": task.priority,
        "user_id": task.user_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
    }


@router.get("/tasks")
async def list_tasks(
    user_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List tasks with optional filters."""
    valid_statuses = {s.value for s in TaskStatus}
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    query = select(Task)
    if user_id:
        query = query.where(Task.user_id == user_id)
    if status:
        query = query.where(Task.status == status)
    query = query.order_by(desc(Task.created_at)).limit(limit)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return [
        {
            "task_id": t.id,
            "description": t.description,
            "status": t.status,
            "assigned_agent_id": t.assigned_agent_id,
            "priority": t.priority,
            "user_id": t.user_id,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in tasks
    ]


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running/pending task."""
    task = await _get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} is already '{task.status}', cannot cancel",
        )

    task.status = TaskStatus.CANCELLED.value
    task.completed_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "task_id": task.id,
        "status": task.status,
        "message": "Task cancelled",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_task(db: AsyncSession, task_id: str) -> Task | None:
    """Fetch a task by ID."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()
