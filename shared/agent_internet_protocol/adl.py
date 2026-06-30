"""ADL (Agent Description Language) shared Pydantic models.

Single source of truth shared by both the SDK (agent-side) and the Platform
backend. When the ADL schema changes, this is the primary file to update.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class PricingModel(str, Enum):
    per_call = "per_call"
    per_minute = "per_minute"
    per_token = "per_token"


# ---------------------------------------------------------------------------
# Core ADL models
# ---------------------------------------------------------------------------
class Provider(BaseModel):
    name: str
    url: str | None = None
    contact: str | None = None


class Capability(BaseModel):
    id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    domains: list[str] = Field(default_factory=list)
    execution_type: str = "synchronous"
    estimated_cost: str = "low"
    estimated_duration: str = "short"


class Endpoints(BaseModel):
    task: str
    health: str
    a2a: str


class Pricing(BaseModel):
    model: PricingModel = PricingModel.per_call
    currency: str = "USD"
    unit_price: float = 0.0
    billing_unit: str = "call"
    estimated_cost: str = "medium"
    discounts: dict[str, float] | None = None


class AgentCard(BaseModel):
    """Full ADL v1 card (adl-spec.md)."""
    id: str
    name: str
    version: str = "1.0.0"
    description: str
    provider: Provider
    capabilities: list[Capability] = Field(default_factory=list)
    endpoints: Endpoints
    pricing: Pricing
    authentication: dict[str, Any] = Field(default_factory=lambda: {"type": "none"})
    tags: dict[str, str] = Field(default_factory=dict)
