"""
Discovery Engine — 4-layer matching funnel.

Layer 1: Domain tag filter (SQL, <10ms)        5000 → 200
Layer 2: Embedding semantic sort (<1s)         200 → top 20
Layer 3: Rating & preference weighting          top 20 re-ranked
Layer 4: ε-greedy explore/exploit               → final top 3

Key design rules:
  - Rating factor: >=4.5 -> x1.15, <2.5 -> x0.60, <10 reviews -> x0.90
  - Newcomer boost: <30 days since registration -> x1.10
  - User pinned agents: x1.15 and force pin to top
  - Trial status: 'trial' agents get x0.95
  - Diversity: same provider's 2nd+ agent -> x0.80
  - epsilon=0.15: 85% exploit, 15% explore
"""

from __future__ import annotations

import json
import random
from typing import Any

import numpy as np

from .embeddings import blob_to_embed, compute_embedding
from ..constants import (
    TrialStatus,
    RATING_EXCELLENT_THRESHOLD,
    RATING_GOOD_THRESHOLD,
    RATING_POOR_THRESHOLD,
    RATING_EXCELLENT_MULTIPLIER,
    RATING_GOOD_MULTIPLIER,
    RATING_POOR_MULTIPLIER,
    RATING_BAD_MULTIPLIER,
    LOW_REVIEW_COUNT_THRESHOLD,
    LOW_REVIEW_PENALTY,
)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two embedding vectors.

    Handles zero-vector edge case gracefully.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def filter_by_domains(
    task_domains: list[str],
    agents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Layer 1: Coarse domain-tag filter.

    NOTE: Because skills.domains is stored as a JSON-array TEXT column,
    we filter in Python rather than SQL. The migration
    001_fix_domains_index.sql adds a normalized `agent_domains` table
    that allows proper indexed SQL queries at scale.
    """
    if not task_domains:
        return agents

    candidates = []
    for agent in agents:
        agent_domains = agent.get("_domains", set())
        if not agent_domains:
            # Fallback: extract from skills
            agent_domains = set()
            for skill in agent.get("skills", []):
                domains_raw = skill.get("domains", "[]")
                if isinstance(domains_raw, str):
                    agent_domains.update(json.loads(domains_raw))
                else:
                    agent_domains.update(domains_raw)
            agent["_domains"] = agent_domains  # Cache for speed
        if agent_domains & set(task_domains):
            candidates.append(agent)
    return candidates


def apply_rating_factor(agent: dict[str, Any], score: float) -> float:
    """Apply rating multiplier per rating-factor rules.

    - avg_rating >= 4.5: x1.15
    - avg_rating < 2.5: x0.60
    - < 10 reviews: x0.90 (uncertainty penalty)
    """
    avg_rating = agent.get("avg_rating", 0.0)
    review_count = agent.get("review_count", 0)

    if avg_rating >= RATING_EXCELLENT_THRESHOLD:
        score *= RATING_EXCELLENT_MULTIPLIER
    elif avg_rating >= RATING_GOOD_THRESHOLD:
        score *= RATING_GOOD_MULTIPLIER
    elif avg_rating >= RATING_POOR_THRESHOLD:
        score *= RATING_POOR_MULTIPLIER
    else:
        score *= RATING_BAD_MULTIPLIER

    if review_count < LOW_REVIEW_COUNT_THRESHOLD:
        score *= LOW_REVIEW_PENALTY

    return score


def apply_preference_weights(
    agent: dict[str, Any],
    score: float,
    user_pinned_ids: set[str],
    newcomer_days: int = 30,
    newcomer_boost: float = 0.10,
) -> float:
    """Layer 3: preference weighting.

    - Newcomer boost (<30 days): x1.10
    - Trial status penalty: x0.95
    - User pinned boost: x1.15
    """
    # Newcomer boost
    days_registered = agent.get("days_since_registration", 999)
    if days_registered < newcomer_days:
        score *= (1.0 + newcomer_boost)

    # Trial status penalty (protect users from untested agents)
    if agent.get("trial_status") == TrialStatus.TRIAL.value:
        score *= 0.95

    # User pinned boost
    if agent["id"] in user_pinned_ids:
        score *= 1.15

    return score


def apply_diversity_penalty(
    scored: list[tuple[dict[str, Any], float]],
    penalty: float = 0.20,
) -> list[tuple[dict[str, Any], float]]:
    """Apply diversity penalty: same provider's 2nd+ agent gets x0.80.

    Uses a flat penalty multiplier rather than cumulative, per the spec:
    'same provider's 2nd agent onwards gets x0.80'.
    """
    seen_providers: dict[str, int] = {}
    result = []
    for agent, score in scored:
        provider = agent.get("provider_name", "")
        if provider:
            seen_providers[provider] = seen_providers.get(provider, 0) + 1
            if seen_providers[provider] > 1:
                score *= (1.0 - penalty)  # flat 0.80 multiplier for 2nd+
        result.append((agent, score))
    return result


def epsilon_greedy_select(
    scored: list[tuple[dict[str, Any], float]],
    top_k: int = 3,
    epsilon: float = 0.15,
) -> list[dict[str, Any]]:
    """Layer 4: epsilon-greedy explore/exploit.

    - exploit (85%): take top-k by score
    - explore (15%): weighted random sample
    """
    if random.random() < epsilon:
        # Explore: weighted random sample
        agents_list = [a for a, _ in scored]
        scores_list = [s for _, s in scored]
        total = sum(scores_list)
        weights = [s / total for s in scores_list] if total > 0 else None
        k = min(top_k, len(scored))
        if k == 0:
            return []
        indices = np.random.choice(
            len(scored), size=k, replace=False, p=weights
        )
        selected = [agents_list[i] for i in indices]
    else:
        # Exploit: take top-k
        selected = [agent for agent, _ in scored[:top_k]]

    return selected


def _get_embedding(agent: dict[str, Any]) -> np.ndarray:
    """Extract embedding from agent dict, handling both raw bytes and list formats."""
    emb = agent.get("capability_embedding")
    if emb is None:
        return np.zeros(384, dtype=np.float32)
    if isinstance(emb, bytes):
        return blob_to_embed(emb)
    if isinstance(emb, (list, np.ndarray)):
        return np.asarray(emb, dtype=np.float32)
    return np.zeros(384, dtype=np.float32)


def discover_agents(
    task_description: str,
    task_domains: list[str],
    agents: list[dict[str, Any]],
    embed_fn=None,
    user_pinned_ids: set[str] | None = None,
    top_k: int = 3,
    epsilon: float | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Full discovery pipeline: domain filter -> embedding -> weighting -> epsilon-greedy.

    Parameters:
        task_description: Natural language task description for embedding match.
        task_domains: Domain tags for Layer 1 coarse filter.
        agents: List of agent dicts with 'id', 'avg_rating', 'trial_status', etc.
        embed_fn: Optional embedding function (defaults to compute_embedding).
        user_pinned_ids: Set of agent IDs pinned by the requesting user.
        top_k: Number of results to return.
        epsilon: Explore probability (0.0 = pure exploit, 1.0 = pure explore).
                 If None, falls back to settings.discovery_epsilon.

    Returns:
        (selected_agents, mode) where mode is "exploit" or "explore".
    """
    from ..config import settings

    if embed_fn is None:
        embed_fn = compute_embedding
    if user_pinned_ids is None:
        user_pinned_ids = set()
    if epsilon is None:
        epsilon = settings.discovery_epsilon

    # Layer 1: Domain filter
    candidates = filter_by_domains(task_domains, agents)
    if not candidates:
        candidates = agents  # fallback to all if nothing matches domain

    # Layer 2: Embedding sort
    task_emb = embed_fn(task_description)
    scored = [(a, cosine_similarity(task_emb, _get_embedding(a)))
              for a in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    top20 = scored[:20]

    # Layer 3: Rating + preference weighting
    weighted = []
    for agent, score in top20:
        score = apply_rating_factor(agent, score)
        score = apply_preference_weights(agent, score, user_pinned_ids)
        weighted.append((agent, score))

    weighted = apply_diversity_penalty(weighted)
    weighted.sort(key=lambda x: x[1], reverse=True)

    # Layer 4: epsilon-greedy
    selected = epsilon_greedy_select(weighted, top_k=top_k, epsilon=epsilon)

    # Pinned agents always on top (force pin)
    pinned = [a for a in selected if a["id"] in user_pinned_ids]
    others = [a for a in selected if a["id"] not in user_pinned_ids]
    selected = pinned + others

    # Determine mode string based on actual selection vs greedy pick
    greedy_top = [a for a, _ in weighted[:top_k]]
    mode = "exploit" if selected == greedy_top else "explore"

    return selected[:top_k], mode


# ---------------------------------------------------------------------------
# Complexity heuristic — determines single-agent vs collaboration mode.
# ---------------------------------------------------------------------------
def is_complex_task(
    description: str,
    domains: list[str],
    threshold_keywords: int = 2,
) -> bool:
    """
    Heuristic for auto-complexity detection (api-spec.md / aip-protocol.md path 2).

    Returns True if the task likely needs multiple agents.
    MVP: keyword-based. Can be upgraded to LLM-based classification.
    """
    complexity_keywords = [
        "分析", "评估", "比较", "审计", "审查", "审核",
        "analyze", "assess", "compare", "audit", "review",
        "跨领域", "多方面", "综合", "端到端",
        "cross-domain", "multi-faceted", "comprehensive", "end-to-end",
    ]
    hits = sum(1 for kw in complexity_keywords if kw.lower() in description.lower())
    # Multiple domains also suggest complexity
    domain_signal = len(domains) >= 2
    return hits >= threshold_keywords or domain_signal
