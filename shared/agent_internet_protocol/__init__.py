"""agent-internet-protocol — shared ADL and AIP protocol models.

Single source of truth for both the SDK (agent-side) and the Platform backend.

Usage::

    from shared import AgentCard, Provider, Capability, Endpoints, Pricing
    from shared import L1Envelope, L2Message, CollaborationSession
"""

from .adl import (
    AgentCard,
    Capability,
    Endpoints,
    Pricing,
    PricingModel,
    Provider,
)
from .builders import (
    DEFAULT_TTL,
    agree,
    build_l1_envelope,
    build_l2_message,
    clarify,
    critique,
    disagree,
    propose,
    refine,
    synthesize,
)
from .protocol import (
    AIP_VERSION,
    CollaborationSender,
    CollaborationSession,
    L1Envelope,
    L2Message,
    MessageRecipient,
    MessageSender,
    SessionParticipant,
)

__all__ = [
    # ADL
    "AgentCard",
    "Capability",
    "Endpoints",
    "Pricing",
    "PricingModel",
    "Provider",
    # Protocol
    "AIP_VERSION",
    "CollaborationSender",
    "CollaborationSession",
    "L1Envelope",
    "L2Message",
    "MessageRecipient",
    "MessageSender",
    "SessionParticipant",
    # Builders
    "DEFAULT_TTL",
    "agree",
    "build_l1_envelope",
    "build_l2_message",
    "clarify",
    "critique",
    "disagree",
    "propose",
    "refine",
    "synthesize",
]
