"""Tests for agent_internet.collaboration module."""

import pytest
from agent_internet_protocol import AIP_VERSION
from unittest.mock import AsyncMock, MagicMock, patch
from agent_internet.collaboration import CollaborationClient


class TestCollaborationClient:
    """Test CollaborationClient."""

    def test_init_default(self):
        """Test CollaborationClient initialization with defaults."""
        client = CollaborationClient()
        assert client.base_url == "http://localhost:8000"

    def test_init_custom_url(self):
        """Test CollaborationClient initialization with custom URL."""
        client = CollaborationClient(base_url="http://example.com:9000")
        assert client.base_url == "http://example.com:9000"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped."""
        client = CollaborationClient(base_url="http://example.com/")
        assert client.base_url == "http://example.com"

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation."""
        client = CollaborationClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "session-123",
            "status": "created",
            "participants": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        with patch.object(client, "_get_client", return_value=mock_instance):

            result = await client.create_session(
                initiator_agent="agent-1",
                goal="Test goal",
                discovery_query="Test query",
                required_domains=["domain1"],
                shared_context={"key": "value"},
                parent_task_id="task-123",
            )

            assert result["id"] == "session-123"
            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert "/api/v1/collaboration/sessions" in call_args[0][0]
            payload = call_args[1]["json"]
            assert payload["initiator_agent"] == "agent-1"
            assert payload["goal"] == "Test goal"
            assert payload["discovery_query"] == "Test query"
            assert payload["required_domains"] == ["domain1"]
            assert payload["shared_context"] == {"key": "value"}
            assert payload["parent_task_id"] == "task-123"

    @pytest.mark.asyncio
    async def test_create_session_defaults(self):
        """Test session creation with default parameters."""
        client = CollaborationClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "session-123"}
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        with patch.object(client, "_get_client", return_value=mock_instance):

            await client.create_session(
                initiator_agent="agent-1",
                goal="Test goal",
            )

            call_args = mock_instance.post.call_args
            payload = call_args[1]["json"]
            assert payload["discovery_query"] == "Test goal"
            assert payload["required_domains"] == []
            assert payload["shared_context"] == {}
            assert payload["parent_task_id"] is None

    @pytest.mark.asyncio
    async def test_get_session_success(self):
        """Test successful get_session."""
        client = CollaborationClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-123",
            "status": "active",
            "turn_count": 5,
        }
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        with patch.object(client, "_get_client", return_value=mock_instance):

            result = await client.get_session("session-123")

            assert result["id"] == "session-123"
            assert result["status"] == "active"
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert "/api/v1/collaboration/sessions/session-123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful send_message."""
        client = CollaborationClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        with patch.object(client, "_get_client", return_value=mock_instance):

            message = {
                "aip_version": AIP_VERSION,
                "protocol_layer": "collaboration",
                "message_type": "propose",
                "body": {"proposal": "test"},
            }
            result = await client.send_message("session-123", message)

            assert result["status"] == "ok"
            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert "/api/v1/collaboration/sessions/session-123/messages" in call_args[0][0]
            assert call_args[1]["json"] == message

    @pytest.mark.asyncio
    async def test_get_messages_success(self):
        """Test successful get_messages."""
        client = CollaborationClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "messages": [
                {"message_id": "msg1", "turn_number": 1},
                {"message_id": "msg2", "turn_number": 2},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        with patch.object(client, "_get_client", return_value=mock_instance):

            result = await client.get_messages("session-123", since_turn=1)

            assert len(result["messages"]) == 2
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert "/api/v1/collaboration/sessions/session-123/messages" in call_args[0][0]
            assert call_args[1]["params"]["since_turn"] == 1

    @pytest.mark.asyncio
    async def test_get_messages_default_since_turn(self):
        """Test get_messages with default since_turn."""
        client = CollaborationClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": []}
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        with patch.object(client, "_get_client", return_value=mock_instance):

            await client.get_messages("session-123")

            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["since_turn"] == 0
