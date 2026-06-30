"""Shared AIP message builders — L1 envelope + L2 collaboration messages.

Single source of truth for both the SDK (agent-side) and the Platform backend.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .protocol import AIP_VERSION

DEFAULT_TTL = 300  # seconds


# ---------------------------------------------------------------------------
# L1 envelope
# ---------------------------------------------------------------------------
def build_l1_envelope(
    message_type: str,
    sender_type: str,
    sender_id: str,
    recipient_type: str,
    recipient_id: str,
    body: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    ttl_seconds: int = DEFAULT_TTL,
) -> dict[str, Any]:
    """Build an AIP/MP L1 message envelope."""
    return {
        "aip_version": AIP_VERSION,
        "protocol_layer": "message",
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "message_type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": ttl_seconds,
        "priority": "normal",
        "sender": {"type": sender_type, "id": sender_id},
        "recipient": {"type": recipient_type, "id": recipient_id},
        "correlation_id": correlation_id,
        "body": body or {},
    }


# ---------------------------------------------------------------------------
# L2 collaboration message
# ---------------------------------------------------------------------------
def build_l2_message(
    session_id: str,
    sender_agent_id: str,
    sender_role: str,
    message_type: str,
    turn_number: int,
    body: dict[str, Any] | None = None,
    references: list[str] | None = None,
    session_context_update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an AIP/CP L2 collaboration message."""
    return {
        "aip_version": AIP_VERSION,
        "protocol_layer": "collaboration",
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender": {"agent_id": sender_agent_id, "role": sender_role},
        "message_type": message_type,
        "turn_number": turn_number,
        "references": references or [],
        "body": body or {},
        "session_context_update": session_context_update,
    }


# ---------------------------------------------------------------------------
# Convenience builders — one per L2 message type
# ---------------------------------------------------------------------------
def propose(
    session_id: str, agent_id: str, role: str, turn: int, proposal: dict,
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "propose", turn,
        body={"proposal": proposal},
    )


def critique(
    session_id: str, agent_id: str, role: str, turn: int,
    issues: list, references: list[str],
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "critique", turn,
        body={"issues": issues}, references=references,
    )


def clarify(
    session_id: str, agent_id: str, role: str, turn: int,
    question: str, references: list[str],
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "clarify", turn,
        body={"question": question}, references=references,
    )


def refine(
    session_id: str, agent_id: str, role: str, turn: int,
    updated: dict, references: list[str],
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "refine", turn,
        body=updated, references=references,
    )


def agree(
    session_id: str, agent_id: str, role: str, turn: int,
    supplement: str = "", references: list[str] | None = None,
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "agree", turn,
        body={"supplement": supplement}, references=references or [],
    )


def disagree(
    session_id: str, agent_id: str, role: str, turn: int,
    reason: str, references: list[str],
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "disagree", turn,
        body={"reason": reason}, references=references,
    )


def synthesize(
    session_id: str, agent_id: str, role: str, turn: int,
    conclusion: dict,
) -> dict:
    return build_l2_message(
        session_id, agent_id, role, "synthesize", turn,
        body={"conclusion": conclusion},
    )
