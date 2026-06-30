"""DiscoveryClient — search for agents (per sdk-guide.md)."""

from __future__ import annotations

import logging
import os
from typing import Any

from .http_client import HttpClientBase
from .paths import DISCOVERY_SEARCH

logger = logging.getLogger(__name__)


class DiscoveryClient(HttpClientBase):
    """Client for the Agent Discovery Engine."""

    def __init__(self, base_url: str | None = None, **kwargs):
        if base_url is None:
            base_url = os.environ.get("REGISTRY_URL", "http://localhost:8000")
        super().__init__(base_url, **kwargs)

    async def search(
        self,
        description: str,
        domains: list[str] | None = None,
        top_k: int = 3,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        async def _do_search():
            client = self._get_client()
            resp = await client.post(
                f"{self.base_url}{DISCOVERY_SEARCH}",
                json={
                    "description": description,
                    "domains": domains or [],
                    "top_k": top_k,
                    "user_id": user_id,
                },
            )
            resp.raise_for_status()
            return resp.json()
        logger.info("搜索请求: description=%s, domains=%s, top_k=%d", description[:50], domains, top_k)
        return await self._retry_async(_do_search)
