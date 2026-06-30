"""Agent registration, query, update, deregister, heartbeat — per api-spec.md 1."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session
from ..models import Agent, Skill
from ..schemas import (
    AgentCard,
    AgentDetailResponse,
    AgentListResponse,
    HeartbeatRequest,
    RegisterResponse,
    UpdateAgentRequest,
)
from ..constants import (
    AgentStatus,
    TrialStatus,
    HealthStatus,
    DEFAULT_FREE_QUOTA,
)
from ..core.embeddings import compute_agent_embedding, embed_to_blob
from ..repository import AgentRepository

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Helper: build agent response dict from ORM model
# ---------------------------------------------------------------------------
async def _get_agent_domains(agent: Agent, session: AsyncSession) -> list[str]:
    """Extract unique domains from agent's skills."""
    skills = await AgentRepository.get_skills_for_agent(session, agent.id)
    all_domains: list[str] = []
    for s in skills:
        try:
            all_domains.extend(json.loads(s.domains))
        except (json.JSONDecodeError, TypeError):
            pass
    return list(set(all_domains))


async def _get_agent_review_stats(agent: Agent, session: AsyncSession) -> dict:
    """Compute review_count and rating_distribution from reviews."""
    from ..models import AgentReview
    from sqlalchemy import func

    review_result = await session.execute(
        select(
            func.count(AgentReview.id).label('count'),
            AgentReview.rating
        ).where(
            AgentReview.agent_id == agent.id
        ).group_by(AgentReview.rating)
    )

    review_count = 0
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for row in review_result.all():
        count = row.count
        rating = row.rating
        review_count += count
        if rating in rating_distribution:
            rating_distribution[rating] = count

    return {
        "review_count": review_count,
        "rating_distribution": rating_distribution,
    }


async def _build_agent_response(
    agent: Agent,
    session: AsyncSession,
    detail: bool = False
) -> dict:
    """
    Build agent response dict from ORM model.

    Args:
        agent: Agent ORM row
        session: Database session
        detail: If True, include full details (card_json, all fields).
                If False, return list item summary.
    """
    # Get common data
    domains = await _get_agent_domains(agent, session)
    review_stats = await _get_agent_review_stats(agent, session)

    # Parse card_json if needed
    card = None
    if detail:
        try:
            card = json.loads(agent.card_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Build base response
    response = {
        "id": agent.id,
        "name": agent.name,
        "version": agent.version,
        "provider_name": agent.provider_name,
        "description": agent.description,
        "status": agent.status,
        "trial_status": agent.trial_status,
        "health_status": agent.health_status,
        "avg_rating": agent.avg_rating,
        "total_tasks": agent.total_tasks,
        "review_count": review_stats["review_count"],
        "rating_distribution": review_stats["rating_distribution"],
        "domains": domains,
        "registered_at": agent.registered_at,
    }

    # Add detail-only fields
    if detail:
        response.update({
            "provider_url": agent.provider_url,
            "endpoint_url": agent.endpoint_url,
            "auth_type": agent.auth_type,
            "free_quota_total": agent.free_quota_total,
            "free_quota_used": agent.free_quota_used,
            "successful_tasks": agent.successful_tasks,
            "failed_tasks": agent.failed_tasks,
            "avg_latency_ms": agent.avg_latency_ms,
            "credit_score": agent.credit_score,
            "card_json": card,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
            "last_heartbeat_at": agent.last_heartbeat_at,
        })

    return response


async def _agent_to_detail(agent: Agent, session: AsyncSession) -> dict:
    """Convert an Agent ORM row to a dict suitable for AgentDetailResponse."""
    return await _build_agent_response(agent, session, detail=True)


async def _agent_to_list_item(agent: Agent, session: AsyncSession) -> dict:
    """Convert an Agent ORM row to a dict suitable for AgentListResponse."""
    return await _build_agent_response(agent, session, detail=False)


# ---------------------------------------------------------------------------
# POST /agents/register
# ---------------------------------------------------------------------------
@router.post("/agents/register", status_code=201)
async def register_agent(card: AgentCard) -> RegisterResponse:
    """
    Register a new Agent.

    Body: full ADL JSON (AgentCard schema).
    Steps:
      1. Validate the ADL card
      2. Compute capability embedding from descriptions
      3. Insert agent row + skill rows
      4. Set trial status (default: 'trial')
    """
    async with async_session() as session:
        # Upsert: update endpoints if agent already registered (e.g. restart)
        existing = await session.get(Agent, card.id)
        if existing:
            existing.endpoint_url = card.endpoints.task
            existing.health_status = HealthStatus.HEALTHY.value
            existing.updated_at = _now()
            existing.last_heartbeat_at = _now()
            await session.commit()
            return {
                "status": "updated",
                "agent_id": card.id,
                "registered_at": existing.registered_at.isoformat() if existing.registered_at else _now().isoformat(),
                "trial_status": existing.trial_status or TrialStatus.TRIAL.value,
                "free_quota_remaining": max(0, (existing.free_quota_total or DEFAULT_FREE_QUOTA) - (existing.free_quota_used or 0)),
            }

        now = _now()

        # Compute embedding from capability descriptions
        try:
            embedding = compute_agent_embedding(card.model_dump())
            embedding_blob = embed_to_blob(embedding)
        except (ValueError, TypeError):
            embedding_blob = None

        agent = Agent(
            id=card.id,
            name=card.name,
            version=card.version,
            provider_name=card.provider.name,
            provider_url=card.provider.url,
            description=card.description,
            card_json=card.model_dump_json(),
            capability_embedding=embedding_blob,
            status=AgentStatus.ACTIVE.value,
            endpoint_url=card.endpoints.task,
            auth_type=card.authentication.get("type", "none"),
            trial_status=TrialStatus.TRIAL.value,
            free_quota_total=DEFAULT_FREE_QUOTA,
            free_quota_used=0,
            health_status=HealthStatus.UNKNOWN.value,
            registered_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(agent)

        # Insert skills (capabilities)
        for cap in card.capabilities:
            skill_id = f"{card.id}/{cap.id}"
            skill = Skill(
                id=skill_id,
                agent_id=card.id,
                name=cap.name,
                description=cap.description,
                input_schema=json.dumps(cap.input_schema),
                output_schema=json.dumps(cap.output_schema),
                domains=json.dumps(cap.domains),
                execution_type=cap.execution_type,
                estimated_cost=cap.estimated_cost,
                estimated_duration=cap.estimated_duration,
            )
            session.add(skill)

        await session.commit()

        return RegisterResponse(
            status="registered",
            agent_id=card.id,
            registered_at=now,
            trial_status=TrialStatus.TRIAL,
            free_quota_remaining=DEFAULT_FREE_QUOTA,
        )


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}
# ---------------------------------------------------------------------------
@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentDetailResponse:
    """Get full agent details by ID."""
    async with async_session() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        data = await _agent_to_detail(agent, session)
        return AgentDetailResponse(**data)


# ---------------------------------------------------------------------------
# GET /agents
# ---------------------------------------------------------------------------
@router.get("/agents")
async def list_agents(
    domain: str | None = None,
    status: str | None = None,
    sort: str = "rating",
) -> list[AgentListResponse]:
    """List / filter agents by domain, status, and sort by rating."""
    async with async_session() as session:
        query = select(Agent)

        if status:
            query = query.where(Agent.status == status)

        if domain:
            # Filter agents that have a skill in the given domain
            # Use JSON_CONTAINS for safe domain matching instead of string interpolation
            query = query.where(
                Agent.id.in_(
                    select(Skill.agent_id).where(
                        Skill.domains.contains(f'"{domain}"')
                    )
                )
            )

        # Sort
        if sort == "rating":
            query = query.order_by(Agent.avg_rating.desc().nullslast())
        elif sort == "newest":
            query = query.order_by(Agent.created_at.desc().nullslast())
        elif sort == "name":
            query = query.order_by(Agent.name.asc())
        else:
            query = query.order_by(Agent.avg_rating.desc().nullslast())

        result = await session.execute(query)
        agents = result.scalars().all()

        items = []
        for agent in agents:
            data = await _agent_to_list_item(agent, session)
            items.append(AgentListResponse(**data))
        return items


# ---------------------------------------------------------------------------
# PUT /agents/{agent_id}
# ---------------------------------------------------------------------------
@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, body: UpdateAgentRequest) -> AgentDetailResponse:
    """Update an agent's ADL card. Triggers embedding recomputation."""
    async with async_session() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        if body.card_json is not None:
            # Validate and update ADL
            try:
                card = AgentCard(**body.card_json)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Invalid ADL card: {e}")

            agent.name = card.name
            agent.version = card.version
            agent.provider_name = card.provider.name
            agent.provider_url = card.provider.url
            agent.description = card.description
            agent.endpoint_url = card.endpoints.task
            agent.auth_type = card.authentication.get("type", "none")
            agent.card_json = card.model_dump_json()

            # Recompute embedding
            try:
                embedding = compute_agent_embedding(card.model_dump())
                agent.capability_embedding = embed_to_blob(embedding)
            except Exception:
                agent.capability_embedding = None

            # Replace skills
            await session.execute(
                Skill.__table__.delete().where(Skill.agent_id == agent_id)
            )
            for cap in card.capabilities:
                skill_id = f"{card.id}/{cap.id}"
                skill = Skill(
                    id=skill_id,
                    agent_id=card.id,
                    name=cap.name,
                    description=cap.description,
                    input_schema=json.dumps(cap.input_schema),
                    output_schema=json.dumps(cap.output_schema),
                    domains=json.dumps(cap.domains),
                    execution_type=cap.execution_type,
                    estimated_cost=cap.estimated_cost,
                    estimated_duration=cap.estimated_duration,
                )
                session.add(skill)

        agent.updated_at = _now()
        await session.commit()
        await session.refresh(agent)

        data = await _agent_to_detail(agent, session)
        return AgentDetailResponse(**data)


# ---------------------------------------------------------------------------
# DELETE /agents/{agent_id}
# ---------------------------------------------------------------------------
@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str) -> dict:
    """Deregister (soft-delete) an agent by setting status to 'inactive'."""
    async with async_session() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        agent.status = AgentStatus.INACTIVE.value
        agent.updated_at = _now()
        await session.commit()

        return {"status": "deregistered", "agent_id": agent_id}


# ---------------------------------------------------------------------------
# POST /agents/{agent_id}/heartbeat
# ---------------------------------------------------------------------------
@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, body: HeartbeatRequest) -> dict:
    """Agent sends heartbeat to report health status and load."""
    async with async_session() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        agent.health_status = body.status
        agent.last_heartbeat_at = _now()
        await session.commit()

        return {
            "status": "acknowledged",
            "agent_id": agent_id,
            "health_status": body.status,
            "last_heartbeat_at": agent.last_heartbeat_at,
        }
