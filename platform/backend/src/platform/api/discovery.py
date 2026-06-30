"""Agent discovery & search — per api-spec.md 2."""

from __future__ import annotations

from fastapi import APIRouter

from ..database import async_session
from ..schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryMatch,
    SearchMode,
    TrialStatus,
)
from ..core.discovery import discover_agents
from ..repository import AgentRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /discovery/search
# ---------------------------------------------------------------------------
@router.post("/discovery/search")
async def search_agents(req: DiscoveryRequest) -> DiscoveryResponse:
    """
    Search for agents matching a task description.

    Uses the 4-layer matching funnel:
      Layer 1: Domain tag filter
      Layer 2: Embedding semantic sort
      Layer 3: Rating & preference weighting
      Layer 4: epsilon-greedy explore/exploit

    Request body:
      - description: Natural language task description
      - domains: Optional domain tags for coarse filter
      - top_k: Number of results (default 3)
      - user_id: Optional user ID for pinned-agent boost
    """
    async with async_session() as session:
        # Fetch all active agents and build discovery payloads via repository
        agent_dicts = await AgentRepository.get_all_active_with_discovery_payloads(session)

        if not agent_dicts:
            return DiscoveryResponse(matches=[], search_mode=SearchMode.exploit)

        # Get user's pinned agents if user_id provided
        pinned_ids: set[str] = set()
        if req.user_id:
            pinned_ids = await AgentRepository.get_pinned_agent_ids(session, req.user_id)

        # Run the discovery funnel
        selected, mode = discover_agents(
            task_description=req.description,
            task_domains=req.domains,
            agents=agent_dicts,
            user_pinned_ids=pinned_ids,
            top_k=req.top_k,
        )

        # Build response
        matches = []
        for a in selected:
            avg_rating = a.get("avg_rating", 0.0)
            trial_status_str = a.get("trial_status", TrialStatus.TRIAL.value)
            try:
                trial_status = TrialStatus(trial_status_str)
            except ValueError:
                trial_status = TrialStatus.TRIAL

            reason_list = []
            if set(req.domains) & a.get("_domains", set()):
                reason_list.append("domain_match")
            if a.get("avg_rating", 0) >= 4.0 and a.get("review_count", 0) > 10:
                reason_list.append("high_rating")
            reason_list.append("semantic_similarity")
            if a["id"] in pinned_ids:
                reason_list.append("user_pinned")

            matches.append(
                DiscoveryMatch(
                    agent_id=a["id"],
                    agent_name=a.get("name", a["id"]),
                    score=0.0,  # Will be populated post-selection
                    match_reasons=reason_list,
                    avg_rating=avg_rating,
                    trial_status=trial_status,
                    pricing=a.get("pricing", {}),
                )
            )

        mode_enum = SearchMode.exploit if mode == "exploit" else SearchMode.explore

        return DiscoveryResponse(matches=matches, search_mode=mode_enum)
