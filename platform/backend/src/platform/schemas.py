"""Pydantic v2 request/response schemas for the Platform API.

Protocol models (ADL + AIP) are imported from the shared ``agent-internet-protocol``
package — the single source of truth.  API-specific request/response schemas
are defined here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from .constants import (
    AgentStatus,
    TrialStatus,
    TaskStatus,
    SessionStatus,
    HealthStatus,
    DEFAULT_USER_ID,
)

# ---------------------------------------------------------------------------
# Shared protocol models — single source of truth
# ---------------------------------------------------------------------------
from agent_internet_protocol import (
    # ADL
    AgentCard,
    Capability,
    Endpoints,
    Pricing,
    PricingModel,
    Provider,
    # Protocol
    CollaborationSender,
    CollaborationSession,
    L1Envelope,
    L2Message,
    MessageRecipient,
    MessageSender,
    SessionParticipant,
    AIP_VERSION,
)

# Backward-compatible alias: Platform code uses AIPEnvelope for L1Envelope.
AIPEnvelope = L1Envelope

# ---------------------------------------------------------------------------
# Enums (API-specific, not in shared protocol)
# ---------------------------------------------------------------------------
class SearchMode(str, Enum):
    exploit = "exploit"
    explore = "explore"


# ---------------------------------------------------------------------------
# CollaborationMessage — kept locally because the sender field uses
# ``dict[str, str]`` while the shared L2Message uses ``CollaborationSender``.
# The two are semantically equivalent but the Platform accepts looser input.
# ---------------------------------------------------------------------------
class CollaborationMessage(BaseModel):
    """L2 collaboration message (AIP/CP) — Platform-local variant."""
    aip_version: str = AIP_VERSION
    protocol_layer: str = "collaboration"
    message_id: str
    session_id: str
    timestamp: datetime
    sender: dict[str, str]  # {agent_id, role} — looser than CollaborationSender
    message_type: str  # propose | critique | clarify | refine | agree | disagree | synthesize
    turn_number: int
    references: list[str] = Field(default_factory=list)
    body: dict[str, Any] = Field(default_factory=dict)
    session_context_update: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# API Request / Response models
# ---------------------------------------------------------------------------
class RegisterResponse(BaseModel):
    status: str
    agent_id: str
    registered_at: datetime
    trial_status: TrialStatus
    free_quota_remaining: int


class HeartbeatRequest(BaseModel):
    status: str = HealthStatus.HEALTHY.value
    load: float = 0.0


class AgentListResponse(BaseModel):
    """Agent summary returned in list/filter results."""
    id: str
    name: str
    version: str
    provider_name: str | None = None
    description: str | None = None
    status: str
    trial_status: str
    health_status: str
    avg_rating: float
    total_tasks: int
    review_count: int = 0
    rating_distribution: dict[int, int] = Field(default_factory=dict)
    domains: list[str] = Field(default_factory=list)
    registered_at: datetime | None = None


class AgentDetailResponse(BaseModel):
    """Full agent detail including ADL card fields."""
    id: str
    name: str
    version: str
    provider_name: str | None = None
    provider_url: str | None = None
    description: str | None = None
    endpoint_url: str | None = None
    health_status: str
    auth_type: str
    status: str
    trial_status: str
    free_quota_total: int
    free_quota_used: int
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    avg_rating: float
    avg_latency_ms: float
    credit_score: float
    review_count: int = 0
    rating_distribution: dict[int, int] = Field(default_factory=dict)
    card_json: dict[str, Any] | None = None
    domains: list[str] = Field(default_factory=list)
    registered_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_heartbeat_at: datetime | None = None


class UpdateAgentRequest(BaseModel):
    """Fields that can be updated on an agent."""
    card_json: dict[str, Any] | None = None


class DiscoveryRequest(BaseModel):
    description: str
    domains: list[str] = Field(default_factory=list)
    top_k: int = 3
    user_id: str | None = None


class DiscoveryMatch(BaseModel):
    agent_id: str
    agent_name: str
    score: float
    match_reasons: list[str]
    avg_rating: float
    trial_status: TrialStatus
    pricing: dict[str, Any]


class DiscoveryResponse(BaseModel):
    matches: list[DiscoveryMatch]
    search_mode: SearchMode


class TaskSubmitRequest(BaseModel):
    description: str
    input: dict[str, Any]
    domains: list[str] = Field(default_factory=list)
    collaboration_mode: bool = False
    preferred_agents: list[str] = Field(default_factory=list)
    priority: str = "normal"
    user_id: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    mode: str  # "single" | "collaboration"
    session_id: str | None = None
    participants: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    parent_task_id: str | None = None
    initiator_agent: str
    goal: str
    discovery_query: str | None = None  # rewritten by the initiating agent
    required_domains: list[str] = Field(default_factory=list)
    shared_context: dict[str, Any] = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    agent_id: str
    task_id: str
    user_id: str = DEFAULT_USER_ID
    session_id: str | None = None
    rating: int = Field(ge=1, le=5)
    review_text: str | None = None


class ReviewResponse(BaseModel):
    id: int
    agent_id: str
    user_id: str
    task_id: str | None = None
    session_id: str | None = None
    rating: int
    review_text: str | None = None
    created_at: datetime
    updated_at: datetime


class PinAgentRequest(BaseModel):
    agent_id: str
    note: str | None = None


class PinAgentResponse(BaseModel):
    id: int
    user_id: str
    agent_id: str
    agent_name: str | None = None
    pinned_at: datetime
    note: str | None = None


class BillingDepositRequest(BaseModel):
    user_id: str
    amount: float
    payment_method: str


class BillingAccountResponse(BaseModel):
    balance: float
    free_credit: float
    total_deposited: float
    total_spent: float


# ---------------------------------------------------------------------------
# Error response (standardised)
# ---------------------------------------------------------------------------
class ErrorResponse(BaseModel):
    """Standard error envelope. Fills the previously-missing error format gap."""
    error: str
    detail: str | None = None
    code: str | None = None
    request_id: str | None = None


# ---------------------------------------------------------------------------
# Re-export everything that importers expect (backward-compatible __all__)
# ---------------------------------------------------------------------------
__all__ = [
    # Shared ADL
    "AgentCard",
    "Capability",
    "Endpoints",
    "Pricing",
    "PricingModel",
    "Provider",
    # Shared protocol
    "AIPEnvelope",          # alias of L1Envelope
    "CollaborationSender",
    "CollaborationSession",
    "L1Envelope",
    "L2Message",
    "MessageRecipient",
    "MessageSender",
    "SessionParticipant",
    # Platform-local
    "CollaborationMessage",
    # Enums
    "AgentStatus",
    "TrialStatus",
    "TaskStatus",
    "SessionStatus",
    "SearchMode",
    # Request / Response
    "RegisterResponse",
    "HeartbeatRequest",
    "AgentListResponse",
    "AgentDetailResponse",
    "UpdateAgentRequest",
    "DiscoveryRequest",
    "DiscoveryMatch",
    "DiscoveryResponse",
    "TaskSubmitRequest",
    "TaskResponse",
    "SessionCreateRequest",
    "ReviewRequest",
    "ReviewResponse",
    "PinAgentRequest",
    "PinAgentResponse",
    "BillingDepositRequest",
    "BillingAccountResponse",
    "ErrorResponse",
]
