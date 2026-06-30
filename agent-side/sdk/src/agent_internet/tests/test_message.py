"""Tests for agent_internet.message module."""

from agent_internet.message import (
    build_l1_envelope,
    build_l2_message,
    propose,
    critique,
    clarify,
    refine,
    agree,
    disagree,
    synthesize,
)


class TestL1Envelope:
    """Test L1 envelope building."""

    def test_build_l1_envelope_basic(self):
        """Test basic L1 envelope creation."""
        envelope = build_l1_envelope(
            message_type="task",
            sender_type="user",
            sender_id="user-123",
            recipient_type="agent",
            recipient_id="agent-456",
        )

        assert envelope["aip_version"] == "1.0"
        assert envelope["protocol_layer"] == "message"
        assert envelope["message_type"] == "task"
        assert envelope["sender"]["type"] == "user"
        assert envelope["sender"]["id"] == "user-123"
        assert envelope["recipient"]["type"] == "agent"
        assert envelope["recipient"]["id"] == "agent-456"
        assert "message_id" in envelope
        assert envelope["message_id"].startswith("msg_")
        assert "timestamp" in envelope
        assert envelope["ttl_seconds"] == 300
        assert envelope["priority"] == "normal"
        assert envelope["body"] == {}
        assert envelope["correlation_id"] is None

    def test_build_l1_envelope_with_body(self):
        """Test L1 envelope with body."""
        body = {"query": "test query"}
        envelope = build_l1_envelope(
            message_type="task",
            sender_type="user",
            sender_id="user-123",
            recipient_type="agent",
            recipient_id="agent-456",
            body=body,
        )
        assert envelope["body"] == body

    def test_build_l1_envelope_with_correlation_id(self):
        """Test L1 envelope with correlation_id."""
        envelope = build_l1_envelope(
            message_type="task",
            sender_type="user",
            sender_id="user-123",
            recipient_type="agent",
            recipient_id="agent-456",
            correlation_id="corr-789",
        )
        assert envelope["correlation_id"] == "corr-789"

    def test_build_l1_envelope_with_custom_ttl(self):
        """Test L1 envelope with custom TTL."""
        envelope = build_l1_envelope(
            message_type="task",
            sender_type="user",
            sender_id="user-123",
            recipient_type="agent",
            recipient_id="agent-456",
            ttl_seconds=600,
        )
        assert envelope["ttl_seconds"] == 600


class TestL2Message:
    """Test L2 collaboration message building."""

    def test_build_l2_message_basic(self):
        """Test basic L2 message creation."""
        msg = build_l2_message(
            session_id="session-123",
            sender_agent_id="agent-456",
            sender_role="initiator",
            message_type="propose",
            turn_number=1,
        )

        assert msg["aip_version"] == "1.0"
        assert msg["protocol_layer"] == "collaboration"
        assert msg["session_id"] == "session-123"
        assert msg["sender"]["agent_id"] == "agent-456"
        assert msg["sender"]["role"] == "initiator"
        assert msg["message_type"] == "propose"
        assert msg["turn_number"] == 1
        assert "message_id" in msg
        assert msg["message_id"].startswith("msg_")
        assert "timestamp" in msg
        assert msg["references"] == []
        assert msg["body"] == {}
        assert msg["session_context_update"] is None

    def test_build_l2_message_with_body(self):
        """Test L2 message with body."""
        body = {"proposal": {"key": "value"}}
        msg = build_l2_message(
            session_id="session-123",
            sender_agent_id="agent-456",
            sender_role="initiator",
            message_type="propose",
            turn_number=1,
            body=body,
        )
        assert msg["body"] == body

    def test_build_l2_message_with_references(self):
        """Test L2 message with references."""
        refs = ["msg_abc123", "msg_def456"]
        msg = build_l2_message(
            session_id="session-123",
            sender_agent_id="agent-456",
            sender_role="initiator",
            message_type="propose",
            turn_number=1,
            references=refs,
        )
        assert msg["references"] == refs

    def test_build_l2_message_with_context_update(self):
        """Test L2 message with session context update."""
        ctx = {"key": "value"}
        msg = build_l2_message(
            session_id="session-123",
            sender_agent_id="agent-456",
            sender_role="initiator",
            message_type="propose",
            turn_number=1,
            session_context_update=ctx,
        )
        assert msg["session_context_update"] == ctx


class TestL2ConvenienceBuilders:
    """Test L2 convenience message builders."""

    def test_propose(self):
        """Test propose message builder."""
        proposal = {"architecture": "microservices"}
        msg = propose(
            session_id="s1",
            agent_id="a1",
            role="architect",
            turn=1,
            proposal=proposal,
        )
        assert msg["message_type"] == "propose"
        assert msg["body"]["proposal"] == proposal

    def test_critique(self):
        """Test critique message builder."""
        issues = ["issue1", "issue2"]
        refs = ["msg_ref1"]
        msg = critique(
            session_id="s1",
            agent_id="a1",
            role="reviewer",
            turn=2,
            issues=issues,
            references=refs,
        )
        assert msg["message_type"] == "critique"
        assert msg["body"]["issues"] == issues
        assert msg["references"] == refs

    def test_clarify(self):
        """Test clarify message builder."""
        question = "What is the QPS target?"
        refs = ["msg_ref1"]
        msg = clarify(
            session_id="s1",
            agent_id="a1",
            role="architect",
            turn=3,
            question=question,
            references=refs,
        )
        assert msg["message_type"] == "clarify"
        assert msg["body"]["question"] == question
        assert msg["references"] == refs

    def test_refine(self):
        """Test refine message builder."""
        updated = {"architecture": "updated design"}
        refs = ["msg_ref1"]
        msg = refine(
            session_id="s1",
            agent_id="a1",
            role="architect",
            turn=4,
            updated=updated,
            references=refs,
        )
        assert msg["message_type"] == "refine"
        assert msg["body"] == updated
        assert msg["references"] == refs

    def test_agree(self):
        """Test agree message builder."""
        msg = agree(
            session_id="s1",
            agent_id="a1",
            role="reviewer",
            turn=5,
            supplement="Looks good",
        )
        assert msg["message_type"] == "agree"
        assert msg["body"]["supplement"] == "Looks good"
        assert msg["references"] == []

    def test_agree_with_references(self):
        """Test agree message builder with references."""
        refs = ["msg_ref1"]
        msg = agree(
            session_id="s1",
            agent_id="a1",
            role="reviewer",
            turn=5,
            supplement="Looks good",
            references=refs,
        )
        assert msg["references"] == refs

    def test_disagree(self):
        """Test disagree message builder."""
        reason = "Security concerns"
        refs = ["msg_ref1"]
        msg = disagree(
            session_id="s1",
            agent_id="a1",
            role="reviewer",
            turn=6,
            reason=reason,
            references=refs,
        )
        assert msg["message_type"] == "disagree"
        assert msg["body"]["reason"] == reason
        assert msg["references"] == refs

    def test_synthesize(self):
        """Test synthesize message builder."""
        conclusion = {"final_verdict": "approved"}
        msg = synthesize(
            session_id="s1",
            agent_id="a1",
            role="architect",
            turn=7,
            conclusion=conclusion,
        )
        assert msg["message_type"] == "synthesize"
        assert msg["body"]["conclusion"] == conclusion
