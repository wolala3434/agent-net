"""Rating & reviews — per api-spec.md 5."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from ..database import async_session
from ..models import Agent, AgentReview
from ..schemas import ReviewRequest, ReviewResponse
from ..constants import DEFAULT_USER_ID

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# POST /reviews
# ---------------------------------------------------------------------------
@router.post("/reviews", status_code=201)
async def submit_review(body: ReviewRequest) -> ReviewResponse:
    """
    Submit a rating (1-5) and optional text review for an agent.

    Validates:
      - Agent exists
      - User+task uniqueness (one review per task per user)
      - Rating is between 1 and 5
    """
    async with async_session() as session:
        # Check agent exists
        agent = await session.get(Agent, body.agent_id)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{body.agent_id}' not found",
            )

        now = _now()

        review = AgentReview(
            agent_id=body.agent_id,
            user_id=body.user_id if body.user_id else DEFAULT_USER_ID,
            task_id=body.task_id,
            session_id=body.session_id,
            rating=body.rating,
            review_text=body.review_text,
            created_at=now,
            updated_at=now,
        )
        session.add(review)

        try:
            await session.commit()
            await session.refresh(review)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Review already exists for this user+task combination",
            )

        # Recalculate agent's avg_rating
        agg_result = await session.execute(
            select(
                func.avg(AgentReview.rating).label("avg_r"),
                func.count(AgentReview.id).label("cnt"),
            ).where(AgentReview.agent_id == body.agent_id)
        )
        row = agg_result.one()
        new_avg = float(row.avg_r) if row.avg_r else 0.0

        agent.avg_rating = round(new_avg, 2)
        agent.updated_at = now
        await session.commit()

        return ReviewResponse(
            id=review.id,
            agent_id=review.agent_id,
            user_id=review.user_id,
            task_id=review.task_id,
            session_id=review.session_id,
            rating=review.rating,
            review_text=review.review_text,
            created_at=review.created_at,
            updated_at=review.updated_at,
        )


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/reviews
# ---------------------------------------------------------------------------
@router.get("/agents/{agent_id}/reviews")
async def get_agent_reviews(
    agent_id: str,
    sort: str = "recent",
    limit: int = 20,
) -> list[ReviewResponse]:
    """Get reviews for an agent, sorted by most recent or highest rating."""
    async with async_session() as session:
        query = (
            select(AgentReview)
            .where(AgentReview.agent_id == agent_id)
        )

        if sort == "recent":
            query = query.order_by(AgentReview.created_at.desc())
        elif sort == "rating":
            query = query.order_by(AgentReview.rating.desc())
        else:
            query = query.order_by(AgentReview.created_at.desc())

        query = query.limit(min(limit, 100))
        result = await session.execute(query)
        reviews = result.scalars().all()

        return [
            ReviewResponse(
                id=r.id,
                agent_id=r.agent_id,
                user_id=r.user_id,
                task_id=r.task_id,
                session_id=r.session_id,
                rating=r.rating,
                review_text=r.review_text,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in reviews
        ]


# ---------------------------------------------------------------------------
# GET /users/{user_id}/reviews
# ---------------------------------------------------------------------------
@router.get("/users/{user_id}/reviews")
async def get_user_reviews(user_id: str) -> list[ReviewResponse]:
    """Get all reviews submitted by a specific user."""
    async with async_session() as session:
        result = await session.execute(
            select(AgentReview)
            .where(AgentReview.user_id == user_id)
            .order_by(AgentReview.created_at.desc())
        )
        reviews = result.scalars().all()

        return [
            ReviewResponse(
                id=r.id,
                agent_id=r.agent_id,
                user_id=r.user_id,
                task_id=r.task_id,
                session_id=r.session_id,
                rating=r.rating,
                review_text=r.review_text,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in reviews
        ]
