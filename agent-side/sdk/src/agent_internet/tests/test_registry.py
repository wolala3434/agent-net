"""Tests for agent_internet.registry module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent_internet.registry import RegistryClient


class TestRegistryClient:
    """Test RegistryClient."""

    def test_init_default(self):
        """Test RegistryClient initialization with defaults."""
        client = RegistryClient()
        assert client.base_url == "http://localhost:8000"
        assert client._client is None

    def test_init_custom_url(self):
        """Test RegistryClient initialization with custom URL."""
        client = RegistryClient(base_url="http://example.com:9000")
        assert client.base_url == "http://example.com:9000"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped."""
        client = RegistryClient(base_url="http://example.com/")
        assert client.base_url == "http://example.com"

    @pytest.mark.asyncio
    async def test_get_client_creates_client(self):
        """Test that _get_client creates httpx.AsyncClient."""
        client = RegistryClient()
        httpx_client = client._get_client()
        assert httpx_client is not None
        assert client._client is not None
        await client.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses_client(self):
        """Test that _get_client reuses existing client."""
        client = RegistryClient()
        client1 = client._get_client()
        client2 = client._get_client()
        assert client1 is client2
        await client.close()

    @pytest.mark.asyncio
    async def test_register_success(self):
        """Test successful agent registration."""
        client = RegistryClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"agent_id": "test.agent@1.0.0"}
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            adl_card = {"id": "test.agent@1.0.0", "name": "Test Agent"}
            result = await client.register(adl_card)

            assert result == {"agent_id": "test.agent@1.0.0"}
            mock_httpx_client.post.assert_called_once()
            call_args = mock_httpx_client.post.call_args
            assert "/api/v1/agents/register" in call_args[0][0]
            assert call_args[1]["json"] == adl_card

    @pytest.mark.asyncio
    async def test_register_raises_on_error(self):
        """Test that register raises on HTTP error."""
        client = RegistryClient()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        mock_httpx_client = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            with pytest.raises(Exception, match="HTTP 500"):
                await client.register({"id": "test.agent@1.0.0"})

    @pytest.mark.asyncio
    async def test_heartbeat_success(self):
        """Test successful heartbeat."""
        client = RegistryClient()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.post.return_value = AsyncMock()

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.heartbeat("test.agent@1.0.0", status="healthy", load=0.5)

            mock_httpx_client.post.assert_called_once()
            call_args = mock_httpx_client.post.call_args
            assert "/api/v1/agents/test.agent@1.0.0/heartbeat" in call_args[0][0]
            assert call_args[1]["json"] == {"status": "healthy", "load": 0.5}

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful agent search."""
        client = RegistryClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "matches": [
                {"agent_id": "agent1", "score": 0.9},
                {"agent_id": "agent2", "score": 0.8},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            result = await client.search(
                description="test query",
                domains=["domain1", "domain2"],
                top_k=5,
            )

            assert len(result["matches"]) == 2
            mock_httpx_client.post.assert_called_once()
            call_args = mock_httpx_client.post.call_args
            assert "/api/v1/discovery/search" in call_args[0][0]
            assert call_args[1]["json"]["description"] == "test query"
            assert call_args[1]["json"]["domains"] == ["domain1", "domain2"]
            assert call_args[1]["json"]["top_k"] == 5

    @pytest.mark.asyncio
    async def test_search_default_params(self):
        """Test search with default parameters."""
        client = RegistryClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"matches": []}
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.search(description="test")

            call_args = mock_httpx_client.post.call_args
            assert call_args[1]["json"]["domains"] == []
            assert call_args[1]["json"]["top_k"] == 3

    @pytest.mark.asyncio
    async def test_get_agent_success(self):
        """Test successful get_agent."""
        client = RegistryClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "test.agent@1.0.0", "name": "Test"}
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.get.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            result = await client.get_agent("test.agent@1.0.0")

            assert result["id"] == "test.agent@1.0.0"
            mock_httpx_client.get.assert_called_once()
            call_args = mock_httpx_client.get.call_args
            assert "/api/v1/agents/test.agent@1.0.0" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_deregister_success(self):
        """Test successful agent deregistration."""
        client = RegistryClient()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.delete.return_value = AsyncMock()

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.deregister("test.agent@1.0.0")

            mock_httpx_client.delete.assert_called_once()
            call_args = mock_httpx_client.delete.call_args
            assert "/api/v1/agents/test.agent@1.0.0" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the client."""
        client = RegistryClient()
        client._get_client()
        assert client._client is not None

        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """Test closing when client is not initialized."""
        client = RegistryClient()
        assert client._client is None
        await client.close()  # Should not raise
        assert client._client is None
