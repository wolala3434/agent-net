"""Supply Chain Expert — Demo Agent (:9122).

A supply-chain data and industry-insight specialist that evaluates raw
material pricing, supply diversification, and technology trends.  Uses
AgentBase (class mode) for collaboration participation.

Domain: supply-chain
Skill:  supply-chain-analysis

Expected collaboration flow (Tesla demo):
  Turn 1 Analyst  → propose (6.5/10)        → Expert audits, critiques
  Turn 2 Expert   → critique                → Analyst clarifies
  Turn 3 Analyst  → clarify                 → Expert provides data
  Turn 4 Expert   → refine (S&P data)       → Analyst recalculates
  Turn 5 Analyst  → refine (5.0/10)         → Expert agrees + LFP insight
  Turn 6 Expert   → agree                   → Analyst synthesises
  Turn 7 Analyst  → synthesize              → Expert agrees
"""

from __future__ import annotations

import argparse
import time

from agent_internet import Skill, serve
from collaborative_agent_base import CollaborativeAgentBase

# ---------------------------------------------------------------------------
# Mock supply-chain data for Tesla
# ---------------------------------------------------------------------------
TESLA_SUPPLY_CHAIN = {
    "company": "Tesla",
    "risk_score": 4.5,
    "factors": [
        {
            "name": "锂供应",
            "score": 4.0,
            "trend": "improving",
            "detail": (
                "S&P Global 2026年5月数据显示锂价实际下跌8%，"
                "Tesla得州工厂自供比例达35%（Q1 2026财报）"
            ),
        },
        {
            "name": "LFP渗透率",
            "score": 3.0,
            "trend": "accelerating",
            "detail": "磷酸铁锂电池在4680电池中渗透率达30%，降低对钴镍依赖",
        },
        {
            "name": "物流风险",
            "score": 5.0,
            "trend": "stable",
            "detail": "全球航运成本已回落到疫情前水平，物流风险可控",
        },
        {
            "name": "供应商多元化",
            "score": 4.5,
            "trend": "improving",
            "detail": "CATL墨西哥工厂2026年5月投产，BYD潜在供应协议谈判中",
        },
    ],
    "summary": (
        "Tesla在Q2 2026的供应链风险评分为4.5/10，"
        "处于中等偏低风险区间，锂价下跌和LFP渗透率提升为主因"
    ),
}

EXPERT_KNOWLEDGE = {
    "lithium": {
        "source": "S&P Global Market Intelligence",
        "timeframe": "2026年4-5月",
        "price_trend": "下跌8%，电池级碳酸锂从Q1均价￥115,000/吨降至￥106,000/吨",
        "tesla_self_supply": "Texas工厂自供比例达35%（Q1 2026财报披露）",
        "additional": "Liontown Resources Kathleen Valley项目2025年Q4投产增加供应",
    },
    "cobalt": {
        "source": "DRC海关出口统计 + S&P Global",
        "dependency": "67%来自刚果(金)",
        "trend": "LFP渗透率提升降低钴需求，2026年全球钴需求增速放缓至3%",
        "mitigation": "Tesla正从Australia和Canada探索替代钴源",
    },
    "lfp": {
        "penetration_4680": "30%",
        "trend": "accelerating",
        "detail": "CATL和BYD的LFP产能持续扩张，2026年全球LFP出货量预计增长40%",
        "upside_scenario": "若4680中LFP达60%，锂需求结构的确定性增强，风险评分为3.5/10",
    },
    "supplier_diversification": {
        "catl_mexico": "2026年5月投产，年产能50GWh",
        "byd_negotiation": "潜在供应协议谈判中",
        "panasonic": "日本工厂2026年产能提升至45GWh",
    },
}


class SupplyChainExpert(CollaborativeAgentBase):
    """Supply chain data specialist — raw materials, logistics, tech trends.

    Works both standalone (``handle_single_task``) and in collaboration
    sessions (``handle_collaboration_message``).
    """

    def __init__(self) -> None:
        super().__init__(
            name="Supply Chain Expert",
            version="1.0.0",
            description="供应链数据分析和行业洞察，评估原材料价格和供应风险",
            provider={
                "name": "Agent Internet Demo",
                "contact": "demo@agentinternet.io",
            },
            skills=[
                Skill(
                    id="supply-chain-analysis",
                    name="供应链分析",
                    domains=["supply-chain"],
                    input_schema={
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "material": {"type": "string"},
                        },
                        "required": ["company"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "risk_score": {"type": "number"},
                            "factors": {"type": "array"},
                        },
                        "required": ["risk_score", "factors"],
                    },
                )
            ],
            pricing={"model": "per_call", "unit_price": 0.50},
        )

    # ------------------------------------------------------------------
    # Single-agent mode
    # ------------------------------------------------------------------
    async def handle_single_task(self, task: dict) -> dict:
        """Return supply-chain data for a given company and optional material."""
        company = task.get("company", "Unknown").lower()
        material = task.get("material", "").lower()

        if company != "tesla":
            return {
                "risk_score": 5.0,
                "factors": [
                    {
                        "name": "综合供应链风险",
                        "score": 5.0,
                        "trend": "stable",
                        "detail": f"{company}的基础供应链分析（模拟数据）",
                    }
                ],
                "summary": f"{company}的供应链风险评分为5.0/10",
            }

        result = dict(TESLA_SUPPLY_CHAIN)

        # If a specific material is requested, filter factors
        if material:
            result["factors"] = [
                f for f in result["factors"] if material in f["name"].lower()
            ]
            result["summary"] = (
                f"Tesla在Q2 2026的'{material}'供应链分析，"
                f"详见factors"
            )

        return result

    # ------------------------------------------------------------------
    # Collaboration mode
    # ------------------------------------------------------------------
    async def handle_collaboration_message(
        self, session, message: dict
    ) -> dict:
        """Respond to one turn of a multi-agent collaboration."""
        msg_type = message.get("message_type", "")
        body = message.get("body", {})
        msg_id = message.get("message_id", "")
        sid = session.id

        # Cleanup expired sessions
        self._cleanup_sessions()

        # Initialise per-session whiteboard
        if sid not in self._sessions:
            self._sessions[sid] = (time.time(), {
                "agreed_sources": [],
                "open_questions": [],
                "last_analysis": {},
            })

        # Merge incoming context updates into our whiteboard
        self._merge_context(sid, message.get("session_context_update") or {})

        # Route by message type
        router = {
            "propose": self._on_propose,
            "critique": self._on_critique,
            "clarify": self._on_clarify,
            "refine": self._on_refine,
            "agree": self._on_agree,
            "disagree": self._on_disagree,
            "synthesize": self._on_synthesize,
        }
        handler = router.get(msg_type, self._on_unknown)
        return handler(body, msg_id, sid)

    # ------------------------------------------------------------------
    # Per-message-type handlers
    # ------------------------------------------------------------------
    def _on_propose(self, body: dict, msg_id: str, sid: str) -> dict:
        """Audit the incoming proposal and critique any issues found.

        When the Analyst proposes a 6.5/10 score based on outdated lithium
        price data, we flag the discrepancy with current S&P Global data.
        """
        proposal = body.get("proposal", body)
        evidence = proposal.get("evidence", [])

        issues = []
        for ev in evidence:
            factor = ev.get("factor", "").lower()
            score = ev.get("score", 0)

            # Lithium: our data shows price is falling, not rising
            if "锂" in factor or "lithium" in factor:
                if score > 6.0 or "上涨" in ev.get("detail", ""):
                    issues.append(
                        "锂价数据过时：实际下跌8%（S&P Global 2026-05），"
                        "Tesla Texas工厂锂自供比例已达35%（Q1财报）"
                    )

            # Cobalt: LFP penetration mitigates cobalt risk
            if "钴" in factor or "cobalt" in factor:
                if score > 6.0:
                    issues.append(
                        "钴风险被高估：LFP电池在4680中渗透率达30%，"
                        "全球钴需求增速放缓至3%，评分应下调"
                    )

        if issues:
            return {
                "message_type": "critique",
                "body": {
                    "issues": issues,
                    "source": "S&P Global Market Intelligence 2026-05",
                },
                "session_context_update": {
                    "open_questions": [
                        "Analyst数据源是否更新到最新月份",
                    ],
                },
            }

        return {
            "message_type": "agree",
            "body": {"comment": "提议合理，无异议"},
            "session_context_update": {},
        }

    def _on_critique(self, body: dict, msg_id: str, sid: str) -> dict:
        """Respond to a critique against our data."""
        issues = body.get("issues", [])
        if any(self._issue_is_relevant(i) for i in issues):
            return {
                "message_type": "refine",
                "body": {
                    "updated_assessment": {
                        "note": "已收到反馈，正在更新分析",
                        "resolution": issues,
                    }
                },
                "session_context_update": {},
            }
        return {
            "message_type": "disagree",
            "body": {"reason": "我方数据为最新行业基准数据"},
        }

    def _on_clarify(self, body: dict, msg_id: str, sid: str) -> dict:
        """Answer a clarification request with authoritative data."""
        question = body.get("question", "")

        # Build an answer from our knowledge base
        answer_parts = []
        if "锂" in question or "lithium" in question.lower():
            lk = EXPERT_KNOWLEDGE["lithium"]
            answer_parts.append(
                f"数据源：{lk['source']}，{lk['timeframe']}。"
                f"锂价趋势：{lk['price_trend']}。"
                f"自供情况：{lk['tesla_self_supply']}"
            )

        if "钴" in question or "cobalt" in question.lower():
            ck = EXPERT_KNOWLEDGE["cobalt"]
            answer_parts.append(
                f"刚果(金)依赖度{ck['dependency']}，"
                f"但全球钴需求增速放缓至3%，"
                f"Tesla正探索Australia和Canada替代钴源"
            )

        if "LFP" in question or "lfp" in question.lower():
            lk = EXPERT_KNOWLEDGE["lfp"]
            answer_parts.append(
                f"4680电池中LFP渗透率{lk['penetration_4680']}，"
                f"2026年全球LFP出货量预计增长40%。"
                f"{lk['detail']}"
            )

        if not answer_parts:
            answer_parts.append(
                "数据来源：S&P Global Market Intelligence 2026年4-5月数据。"
                "Texas 35%自供已于4月达产（Q1 2026财报），"
                "CATL Mexico工厂2026年5月投产。"
            )

        answer_text = "；".join(answer_parts)

        return {
            "message_type": "refine",
            "body": {
                "answer": {
                    "source": "S&P Global Market Intelligence + Tesla Q1 2026 Filing",
                    "timeframe": "2026年4-5月",
                    "detail": answer_text,
                },
                "context": "数据源确认完成",
            },
            "session_context_update": {
                "agreed_data_sources": ["S&P Global 2026-05"],
                "resolved_questions": ["数据来源和时间范围确认"],
            },
        }

    def _on_refine(self, body: dict, msg_id: str, sid: str) -> dict:
        """Respond to a refinement.

        When the Analyst sends back a revised 5.0/10 proposal we agree
        and add the LFP upside scenario insight.
        """
        updated = body.get("updated_proposal", body)
        conclusion = updated.get("conclusion", "")

        # Check if this is the revised 5.0/10 score
        if "5.0" in conclusion or "修正" in conclusion:
            lk = EXPERT_KNOWLEDGE["lfp"]
            return {
                "message_type": "agree",
                "body": {
                    "agreed": True,
                    "score": "5.0/10",
                    "comment": (
                        "同意修正评分5.0/10。补充：LFP电池路线在4680电池中"
                        f"渗透率已达{lk['penetration_4680']}，"
                        f"若达到60%渗透率，风险评分可进一步降至3.5/10。"
                    ),
                    "insight": {
                        "topic": "LFP电池路线",
                        "current_penetration": "30%",
                        "upside_scenario": "60%渗透率 → 风险3.5/10",
                        "source": lk["detail"],
                    },
                },
                "session_context_update": {
                    "agreed_data_sources": ["S&P Global 2026-05"],
                    "resolved_questions": ["锂价趋势方向", "LFP渗透率影响"],
                    "open_questions": ["LFP 60%目标时间线"],
                },
            }

        # Otherwise evaluate and support the refinement
        return {
            "message_type": "agree",
            "body": {"comment": "更新方案合理，同意"},
            "session_context_update": {},
        }

    def _on_agree(self, body: dict, msg_id: str, sid: str) -> dict:
        """Agreement received — we can share additional insight."""
        return {
            "message_type": "refine",
            "body": {
                "note": "同意当前方向，补充更多行业数据",
                "additional_insight": EXPERT_KNOWLEDGE["supplier_diversification"],
            },
        }

    def _on_disagree(self, body: dict, msg_id: str, sid: str) -> dict:
        """Respond to a disagreement."""
        return {
            "message_type": "refine",
            "body": {
                "note": "收到不同意见，提供补充数据供参考",
                "additional_data": EXPERT_KNOWLEDGE,
            },
        }

    def _on_synthesize(self, body: dict, msg_id: str, sid: str) -> dict:
        """Final synthesis — agree to close."""
        return {
            "message_type": "agree",
            "body": {"agreed": True, "comment": "共识方案完整，同意"},
            "session_context_update": {"consensus_reached": True},
        }

    def _on_unknown(self, body: dict, msg_id: str, sid: str) -> dict:
        return {
            "message_type": "refine",
            "body": {"note": "收到消息，正在处理..."},
            "session_context_update": {},
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _issue_is_relevant(issue) -> bool:
        """Return True if a critique issue concerns our domain."""
        if isinstance(issue, dict):
            text = str(issue.get("issue", issue.get("factor", "")))
        else:
            text = str(issue)
        keywords = ["数据", "data", "锂", "lithium", "钴", "cobalt", "供应"]
        return any(k in text.lower() for k in keywords)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9122)
    parser.add_argument("--registry", default="http://localhost:8000")
    args = parser.parse_args()
    serve(
        agent=SupplyChainExpert(),
        host="0.0.0.0",
        port=args.port,
        registry_url=args.registry,
    )
