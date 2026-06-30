"""Admin API — platform operator endpoints.

Accessed only by admin users. Covers: agent review queue, system
overview, revenue dashboard, report moderation.

MVP: uses query-param ``user_id`` (insecure but sufficient for local dev).
Production: replace with JWT ``guard_admin`` dependency.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import (
    SECONDS_PER_DAY,
    AgentStatus,
    TrialStatus,
    DESCRIPTION_TRUNCATE_LEN,
)
from ..database import async_session as _async_session_factory
from ..models import (
    Agent,
    AgentReview,
    BillingTransaction,
    CollaborationSession,
    Task,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USERS = {"admin", "root"}


def _require_admin(user_id: str = Query(...)):
    if user_id not in ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


async def get_db() -> AsyncSession:
    """Yield an async DB session from the shared session factory."""
    async with _async_session_factory() as session:
        yield session


# ── System Overview ──────────────────────────────────────────
@router.get("/overview")
async def admin_overview(
    user_id: str = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):

    agent_count = (await db.execute(select(func.count(Agent.id)))).scalar()
    active_agent_count = (
        await db.execute(
            select(func.count(Agent.id)).where(Agent.status == AgentStatus.ACTIVE.value)
        )
    ).scalar()
    task_count = (await db.execute(select(func.count(Task.id)))).scalar()
    session_count = (
        await db.execute(select(func.count(CollaborationSession.id)))
    ).scalar()
    review_count = (
        await db.execute(select(func.count(AgentReview.id)))
    ).scalar()

    # Revenue
    revenue = (
        await db.execute(
            select(
                func.coalesce(func.sum(BillingTransaction.amount), 0),
                func.coalesce(func.sum(BillingTransaction.platform_fee), 0),
            ).where(BillingTransaction.is_free == 0)
        )
    ).first()
    total_revenue, total_fees = revenue if revenue else (0, 0)

    return {
        "agents": {"total": agent_count, "active": active_agent_count},
        "tasks": {"total": task_count},
        "sessions": {"total": session_count},
        "reviews": {"total": review_count},
        "revenue": {
            "gmv": round(float(total_revenue), 2),
            "platform_fees": round(float(total_fees), 2),
        },
    }


# ── Agent Review Queue ───────────────────────────────────────
@router.get("/agents/pending")
async def pending_agents(
    user_id: str = Depends(_require_admin),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Agents awaiting approval (trial status)."""

    result = await db.execute(
        select(Agent)
        .where(Agent.status == AgentStatus.ACTIVE.value, Agent.trial_status == TrialStatus.TRIAL.value)
        .order_by(Agent.registered_at.desc())
        .limit(limit)
    )
    agents = result.scalars().all()
    return {
        "total": len(agents),
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "provider_name": a.provider_name,
                "description": a.description[:DESCRIPTION_TRUNCATE_LEN] if a.description else "",
                "free_quota_total": a.free_quota_total,
                "free_quota_used": a.free_quota_used,
                "avg_rating": a.avg_rating,
                "total_tasks": a.total_tasks,
                "registered_at": a.registered_at.isoformat() if a.registered_at else None,
            }
            for a in agents
        ],
    }


@router.post("/agents/{agent_id}/approve")
async def approve_agent(
    agent_id: str,
    user_id: str = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve an agent (trial → verified)."""

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.trial_status = TrialStatus.VERIFIED.value
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"agent_id": agent_id, "trial_status": TrialStatus.VERIFIED.value}


@router.post("/agents/{agent_id}/reject")
async def reject_agent(
    agent_id: str,
    user_id: str = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject/downgrade an agent (→ low_quality)."""

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.trial_status = TrialStatus.LOW_QUALITY.value
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"agent_id": agent_id, "trial_status": TrialStatus.LOW_QUALITY.value}


@router.post("/agents/{agent_id}/suspend")
async def suspend_agent(
    agent_id: str,
    user_id: str = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Suspend an agent (active → suspended)."""

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.status = AgentStatus.SUSPENDED.value
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"agent_id": agent_id, "status": AgentStatus.SUSPENDED.value}


# ── All Agents (with full data for admin) ────────────────────
@router.get("/agents/all")
async def all_agents_admin(
    user_id: str = Depends(_require_admin),
    status: str | None = None,
    trial_status: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Admin list of all agents with full data."""

    q = select(Agent).order_by(Agent.registered_at.desc())
    if status:
        q = q.where(Agent.status == status)
    if trial_status:
        q = q.where(Agent.trial_status == trial_status)
    q = q.limit(limit)

    result = await db.execute(q)
    agents = result.scalars().all()
    return {
        "total": len(agents),
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "provider_name": a.provider_name,
                "status": a.status,
                "trial_status": a.trial_status,
                "avg_rating": a.avg_rating,
                "total_tasks": a.total_tasks,
                "successful_tasks": a.successful_tasks,
                "failed_tasks": a.failed_tasks,
                "free_quota_used": a.free_quota_used,
                "free_quota_total": a.free_quota_total,
                "health_status": a.health_status,
                "last_heartbeat_at": a.last_heartbeat_at.isoformat() if a.last_heartbeat_at else None,
                "registered_at": a.registered_at.isoformat() if a.registered_at else None,
            }
            for a in agents
        ],
    }


# ── Revenue Dashboard ────────────────────────────────────────
@router.get("/revenue")
async def admin_revenue(
    user_id: str = Depends(_require_admin),
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Revenue summary for the admin dashboard."""

    since = datetime.now(timezone.utc).timestamp() - days * SECONDS_PER_DAY
    since_dt = datetime.fromtimestamp(since, tz=timezone.utc)

    result = await db.execute(
        select(
            func.coalesce(func.sum(BillingTransaction.amount), 0),
            func.coalesce(func.sum(BillingTransaction.platform_fee), 0),
            func.coalesce(func.sum(BillingTransaction.agent_earning), 0),
            func.count(BillingTransaction.id),
        ).where(
            BillingTransaction.is_free == 0,
            BillingTransaction.created_at >= since_dt,
        )
    )
    gmv, fees, earnings, count = result.first() or (0, 0, 0, 0)

    # Per-agent breakdown
    agent_result = await db.execute(
        select(
            BillingTransaction.agent_id,
            func.sum(BillingTransaction.agent_earning),
            func.count(BillingTransaction.id),
        )
        .where(
            BillingTransaction.is_free == 0,
            BillingTransaction.created_at >= since_dt,
        )
        .group_by(BillingTransaction.agent_id)
        .order_by(func.sum(BillingTransaction.agent_earning).desc())
        .limit(20)
    )

    return {
        "period_days": days,
        "gmv": round(float(gmv), 2),
        "platform_fees": round(float(fees), 2),
        "agent_earnings_total": round(float(earnings), 2),
        "transaction_count": count,
        "top_agents": [
            {
                "agent_id": aid,
                "earnings": round(float(e), 2),
                "transactions": int(tc),
            }
            for aid, e, tc in agent_result.all()
        ],
    }


# ── Report / Review Moderation ───────────────────────────────
@router.get("/reviews/flagged")
async def flagged_reviews(
    user_id: str = Depends(_require_admin),
    min_rating: int = 2,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Reviews that may need moderator attention (low ratings)."""

    result = await db.execute(
        select(AgentReview)
        .where(AgentReview.rating <= min_rating)
        .order_by(AgentReview.created_at.desc())
        .limit(limit)
    )
    reviews = result.scalars().all()
    return {
        "total": len(reviews),
        "reviews": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "user_id": r.user_id,
                "task_id": r.task_id,
                "rating": r.rating,
                "review_text": r.review_text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
    }


@router.delete("/reviews/{review_id}")
async def delete_review(
    review_id: int,
    user_id: str = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a flagged review."""

    result = await db.execute(select(AgentReview).where(AgentReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.delete(review)
    await db.commit()
    return {"deleted": review_id}
