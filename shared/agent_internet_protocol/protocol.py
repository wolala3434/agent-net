"""AIP Protocol shared Pydantic models — L1 envelope + L2 collaboration.

Single source of truth shared by both the SDK and the Platform backend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

AIP_VERSION = "1.0"


# ---------------------------------------------------------------------------
# L1 — Message Protocol (AIP/MP)
# ---------------------------------------------------------------------------
class MessageSender(BaseModel):
    type: str   # agent | gateway | registry | dashboard
    id: str


class MessageRecipient(BaseModel):
    type: str
    id: str


class L1Envelope(BaseModel):
    """AIP/MP L1 message envelope."""
    aip_version: str = AIP_VERSION
    protocol_layer: str = "message"
    message_id: str
    message_type: str
    timestamp: datetime
    ttl_seconds: int = 300
    priority: str = "normal"
    sender: MessageSender
    recipient: MessageRecipient
    correlation_id: str | None = None
    body: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# L2 — Collaboration Protocol (AIP/CP)
# ---------------------------------------------------------------------------
class CollaborationSender(BaseModel):
    agent_id: str
    role: str


class L2Message(BaseModel):
    """AIP/CP L2 collaboration message envelope."""
    aip_version: str = AIP_VERSION
    protocol_layer: str = "collaboration"
    message_id: str
    session_id: str
    timestamp: datetime
    sender: CollaborationSender
    message_type: str  # propose | critique | clarify | refine | agree | disagree | synthesize
    turn_number: int
    references: list[str] = Field(default_factory=list)
    body: dict[str, Any] = Field(default_factory=dict)
    session_context_update: dict[str, Any] | None = None


class SessionParticipant(BaseModel):
    agent_id: str
    role: str
    joined_at: datetime


class CollaborationSession(BaseModel):
    """Full collaboration session data structure (aip-protocol.md)."""
    id: str
    task_id: str | None = None
    status: str = "initiated"
    goal: str
    participants: list[SessionParticipant] = Field(default_factory=list)
    shared_context: dict[str, Any] = Field(default_factory=dict)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    turn_count: int = 0
