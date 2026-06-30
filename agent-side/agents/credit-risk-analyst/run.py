"""Credit Risk Analyst — Demo Agent (:9121).

A financial risk analyst agent that assesses credit and supply-chain risks
for companies.  Uses AgentBase (class mode) so it can participate in
multi-agent collaboration dialogues.

Domain: analysis.financial, analysis.risk
Skill:  credit-risk-assessment

Expected collaboration flow (Tesla demo):
  Turn 1 Analyst  → propose   (6.5/10)
  Turn 2 Expert   → critique  (lithium data outdated)
  Turn 3 Analyst  → clarify   (ask for source / timeframe)
  Turn 4 Expert   → refine    (provide S&P Global data)
  Turn 5 Analyst  → refine    (recalculate -> 5.0/10)
  Turn 6 Expert   → agree     (add LFP insight)
  Turn 7 Analyst  → synthesize (consensus)
"""

from __future__ import annotations

import argparse
import time

from agent_internet import Skill, serve
from collaborative_agent_base import CollaborativeAgentBase

# ---------------------------------------------------------------------------
# Mock financial / risk data for Tesla
# ---------------------------------------------------------------------------
TESLA_RISK_DATA = {
    "risk_score": 6.5,
    "factors": [
        {
            "name": "锂供应风险",
            "score": 7.0,
            "trend": "rising",
            "detail": (
                "锂价在Q2 2026内上涨12%，主要受电动车需求拉动，"
                "S&P Global 2026-03数据"
            ),
        },
        {
            "name": "钴供应链风险",
            "score": 7.0,
            "trend": "rising",
            "detail": "钴67%来自刚果(金)，地缘政治风险高，价格波动加剧",
        },
        {
            "name": "供应商集中度",
            "score": 5.5,
            "trend": "improving",
            "detail": "Tesla正在多元化供应商，目前已签约3家新供应商",
        },
    ],
    "summary": (
        "Tesla在Q2 2026的综合供应链风险评分为6.5/10，"
        "处于中等偏高风险区间，主要风险点在于锂和钴的供应压力"
    ),
}

# ---------------------------------------------------------------------------
# Revised risk assessment after incorporating Expert's data
# ---------------------------------------------------------------------------
REVISED_PROPOSAL = {
    "conclusion": "修正评分：供应链风险评分 5.0/10",
    "reasoning": (
        "根据S&P Global 2026-05最新锂价数据（实际下跌8%），"
        "以及Tesla Texas工厂锂自供比例达35%，重新计算后评分从6.5修正为5.0。"
        "锂供应评分从7.0下调至4.0，钴供应评分从7.0下调至5.5。"
    ),
    "confidence": 0.85,
    "evidence": [
        {
            "factor": "锂供应风险",
            "score": 4.0,
            "trend": "improving",
            "detail": "锂价实际下跌8%（S&P Global 2026-05），Texas工厂自供35%（Q1财报）",
        },
        {
            "factor": "钴供应链风险",
            "score": 5.5,
            "trend": "improving",
            "detail": "尽管67%来自刚果(金)，但LFP渗透率30%降低钴需求",
        },
        {
            "factor": "供应商集中度",
            "score": 5.0,
            "trend": "improving",
            "detail": "CATL Mexico工厂2026年5月投产，进一步多元化供应",
        },
    ],
}


class CreditRiskAnalyst(CollaborativeAgentBase):
    """Financial risk analyst — assess credit and supply chain risks.

    Works both standalone (``handle_single_task``) and in collaboration
    sessions (``handle_collaboration_message``).
    """

    def __init__(self) -> None:
        super().__init__(
            name="Credit Risk Analyst",
            version="1.0.0",
            description="金融风险建模与分析，评估企业信用和供应链风险",
            provider={
                "name": "Agent Internet Demo",
                "contact": "demo@agentinternet.io",
            },
            skills=[
                Skill(
                    id="credit-risk-assessment",
                    name="信用风险评估",
                    domains=["analysis.financial", "analysis.risk"],
                    input_schema={
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "timeframe": {"type": "string"},
                        },
                        "required": ["company", "timeframe"],
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
        """Return a risk assessment for the given company."""
        company = task.get("company", "Unknown").lower()
        if company == "tesla":
            return dict(TESLA_RISK_DATA)
        return {
            "risk_score": 5.0,
            "factors": [
                {
                    "name": "综合风险",
                    "score": 5.0,
                    "trend": "stable",
                    "detail": f"{company}的基础风险分析（模拟数据）",
                }
            ],
            "summary": f"{company}的风险评分为5.0/10",
        }

    # ------------------------------------------------------------------
    # Collaboration mode
    # ------------------------------------------------------------------
    async def handle_collaboration_message(
        self, session, message: dict
    ) -> dict:
        """Respond to one turn of a multi-agent collaboration.

        The agent inspects the incoming message's *type*, *body*, and
        *session_context_update* to decide the next action intelligently
        — no hardcoded turn numbers.
        """
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
                "my_proposal": None,
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
        """We are being asked to propose, or we are reviewing someone's proposal.

        If the body contains *task*, *goal* or *context* (i.e. not a
        concrete proposal), treat it as a request to start the discussion.
        """
        has_task = any(k in body for k in ("task", "goal", "context"))
        has_proposal = "proposal" in body
        if has_task or not has_proposal:
            return self._make_initial_proposal(sid)
        return self._default_response()

    def _on_critique(self, body: dict, msg_id: str, sid: str) -> dict:
        """Respond to a critique.  If valid we ask for clarification."""
        issues = body.get("issues", [])
        if any(self._issue_is_relevant(i) for i in issues):
            return {
                "message_type": "clarify",
                "body": {
                    "question": (
                        "请确认数据来源和时间范围？"
                        "我方使用S&P Global 2026-03数据，"
                        "需要最新数据以更新风险模型。"
                    ),
                    "context": "critique_accepted",
                },
                "session_context_update": {
                    "open_questions": ["数据来源和时间范围确认"],
                },
            }
        return {
            "message_type": "disagree",
            "body": {
                "reason": "我方数据源为S&P Global官方数据，评分已反映当前风险",
            },
        }

    def _on_clarify(self, body: dict, msg_id: str, sid: str) -> dict:
        """Someone asked us for clarification — answer with our data."""
        question = body.get("question", "")
        if "锂" in question or "lithium" in question.lower():
            answer = "锂价数据基于S&P Global 2026-03供应链报告"
        elif "钴" in question or "cobalt" in question.lower():
            answer = "钴供应数据基于DRC海关出口统计及行业报告"
        elif "LFP" in question:
            answer = "LFP渗透率数据基于行业报告，当前约20-25%"
        else:
            answer = "数据来源详细信息请参考S&P Global Market Intelligence平台"
        return {
            "message_type": "refine",
            "body": {
                "answer": {"detail": answer},
                "note": "已提供数据来源说明",
            },
            "session_context_update": {},
        }

    def _on_refine(self, body: dict, msg_id: str, sid: str) -> dict:
        """Respond to a refinement.

        If the body contains an *answer* (response to our clarification
        request), recalculate our risk model.  Otherwise evaluate and
        agree / disagree.
        """
        # Case 1: answer to our clarification question
        answer = body.get("answer", {}) or body.get("data", {})
        if answer:
            return self._refine_with_new_data(sid, str(answer))

        # Case 2: someone else's updated proposal — support it
        return {
            "message_type": "agree",
            "body": {"comment": "方案合理，同意"},
            "session_context_update": {},
        }

    def _on_agree(self, body: dict, msg_id: str, sid: str) -> dict:
        """Agreement received — synthesise the consensus."""
        return {
            "message_type": "synthesize",
            "body": {
                "consensus": {
                    "conclusion": "特斯拉Q2 2026供应链风险共识评分：5.0/10",
                    "key_findings": [
                        "锂供应风险已缓解：Texas自供35%且锂价实际下行8%",
                        "钴供应风险可控：LFP电池渗透率30%降低钴需求",
                        "CATL Mexico投产进一步分散供应风险",
                        "LFP电池路线若达60%渗透率，风险可进一步降至3.5/10",
                    ],
                    "status": "consensus_reached",
                    "participants": ["Credit Risk Analyst", "Supply Chain Expert"],
                }
            },
            "session_context_update": {
                "consensus_reached": True,
                "final_score": "5.0/10",
            },
        }

    def _on_disagree(self, body: dict, msg_id: str, sid: str) -> dict:
        """Respond to a disagreement by re-evaluating."""
        return {
            "message_type": "refine",
            "body": {
                "note": "收到不同意见，将重新审视数据",
                "incoming_reason": body.get("reason", ""),
            },
        }

    def _on_synthesize(self, body: dict, msg_id: str, sid: str) -> dict:
        """Final synthesis received — agree to close."""
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
    def _make_initial_proposal(self, sid: str) -> dict:
        """Propose the initial 6.5/10 risk assessment."""
        proposal = {
            "proposal": {
                "conclusion": "供应链风险评分：6.5/10",
                "reasoning": (
                    "基于S&P Global Q1 2026数据，锂价上涨12%（受电动车需求拉动），"
                    "钴67%依赖刚果(金)，供应商集中度中等偏高。"
                ),
                "confidence": 0.80,
                "evidence": [
                    {
                        "factor": "锂供应风险",
                        "score": 7.0,
                        "trend": "rising",
                        "detail": "锂价在Q2 2026内上涨12%，S&P Global 2026-03数据",
                    },
                    {
                        "factor": "钴供应链风险",
                        "score": 7.0,
                        "trend": "rising",
                        "detail": "钴67%来自刚果(金)，地缘政治风险高",
                    },
                    {
                        "factor": "供应商集中度",
                        "score": 5.5,
                        "trend": "improving",
                        "detail": "Tesla多元化供应商，已签约3家新供应商",
                    },
                ],
            }
        }
        self._sessions[sid] = (time.time(), {**self._sessions[sid][1], "my_proposal": proposal})
        return {
            "message_type": "propose",
            "body": proposal,
            "session_context_update": {
                "agreed_data_sources": ["S&P Global 2026-03"],
                "open_questions": [
                    "锂价最新趋势（S&P Global 2026-05更新）",
                    "钴替代方案进展",
                    "LFP电池渗透率",
                ],
            },
        }

    def _refine_with_new_data(self, sid: str, data_info: str) -> dict:
        """Recalculate risk assessment after receiving updated data."""
        self._sessions[sid] = (time.time(), {**self._sessions[sid][1], "my_proposal": REVISED_PROPOSAL})
        return {
            "message_type": "refine",
            "body": {"updated_proposal": REVISED_PROPOSAL},
            "session_context_update": {
                "agreed_data_sources": ["S&P Global 2026-05"],
                "resolved_questions": ["锂价趋势方向"],
                "open_questions": ["LFP电池渗透率对长期风险的影响"],
            },
        }

    def _merge_context(self, sid: str, update: dict) -> None:
        """Merge *session_context_update* into the per-session whiteboard."""
        ts, state = self._sessions[sid]
        state["agreed_sources"].extend(update.get("agreed_data_sources", []))
        state["open_questions"] = update.get(
            "open_questions", state["open_questions"]
        )
        self._sessions[sid] = (ts, state)

    @staticmethod
    def _issue_is_relevant(issue) -> bool:
        """Return True if a critique issue is worth acting on."""
        if isinstance(issue, dict):
            text = str(issue.get("issue", issue.get("factor", "")))
        else:
            text = str(issue)
        keywords = ["锂", "lithium", "数据", "data", "钴", "cobalt", "LFP"]
        return any(k in text.lower() for k in keywords)

    def _default_response(self) -> dict:
        return {
            "message_type": "refine",
            "body": {"note": "收到消息，正在处理..."},
            "session_context_update": {},
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9121)
    parser.add_argument("--registry", default="http://localhost:8000")
    args = parser.parse_args()
    serve(
        agent=CreditRiskAnalyst(),
        host="0.0.0.0",
        port=args.port,
        registry_url=args.registry,
    )
