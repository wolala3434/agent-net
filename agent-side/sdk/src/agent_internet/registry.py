"""RegistryClient — register, heartbeat, search (per sdk-guide.md)."""

from __future__ import annotations

import logging
import os
from typing import Any

from .http_client import HttpClientBase
from .paths import (
    AGENTS_REGISTER, AGENTS_HEARTBEAT, AGENTS_SEARCH,
    AGENTS_GET, AGENTS_DEREGISTER,
)

logger = logging.getLogger(__name__)


class RegistryClient(HttpClientBase):
    """Async HTTP client for the Agent Internet Registry."""

    def __init__(self, base_url: str | None = None, **kwargs):
        if base_url is None:
            base_url = os.environ.get("REGISTRY_URL", "http://localhost:8000")
        super().__init__(base_url, **kwargs)

    async def register(self, adl_card: dict[str, Any]) -> dict[str, Any]:
        async def _do_register():
            client = self._get_client()
            resp = await client.post(
                f"{self.base_url}{AGENTS_REGISTER}", json=adl_card
            )
            resp.raise_for_status()
            return resp.json()
        return await self._retry_async(_do_register)

    async def heartbeat(self, agent_id: str, status: str = "healthy", load: float = 0.0) -> None:
        async def _do_heartbeat():
            client = self._get_client()
            await client.post(
                f"{self.base_url}{AGENTS_HEARTBEAT.format(agent_id=agent_id)}",
                json={"status": status, "load": load},
            )
        await self._retry_async(_do_heartbeat)

    async def search(self, description: str, domains: list[str] | None = None,
                     top_k: int = 3) -> dict[str, Any]:
        async def _do_search():
            client = self._get_client()
            resp = await client.post(
                f"{self.base_url}{AGENTS_SEARCH}",
                json={"description": description, "domains": domains or [], "top_k": top_k},
            )
            resp.raise_for_status()
            return resp.json()
        return await self._retry_async(_do_search)

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Fetch agent details (ADL card) from the Registry."""
        async def _do_get_agent():
            client = self._get_client()
            resp = await client.get(
                f"{self.base_url}{AGENTS_GET.format(agent_id=agent_id)}",
            )
            resp.raise_for_status()
            return resp.json()
        return await self._retry_async(_do_get_agent)

    async def deregister(self, agent_id: str) -> None:
        async def _do_deregister():
            client = self._get_client()
            await client.delete(f"{self.base_url}{AGENTS_DEREGISTER.format(agent_id=agent_id)}")
        await self._retry_async(_do_deregister)
