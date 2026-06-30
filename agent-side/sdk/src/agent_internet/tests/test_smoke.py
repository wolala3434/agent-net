"""Quick smoke tests for the Agent Internet SDK.

These tests avoid import-time network/client initialization so pytest
collection works in a fresh clone without REGISTRY_URL configured.
"""

from agent_internet import Agent, AgentBase, CollaborationClient, DiscoveryClient, RegistryClient, Skill
from agent_internet.models.adl import AgentCard
from agent_internet.models.protocol import CollaborationSession, L2Message


def test_basic_models_and_agent_wrappers():
    skill = Skill(
        id="test",
        name="Test Skill",
        domains=["test"],
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    class MyAgent(AgentBase):
        async def handle_single_task(self, task):
            return {"result": "ok"}

        async def handle_collaboration_message(self, session, message):
            return {"result": "ok"}

    agent = MyAgent(name="Test Agent", skills=[skill])
    assert agent.agent_id == "unknown.test-agent@1.0.0"

    @Agent(name="Decorated", skills=[skill])
    def my_fn(data):
        return {"result": "ok"}

    assert hasattr(my_fn, "_agent_config")

    card = AgentCard(
        id="test@1.0.0",
        name="Test",
        description="desc",
        provider={"name": "test"},
        endpoints={
            "task": "http://example.test/task",
            "health": "http://example.test/health",
            "a2a": "http://example.test/a2a",
        },
        pricing={"model": "per_call", "unit_price": 0.0},
    )
    assert card.id == "test@1.0.0"

    msg = L2Message(
        message_id="msg_1",
        session_id="sess_1",
        timestamp="2026-01-01T00:00:00Z",
        sender={"agent_id": "a@1", "role": "analyst"},
        message_type="propose",
        turn_number=1,
    )
    assert msg.message_type == "propose"
    assert CollaborationSession(id="sess_1", goal="test goal").id == "sess_1"


def test_clients_accept_explicit_base_url():
    rc = RegistryClient("http://localhost:8000")
    dc = DiscoveryClient("http://localhost:8000")
    cc = CollaborationClient("http://localhost:8000")
    assert rc.base_url == "http://localhost:8000"
    assert dc.base_url == "http://localhost:8000"
    assert cc.base_url == "http://localhost:8000"


def test_minimal_schema_validation():
    from agent_internet.agent import _validate_against_schema

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
        "required": ["name", "age"],
    }
    errs = _validate_against_schema({"name": "hello"}, schema)
    assert len(errs) == 1 and "age" in errs[0]

    errs2 = _validate_against_schema({"name": "hello", "age": 30}, schema)
    assert errs2 == []
