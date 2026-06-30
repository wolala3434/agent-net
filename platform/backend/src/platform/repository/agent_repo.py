"""AgentRepository — unified Agent, Skill, Review queries."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Agent, Skill, AgentReview, UserPinnedAgent
from ..constants import AgentStatus


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentRepository:

    @staticmethod
    async def get_active_agents(db: AsyncSession) -> list[Agent]:
        """Return all agents with status == 'active'."""
        result = await db.execute(
            select(Agent).where(Agent.status == AgentStatus.ACTIVE.value)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_agent_by_id(db: AsyncSession, agent_id: str) -> Agent | None:
        """Fetch a single agent by ID."""
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_skills_for_agent(db: AsyncSession, agent_id: str) -> list[Skill]:
        """Return all skills for a given agent."""
        result = await db.execute(
            select(Skill).where(Skill.agent_id == agent_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_review_count(db: AsyncSession, agent_id: str) -> int:
        """Return the number of reviews for an agent."""
        result = await db.execute(
            select(func.count(AgentReview.id)).where(
                AgentReview.agent_id == agent_id
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def get_pinned_agent_ids(db: AsyncSession, user_id: str) -> set[str]:
        """Return the set of agent IDs pinned by a user."""
        result = await db.execute(
            select(UserPinnedAgent.agent_id).where(
                UserPinnedAgent.user_id == user_id
            )
        )
        return set(result.scalars().all())

    @staticmethod
    async def build_discovery_payload(
        db: AsyncSession, agent: Agent
    ) -> dict[str, Any]:
        """Build a complete discovery-engine-ready dict from an Agent ORM row.

        This is the **single method** that replaces the duplicated ~75-line
        manual build loops in api/discovery.py and session_manager.py.

        Returns a dict with keys:
          id, name, provider_name, description, capability_embedding,
          avg_rating, review_count, trial_status, days_since_registration,
          pricing, skills, _domains
        """
        # --- skills + domains ---
        skills = await AgentRepository.get_skills_for_agent(db, agent.id)
        skill_dicts: list[dict[str, Any]] = []
        all_domains: set[str] = set()
        for s in skills:
            skill_dicts.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "domains": s.domains,
            })
            try:
                all_domains.update(json.loads(s.domains))
            except (json.JSONDecodeError, TypeError):
                pass

        # --- embedding ---
        emb = agent.capability_embedding
        if emb is not None and isinstance(emb, bytes):
            capability_embedding = emb
        elif emb is not None and isinstance(emb, str):
            try:
                capability_embedding = bytes.fromhex(emb)
            except (ValueError, TypeError):
                capability_embedding = None
        else:
            capability_embedding = None

        # --- days since registration ---
        days_since = 999
        if agent.registered_at:
            delta = _now() - agent.registered_at
            days_since = delta.days

        # --- review count ---
        review_count = await AgentRepository.get_review_count(db, agent.id)

        # --- pricing from card_json ---
        pricing: dict[str, Any] = {}
        try:
            card = json.loads(agent.card_json) if agent.card_json else {}
            pricing = card.get("pricing", {})
        except (json.JSONDecodeError, TypeError):
            pass

        return {
            "id": agent.id,
            "name": agent.name,
            "provider_name": agent.provider_name or "",
            "description": agent.description or "",
            "capability_embedding": capability_embedding,
            "avg_rating": agent.avg_rating,
            "review_count": review_count,
            "trial_status": agent.trial_status,
            "days_since_registration": days_since,
            "endpoint_url": agent.endpoint_url,
            "pricing": pricing,
            "skills": skill_dicts,
            "_domains": all_domains,
        }

    @staticmethod
    async def get_all_active_with_discovery_payloads(
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Bulk: fetch all active agents and build full discovery payloads.

        One call replaces the entire manual for-loop in api/discovery.py.
        """
        agents = await AgentRepository.get_active_agents(db)
        payloads = []
        for a in agents:
            payloads.append(await AgentRepository.build_discovery_payload(db, a))
        return payloads
