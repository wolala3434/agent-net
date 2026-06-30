import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
DEFAULT_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)
DEFAULT_MAX_RETRIES = 3


class HttpClientBase:
    def __init__(self, base_url: str, timeout=None, limits=None, max_retries: int = DEFAULT_MAX_RETRIES):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._limits = limits or DEFAULT_LIMITS
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                limits=self._limits,
            )
        return self._client

    async def _retry_async(self, coro_factory, operation: str = ""):
        """重试机制：最多 max_retries 次，指数退避"""
        last_exc = None
        for attempt in range(self._max_retries):
            try:
                return await coro_factory()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < self._max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"{operation} attempt {attempt+1} failed: {e}, retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"{operation} failed after {self._max_retries} attempts: {e}")
        raise last_exc

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
