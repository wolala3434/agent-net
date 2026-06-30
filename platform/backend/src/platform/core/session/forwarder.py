"""Message forwarding — notify participants of new collaboration messages.

Provides two modes:
  - ``forward_to_participants(db, ...)`` — synchronous, uses caller's DB session
  - ``_forward_async(session_id, ...)`` — fire-and-forget, creates own DB session
    (used when the POST /messages response must not be blocked by LLM latency)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from agent_internet_protocol import AIP_VERSION

from ...repository import AgentRepository
from ...config import settings
from ...database import async_session as _async_session_factory
from ...constants import UUID_TRUNCATE_LEN, LOG_ID_TRUNCATE_LEN

logger = logging.getLogger(__name__)


async def forward_to_participants(
    db,
    session_id: str,
    message_id: str,
    participants: list[dict],
    message_data: dict[str, Any],
) -> None:
    """Forward synchronously — caller provides DB session."""
    for participant in participants:
        await _forward_one(db, session_id, message_id, participant, message_data)


async def _forward_async(
    session_id: str,
    message_id: str,
    participants: list[dict],
    message_data: dict[str, Any],
) -> None:
    """Forward asynchronously — creates its own DB session.

    Designed for ``asyncio.create_task()`` so that slow LLM responses
    don't block the HTTP response that triggered the forwarding.
    """
    async with _async_session_factory() as db:
        for participant in participants:
            await _forward_one(db, session_id, message_id, participant, message_data)


async def _forward_one(
    db,
    session_id: str,
    message_id: str,
    participant: dict,
    message_data: dict[str, Any],
) -> None:
    """Forward a single message to one participant."""
    agent_id = participant.get("agent_id")
    if not agent_id:
        return

    agent = await AgentRepository.get_agent_by_id(db, agent_id)
    if not agent:
        return

    # Get A2A URL
    a2a_url = None
    if agent.endpoint_url:
        a2a_url = agent.endpoint_url.replace("/task", "/a2a")
    else:
        try:
            card = json.loads(agent.card_json or "{}")
            a2a_url = card.get("endpoints", {}).get("a2a", "")
        except Exception:
            pass

    a2a_url = a2a_url.replace("0.0.0.0", settings.advertised_host)
    if not a2a_url:
        return

    forward_msg = {
        "aip_version": AIP_VERSION,
        "protocol_layer": "collaboration",
        "message_id": f"fwd_{uuid.uuid4().hex[:UUID_TRUNCATE_LEN]}",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_type": message_data.get("message_type", "propose"),
        "sender": message_data.get("sender", {}),
        "turn_number": message_data.get("turn_number", 0),
        "body": message_data.get("body", {}),
        "session_context_update": message_data.get("session_context_update"),
        "references": [message_id],
    }

    logger.info(
        "[SESSION] Forwarding to %s at %s",
        agent_id[:LOG_ID_TRUNCATE_LEN], a2a_url,
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(a2a_url, json=forward_msg)
            logger.info(
                "[SESSION] Forward to %s → %d",
                agent_id[:LOG_ID_TRUNCATE_LEN], resp.status_code,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Forward to %s failed: %d", agent_id, resp.status_code,
                )
    except Exception as exc:
        logger.warning(
            "Forward to %s (%s) failed: %s", agent_id, a2a_url, exc,
        )
