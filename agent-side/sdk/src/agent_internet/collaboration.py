"""CollaborationClient — session join, send messages, receive (per sdk-guide.md)."""

from __future__ import annotations

import logging
import os
from typing import Any

from .http_client import HttpClientBase
from .paths import COLLAB_SESSIONS, COLLAB_SESSION_GET, COLLAB_MESSAGES

logger = logging.getLogger(__name__)


class CollaborationClient(HttpClientBase):
    """Client for Session Manager — collaboration session participation."""

    def __init__(self, base_url: str | None = None, **kwargs):
        if base_url is None:
            base_url = os.environ.get("REGISTRY_URL", "http://localhost:8000")
        super().__init__(base_url, **kwargs)

    async def create_session(
        self,
        initiator_agent: str,
        goal: str,
        discovery_query: str | None = None,
        required_domains: list[str] | None = None,
        shared_context: dict[str, Any] | None = None,
        parent_task_id: str | None = None,
    ) -> dict[str, Any]:
        async def _do_create_session():
            client = self._get_client()
            resp = await client.post(
                f"{self.base_url}{COLLAB_SESSIONS}",
                json={
                    "initiator_agent": initiator_agent,
                    "goal": goal,
                    "discovery_query": discovery_query or goal,
                    "required_domains": required_domains or [],
                    "shared_context": shared_context or {},
                    "parent_task_id": parent_task_id,
                },
            )
            resp.raise_for_status()
            return resp.json()
        result = await self._retry_async(_do_create_session)
        logger.info("协作会话已创建: initiator=%s, goal=%s", initiator_agent, goal[:50])
        return result

    async def get_session(self, session_id: str) -> dict[str, Any]:
        async def _do_get_session():
            client = self._get_client()
            resp = await client.get(
                f"{self.base_url}{COLLAB_SESSION_GET.format(session_id=session_id)}",
            )
            resp.raise_for_status()
            return resp.json()
        return await self._retry_async(_do_get_session)

    async def send_message(self, session_id: str, message: dict[str, Any]) -> dict[str, Any]:
        async def _do_send_message():
            client = self._get_client()
            resp = await client.post(
                f"{self.base_url}{COLLAB_MESSAGES.format(session_id=session_id)}",
                json=message,
            )
            resp.raise_for_status()
            return resp.json()
        result = await self._retry_async(_do_send_message)
        logger.info("协作消息已发送: session=%s, type=%s", session_id, message.get("message_type", ""))
        return result

    async def get_messages(self, session_id: str, since_turn: int = 0) -> dict[str, Any]:
        async def _do_get_messages():
            client = self._get_client()
            resp = await client.get(
                f"{self.base_url}{COLLAB_MESSAGES.format(session_id=session_id)}",
                params={"since_turn": since_turn},
            )
            resp.raise_for_status()
            return resp.json()
        return await self._retry_async(_do_get_messages)
