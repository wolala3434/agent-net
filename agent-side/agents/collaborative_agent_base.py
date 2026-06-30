"""CollaborativeAgentBase — shared base for collaboration-capable agents.

Extracts common session-management logic that was duplicated across
CreditRiskAnalyst and SupplyChainExpert.
"""

from __future__ import annotations

import time
from typing import Any

from agent_internet import AgentBase


class CollaborativeAgentBase(AgentBase):
    """AgentBase subclass with per-session whiteboard management.

    Subclasses get:
      - ``_sessions`` dict with TTL-based cleanup
      - ``_merge_context`` for merging context updates into the whiteboard
      - ``_default_response`` as a fallback handler
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Per-session whiteboard state with TTL (timestamp, data)
        self._sessions: dict[str, tuple[float, dict]] = {}
        self._session_ttl = 3600  # 1 hour in seconds

    def _cleanup_sessions(self) -> None:
        """Remove sessions older than TTL (1 hour)."""
        now = time.time()
        expired = [sid for sid, (ts, _) in self._sessions.items() if now - ts > self._session_ttl]
        for sid in expired:
            del self._sessions[sid]

    def _merge_context(self, sid: str, update: dict) -> None:
        """Merge *session_context_update* into the per-session whiteboard."""
        ts, state = self._sessions[sid]
        state["agreed_sources"].extend(update.get("agreed_data_sources", []))
        state["open_questions"] = update.get(
            "open_questions", state["open_questions"]
        )
        self._sessions[sid] = (ts, state)

    def _default_response(self) -> dict:
        return {
            "message_type": "refine",
            "body": {"note": "收到消息，正在处理..."},
            "session_context_update": {},
        }
