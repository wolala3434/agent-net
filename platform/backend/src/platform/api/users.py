"""User pinned agents — per api-spec.md 7."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import async_session
from ..models import Agent, UserPinnedAgent
from ..schemas import PinAgentRequest, PinAgentResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /users/{user_id}/pinned-agents
# ---------------------------------------------------------------------------
@router.post("/users/{user_id}/pinned-agents", status_code=201)
async def pin_agent(user_id: str, body: PinAgentRequest) -> PinAgentResponse:
    """Pin/favorite an agent for quick access and search boost."""
    async with async_session() as session:
        # Check agent exists
        agent = await session.get(Agent, body.agent_id)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{body.agent_id}' not found",
            )

        # Check not already pinned
        existing = await session.execute(
            select(UserPinnedAgent).where(
                UserPinnedAgent.user_id == user_id,
                UserPinnedAgent.agent_id == body.agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Agent already pinned by this user",
            )

        pin = UserPinnedAgent(
            user_id=user_id,
            agent_id=body.agent_id,
            note=body.note,
        )
        session.add(pin)

        try:
            await session.commit()
            await session.refresh(pin)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Agent already pinned by this user",
            )

        return PinAgentResponse(
            id=pin.id,
            user_id=pin.user_id,
            agent_id=pin.agent_id,
            agent_name=agent.name,
            pinned_at=pin.pinned_at,
            note=pin.note,
        )


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/pinned-agents/{agent_id}
# ---------------------------------------------------------------------------
@router.delete("/users/{user_id}/pinned-agents/{agent_id}")
async def unpin_agent(user_id: str, agent_id: str) -> dict:
    """Remove a pinned agent."""
    async with async_session() as session:
        result = await session.execute(
            select(UserPinnedAgent).where(
                UserPinnedAgent.user_id == user_id,
                UserPinnedAgent.agent_id == agent_id,
            )
        )
        pin = result.scalar_one_or_none()
        if not pin:
            raise HTTPException(
                status_code=404,
                detail="Pinned agent not found",
            )

        await session.delete(pin)
        await session.commit()

        return {
            "status": "unpinned",
            "user_id": user_id,
            "agent_id": agent_id,
        }


# ---------------------------------------------------------------------------
# GET /users/{user_id}/pinned-agents
# ---------------------------------------------------------------------------
@router.get("/users/{user_id}/pinned-agents")
async def list_pinned_agents(user_id: str) -> list[PinAgentResponse]:
    """List all agents pinned by a user."""
    async with async_session() as session:
        result = await session.execute(
            select(UserPinnedAgent)
            .where(UserPinnedAgent.user_id == user_id)
            .order_by(UserPinnedAgent.pinned_at.desc())
        )
        pins = result.scalars().all()

        response_items = []
        for pin in pins:
            agent = await session.get(Agent, pin.agent_id)
            response_items.append(
                PinAgentResponse(
                    id=pin.id,
                    user_id=pin.user_id,
                    agent_id=pin.agent_id,
                    agent_name=agent.name if agent else None,
                    pinned_at=pin.pinned_at,
                    note=pin.note,
                )
            )
        return response_items
