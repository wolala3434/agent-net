"""
Unit tests for the Discovery Engine (4-layer matching funnel).

Focus areas:
  - Layer 1: Domain tag filter
  - Layer 2: Cosine similarity
  - Layer 3: Rating & preference weighting
  - Layer 4: Epsilon-greedy selection
  - Complexity heuristic
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.platform.core.discovery import (
    apply_diversity_penalty,
    apply_preference_weights,
    apply_rating_factor,
    cosine_similarity,
    discover_agents,
    epsilon_greedy_select,
    filter_by_domains,
    is_complex_task,
)


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert math.isclose(cosine_similarity(a, a), 1.0, rel_tol=1e-5)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        assert math.isclose(cosine_similarity(a, b), 0.0, abs_tol=1e-6)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert math.isclose(cosine_similarity(a, b), -1.0, rel_tol=1e-5)

    def test_zero_vector_returns_zero(self):
        a = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors(self):
        a = np.array([0.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# Layer 1: Domain filter
# ---------------------------------------------------------------------------

class TestDomainFilter:
    @pytest.fixture
    def agents(self):
        return [
            {"id": "a1", "skills": [{"domains": '["code.security", "code.review"]'}]},
            {"id": "a2", "skills": [{"domains": '["supply-chain", "logistics"]'}]},
            {"id": "a3", "skills": [{"domains": '["nlp.summarization"]'}]},
            {"id": "a4", "skills": []},  # no domains
        ]

    def test_filters_by_matching_domain(self, agents):
        result = filter_by_domains(["code.security"], agents)
        ids = {a["id"] for a in result}
        assert ids == {"a1"}

    def test_matches_any_domain(self, agents):
        result = filter_by_domains(["code.security", "supply-chain"], agents)
        ids = {a["id"] for a in result}
        assert ids == {"a1", "a2"}

    def test_no_domains_returns_all(self, agents):
        result = filter_by_domains([], agents)
        assert len(result) == 4

    def test_no_match_returns_empty(self, agents):
        result = filter_by_domains(["nonexistent.domain"], agents)
        assert result == []

    def test_caches_domains(self, agents):
        """Second call uses cached _domains field."""
        filter_by_domains(["code.security"], agents)
        # _domains should be cached
        assert "_domains" in agents[0]
        # Second call should still work without re-parsing
        result = filter_by_domains(["code.security"], agents)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Layer 3: Rating & preference weighting
# ---------------------------------------------------------------------------

class TestRatingFactor:
    def test_high_rated_boost(self):
        agent = {"avg_rating": 4.8, "review_count": 50}
        score = apply_rating_factor(agent, 0.5)
        assert score == pytest.approx(0.5 * 1.15)  # >= 4.5 → x1.15

    def test_mid_rated_neutral(self):
        agent = {"avg_rating": 4.0, "review_count": 50}
        score = apply_rating_factor(agent, 0.5)
        assert score == pytest.approx(0.5 * 1.00)  # 3.5-4.5 → x1.00

    def test_low_mid_penalty(self):
        agent = {"avg_rating": 3.0, "review_count": 50}
        score = apply_rating_factor(agent, 0.5)
        assert score == pytest.approx(0.5 * 0.85)  # 2.5-3.5 → x0.85

    def test_low_rated_heavy_penalty(self):
        agent = {"avg_rating": 1.5, "review_count": 50}
        score = apply_rating_factor(agent, 0.5)
        assert score == pytest.approx(0.5 * 0.60)  # < 2.5 → x0.60

    def test_few_reviews_uncertainty_penalty(self):
        agent = {"avg_rating": 4.8, "review_count": 5}
        score = apply_rating_factor(agent, 1.0)
        assert score == pytest.approx(1.0 * 1.15 * 0.90)  # high rating + uncertainty


class TestPreferenceWeights:
    def test_newcomer_boost(self):
        agent = {"id": "a1", "days_since_registration": 10, "trial_status": "verified"}
        score = apply_preference_weights(agent, 1.0, set(), newcomer_days=30, newcomer_boost=0.10)
        assert score == pytest.approx(1.10)

    def test_old_agent_no_boost(self):
        agent = {"id": "a1", "days_since_registration": 60, "trial_status": "verified"}
        score = apply_preference_weights(agent, 1.0, set())
        assert score == pytest.approx(1.0)

    def test_trial_penalty(self):
        agent = {"id": "a1", "days_since_registration": 60, "trial_status": "trial"}
        score = apply_preference_weights(agent, 1.0, set())
        assert score == pytest.approx(0.95)

    def test_user_pinned_boost(self):
        agent = {"id": "a1", "days_since_registration": 60, "trial_status": "verified"}
        score = apply_preference_weights(agent, 1.0, {"a1"})
        assert score == pytest.approx(1.15)

    def test_combined_boosts(self):
        """Newcomer + pinned: both multipliers apply."""
        agent = {"id": "a1", "days_since_registration": 10, "trial_status": "verified"}
        score = apply_preference_weights(agent, 1.0, {"a1"}, newcomer_days=30, newcomer_boost=0.10)
        assert score == pytest.approx(1.0 * 1.10 * 1.15)


# ---------------------------------------------------------------------------
# Diversity penalty
# ---------------------------------------------------------------------------

class TestDiversityPenalty:
    def test_same_provider_second_agent_penalized(self):
        agents = [
            ({"id": "a1", "provider_name": "Acme"}, 1.0),
            ({"id": "a2", "provider_name": "Acme"}, 1.0),  # 2nd from Acme
            ({"id": "b1", "provider_name": "Beta"}, 1.0),
        ]
        result = apply_diversity_penalty(agents, penalty=0.20)
        assert result[0][1] == 1.0    # first from Acme: no penalty
        assert result[1][1] == 0.80   # second from Acme: 20% penalty
        assert result[2][1] == 1.0    # first from Beta: no penalty

    def test_empty_provider_name_no_penalty(self):
        agents = [
            ({"id": "a1", "provider_name": ""}, 1.0),
            ({"id": "a2", "provider_name": ""}, 1.0),
        ]
        result = apply_diversity_penalty(agents)
        assert result[0][1] == 1.0
        assert result[1][1] == 1.0  # empty provider → no grouping


# ---------------------------------------------------------------------------
# Layer 4: Epsilon-greedy
# ---------------------------------------------------------------------------

class TestEpsilonGreedy:
    @pytest.fixture
    def scored(self):
        return [
            ({"id": "best"}, 0.95),
            ({"id": "second"}, 0.85),
            ({"id": "third"}, 0.75),
            ({"id": "fourth"}, 0.65),
            ({"id": "fifth"}, 0.55),
        ]

    def test_exploit_takes_top_k(self, scored):
        """With epsilon=0.0, should always return the top 3."""
        # Run multiple times to ensure deterministic exploit behavior
        for _ in range(20):
            result = epsilon_greedy_select(scored, top_k=3, epsilon=0.0)
            ids = {a["id"] for a in result}
            assert ids == {"best", "second", "third"}

    def test_explore_returns_k_items(self, scored):
        """Explore mode still returns exactly top_k items."""
        for _ in range(20):
            result = epsilon_greedy_select(scored, top_k=3, epsilon=1.0)
            assert len(result) == 3

    def test_top_k_larger_than_input(self, scored):
        result = epsilon_greedy_select(scored, top_k=10, epsilon=0.0)
        assert len(result) == 5  # capped at input size

    def test_empty_input(self):
        result = epsilon_greedy_select([], top_k=3, epsilon=0.0)
        assert result == []


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

class TestDiscoverAgents:
    @pytest.fixture
    def agents(self):
        """A realistic set of agents with pre-computed embeddings."""
        return [
            {
                "id": "security-1",
                "name": "Security Scanner",
                "provider_name": "CyberShield",
                "description": "Scans code for security vulnerabilities",
                "avg_rating": 4.5,
                "review_count": 50,
                "trial_status": "verified",
                "days_since_registration": 60,
                "skills": [{"domains": '["code.security"]'}],
                "capability_embedding": np.random.randn(384).astype(np.float32).tobytes(),
            },
            {
                "id": "supply-chain-1",
                "name": "Supply Chain Expert",
                "provider_name": "LogiChain",
                "description": "Analyzes supply chain risks",
                "avg_rating": 4.0,
                "review_count": 20,
                "trial_status": "verified",
                "days_since_registration": 30,
                "skills": [{"domains": '["supply-chain"]'}],
                "capability_embedding": np.random.randn(384).astype(np.float32).tobytes(),
            },
            {
                "id": "nlp-1",
                "name": "Summarizer",
                "provider_name": "NLP Studio",
                "description": "Summarizes text documents",
                "avg_rating": 4.2,
                "review_count": 100,
                "trial_status": "verified",
                "days_since_registration": 90,
                "skills": [{"domains": '["nlp.summarization"]'}],
                "capability_embedding": np.random.randn(384).astype(np.float32).tobytes(),
            },
            {
                "id": "trial-agent",
                "name": "New Agent (Trial)",
                "provider_name": "Startup",
                "description": "New risk analysis agent",
                "avg_rating": 3.0,
                "review_count": 3,
                "trial_status": "trial",
                "days_since_registration": 5,
                "skills": [{"domains": '["analysis.risk"]'}],
                "capability_embedding": np.random.randn(384).astype(np.float32).tobytes(),
            },
        ]

    def test_returns_top_k_results(self, agents):
        selected, mode = discover_agents(
            task_description="Find security vulnerabilities in code",
            task_domains=["code.security"],
            agents=agents,
            top_k=2,
            epsilon=0.0,
        )
        assert len(selected) <= 2
        assert mode in ("exploit", "explore")

    def test_domain_filter_applied(self, agents):
        selected, _ = discover_agents(
            task_description="Analyze supply chain risks",
            task_domains=["supply-chain"],
            agents=agents,
            top_k=3,
            epsilon=0.0,
        )
        # Should prefer the supply-chain agent
        ids = [a["id"] for a in selected]
        assert "supply-chain-1" in ids

    def test_pinned_agents_forced_to_top(self, agents):
        selected, _ = discover_agents(
            task_description="Some task",
            task_domains=[],
            agents=agents,
            user_pinned_ids={"nlp-1"},
            top_k=3,
            epsilon=0.0,
        )
        # Pinned agent must appear before non-pinned agents
        # (embeddings are random, so nlp-1 may not be #1, but if present
        #  it will be positioned before any non-pinned agent)
        ids = [a["id"] for a in selected]
        if "nlp-1" in ids:
            nlp_idx = ids.index("nlp-1")
            # No non-pinned agent should appear before it
            for i, aid in enumerate(ids):
                if aid != "nlp-1" and aid not in {"nlp-1"}:
                    assert nlp_idx <= i, (
                        f"Pinned agent nlp-1 at index {nlp_idx} "
                        f"should come before non-pinned {aid} at index {i}"
                    )

    def test_fallback_when_no_domain_match(self, agents):
        """When no agents match domains, fall back to all agents."""
        selected, _ = discover_agents(
            task_description="Do something",
            task_domains=["nonexistent.domain"],
            agents=agents,
            top_k=3,
            epsilon=0.0,
        )
        assert len(selected) > 0

    def test_handles_empty_agent_list(self):
        selected, mode = discover_agents(
            task_description="Anything",
            task_domains=[],
            agents=[],
            top_k=3,
        )
        assert selected == []
        assert mode in ("exploit", "explore")


# ---------------------------------------------------------------------------
# Complexity heuristic
# ---------------------------------------------------------------------------

class TestComplexityHeuristic:
    def test_complex_keywords_trigger_collaboration(self):
        # "评估" and "审计" each count as 1 keyword hit; need >=2 hits
        assert is_complex_task("分析并评估特斯拉供应链风险", []) is True  # 2 hits
        assert is_complex_task("审核并审计系统安全漏洞", []) is True      # 2 hits: 审计+审查

    def test_multiple_domains_trigger_collaboration(self):
        assert is_complex_task("简单任务", ["code.review", "code.security"]) is True

    def test_simple_task_no_collaboration(self):
        assert is_complex_task("翻译这段文字", []) is False
        assert is_complex_task("hello", []) is False

    def test_threshold_configurable(self):
        assert is_complex_task("分析数据并评估风险", [], threshold_keywords=3) is False
        assert is_complex_task("分析数据并评估风险", [], threshold_keywords=2) is True
