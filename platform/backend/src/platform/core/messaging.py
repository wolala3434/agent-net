"""AIP Message Protocol — re-exports shared builders + Platform-specific helpers."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_internet_protocol import (
    build_l1_envelope,
    AIP_VERSION,
)

from ..schemas import AIPEnvelope
from ..models import Message as DBMessage


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------
build_envelope = build_l1_envelope


# ---------------------------------------------------------------------------
# Platform-specific L1 builders (no shared equivalent — keep here)
# ---------------------------------------------------------------------------
def build_register(agent_id: str, adl_json: dict[str, Any]) -> AIPEnvelope:
    return build_envelope(
        "register", "agent", agent_id, "registry", "registry",
        body={"adl": adl_json},
    )


def build_deregister(agent_id: str) -> AIPEnvelope:
    return build_envelope(
        "deregister", "agent", agent_id, "registry", "registry",
    )


def build_heartbeat(
    agent_id: str, status: str = "healthy", load: float = 0.0,
) -> AIPEnvelope:
    return build_envelope(
        "heartbeat", "agent", agent_id, "registry", "registry",
        body={"status": status, "load": load},
    )


def build_task_assign(
    task_id: str, agent_id: str, task_input: dict[str, Any],
) -> AIPEnvelope:
    return build_envelope(
        "task_assign", "gateway", "api-gateway", "agent", agent_id,
        body={"task_id": task_id, "input": task_input},
        correlation_id=task_id,
    )


def build_task_result(
    task_id: str, agent_id: str, result: dict[str, Any],
) -> AIPEnvelope:
    return build_envelope(
        "task_result", "agent", agent_id, "gateway", "api-gateway",
        body={"task_id": task_id, "result": result},
        correlation_id=task_id,
    )


# ---------------------------------------------------------------------------
# Validation helpers (Platform-specific — keep here)
# ---------------------------------------------------------------------------
L1_MESSAGE_TYPES = {
    "register", "deregister", "heartbeat",
    "task_assign", "task_result", "task_status", "task_error", "task_cancel",
}

L2_MESSAGE_TYPES = {
    "propose", "critique", "clarify", "refine",
    "agree", "disagree", "synthesize",
}

VALID_SENDER_TYPES = {"agent", "gateway", "registry", "dashboard"}
VALID_RECIPIENT_TYPES = {"agent", "gateway", "registry", "dashboard"}


def validate_l1_envelope(data: dict[str, Any]) -> list[str]:
    """Validate an L1 message envelope. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Body must be a JSON object"]
    if data.get("aip_version") != AIP_VERSION:
        errors.append(f'aip_version must be "{AIP_VERSION}"')
    if data.get("protocol_layer") != "message":
        errors.append('protocol_layer must be "message"')
    if not data.get("message_id"):
        errors.append("message_id is required")
    if data.get("message_type") not in L1_MESSAGE_TYPES:
        errors.append(
            f"message_type must be one of: {', '.join(sorted(L1_MESSAGE_TYPES))}"
        )
    sender = data.get("sender", {})
    if not isinstance(sender, dict):
        errors.append("sender must be an object")
    else:
        if sender.get("type") not in VALID_SENDER_TYPES:
            errors.append(
                f"sender.type must be one of: {', '.join(sorted(VALID_SENDER_TYPES))}"
            )
        if not sender.get("id"):
            errors.append("sender.id is required")
    recipient = data.get("recipient", {})
    if not isinstance(recipient, dict):
        errors.append("recipient must be an object")
    else:
        if recipient.get("type") not in VALID_RECIPIENT_TYPES:
            errors.append(
                f"recipient.type must be one of: {', '.join(sorted(VALID_RECIPIENT_TYPES))}"
            )
        if not recipient.get("id"):
            errors.append("recipient.id is required")
    return errors


def validate_l2_message(data: dict[str, Any]) -> list[str]:
    """Validate an L2 collaboration message. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Body must be a JSON object"]
    if data.get("aip_version") != AIP_VERSION:
        errors.append(f'aip_version must be "{AIP_VERSION}"')
    if data.get("protocol_layer") != "collaboration":
        errors.append('protocol_layer must be "collaboration"')
    if not data.get("message_id"):
        errors.append("message_id is required")
    if not data.get("session_id"):
        errors.append("session_id is required")
    if data.get("message_type") not in L2_MESSAGE_TYPES:
        errors.append(
            f"message_type must be one of: {', '.join(sorted(L2_MESSAGE_TYPES))}"
        )
    sender = data.get("sender", {})
    if not isinstance(sender, dict):
        errors.append("sender must be an object")
    elif not sender.get("agent_id"):
        errors.append("sender.agent_id is required")
    if not data.get("body"):
        errors.append("body is required")
    return errors


# ---------------------------------------------------------------------------
# Persistence helper (Platform-specific — keep here)
# ---------------------------------------------------------------------------
async def log_l1_message(
    db: AsyncSession,
    envelope: AIPEnvelope,
    status: str = "sent",
) -> DBMessage:
    """Persist an L1 message to the messages table for audit."""
    msg = DBMessage(
        message_id=envelope.message_id,
        correlation_id=envelope.correlation_id,
        sender_type=envelope.sender.type,
        sender_id=envelope.sender.id,
        recipient_type=envelope.recipient.type,
        recipient_id=envelope.recipient.id,
        message_type=envelope.message_type,
        body_json=json.dumps(envelope.body),
        status=status,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
