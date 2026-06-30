"""Tests for agent_internet.agent module."""

import pytest
from agent_internet.agent import (
    Agent,
    AgentBase,
    AgentConfig,
    Skill,
    _validate_against_schema,
)


class TestSkill:
    """Test Skill dataclass."""

    def test_skill_creation(self):
        """Test creating a Skill with required fields."""
        skill = Skill(id="test-skill", name="Test Skill")
        assert skill.id == "test-skill"
        assert skill.name == "Test Skill"
        assert skill.domains == []
        assert skill.input_schema == {}
        assert skill.output_schema == {}

    def test_skill_with_all_fields(self):
        """Test creating a Skill with all fields."""
        skill = Skill(
            id="test-skill",
            name="Test Skill",
            domains=["domain1", "domain2"],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            description="Test description",
            execution_type="async",
            estimated_cost="medium",
            estimated_duration="long",
        )
        assert skill.domains == ["domain1", "domain2"]
        assert skill.description == "Test description"
        assert skill.execution_type == "async"


class TestAgentConfig:
    """Test AgentConfig dataclass."""

    def test_agent_config_defaults(self):
        """Test AgentConfig with default values."""
        config = AgentConfig(name="Test Agent")
        assert config.name == "Test Agent"
        assert config.version == "1.0.0"
        assert config.description == ""
        assert config.provider == {}
        assert config.skills == []
        assert config.pricing == {}
        assert config.tags == {}
        assert config.authentication == {"type": "none"}

    def test_agent_config_with_skills(self):
        """Test AgentConfig with skills."""
        skill = Skill(id="s1", name="Skill 1")
        config = AgentConfig(name="Test Agent", skills=[skill])
        assert len(config.skills) == 1
        assert config.skills[0].id == "s1"


class TestAgentDecorator:
    """Test @Agent decorator."""

    def test_decorator_basic(self):
        """Test basic decorator usage."""
        @Agent(name="Test Agent")
        def my_agent(input_data: dict) -> dict:
            return {"result": "ok"}

        assert hasattr(my_agent, "_agent_config")
        assert my_agent._agent_config.name == "Test Agent"
        assert my_agent._agent_config.version == "1.0.0"

    def test_decorator_with_all_params(self):
        """Test decorator with all parameters."""
        skill = Skill(id="s1", name="Skill 1")

        @Agent(
            name="Test Agent",
            version="2.0.0",
            description="Test description",
            provider={"name": "Test Provider"},
            skills=[skill],
            pricing={"model": "per_call", "unit_price": 0.5},
            tags={"env": "test"},
            authentication={"type": "api_key"},
        )
        def my_agent(input_data: dict) -> dict:
            return {"result": "ok"}

        config = my_agent._agent_config
        assert config.name == "Test Agent"
        assert config.version == "2.0.0"
        assert config.description == "Test description"
        assert config.provider == {"name": "Test Provider"}
        assert len(config.skills) == 1
        assert config.pricing["unit_price"] == 0.5
        assert config.tags == {"env": "test"}
        assert config.authentication == {"type": "api_key"}

    def test_decorator_preserves_function(self):
        """Test that decorator preserves original function behavior."""
        @Agent(name="Test Agent")
        def my_agent(x: int, y: int) -> int:
            return x + y

        result = my_agent(3, 4)
        assert result == 7

    def test_decorator_with_kwargs(self):
        """Test decorator with kwargs."""
        @Agent(name="Test Agent")
        def my_agent(**kwargs) -> dict:
            return kwargs

        result = my_agent(a=1, b=2)
        assert result == {"a": 1, "b": 2}


class TestAgentBase:
    """Test AgentBase class."""

    def test_agentbase_init(self):
        """Test AgentBase initialization."""
        agent = AgentBase(name="Test Agent")
        assert agent.config.name == "Test Agent"
        assert agent.config.version == "1.0.0"
        assert agent.my_domains == set()

    def test_agentbase_with_skills(self):
        """Test AgentBase with skills extracts domains."""
        skill1 = Skill(id="s1", name="Skill 1", domains=["domain1", "domain2"])
        skill2 = Skill(id="s2", name="Skill 2", domains=["domain3"])

        agent = AgentBase(name="Test Agent", skills=[skill1, skill2])
        assert agent.my_domains == {"domain1", "domain2", "domain3"}

    def test_agent_id_generation(self):
        """Test agent_id property generation."""
        agent = AgentBase(
            name="Test Agent",
            version="1.0.0",
            provider={"name": "Test Provider"},
        )
        assert agent.agent_id == "test-provider.test-agent@1.0.0"

    def test_agent_id_with_spaces(self):
        """Test agent_id with spaces in names."""
        agent = AgentBase(
            name="My Test Agent",
            provider={"name": "My Provider"},
        )
        assert agent.agent_id == "my-provider.my-test-agent@1.0.0"

    def test_should_i_initiate_collaboration_no_gaps(self):
        """Test collaboration check when no gaps exist."""
        skill = Skill(id="s1", name="Skill 1", domains=["domain1", "domain2"])
        agent = AgentBase(name="Test Agent", skills=[skill])

        task = {"required_domains": ["domain1"]}
        assert agent.should_i_initiate_collaboration(task) is False

    def test_should_i_initiate_collaboration_with_gaps(self):
        """Test collaboration check when gaps exist."""
        skill = Skill(id="s1", name="Skill 1", domains=["domain1"])
        agent = AgentBase(name="Test Agent", skills=[skill])

        task = {"required_domains": ["domain1", "domain2"]}
        assert agent.should_i_initiate_collaboration(task) is True

    def test_should_i_initiate_collaboration_empty_domains(self):
        """Test collaboration check with empty required_domains."""
        agent = AgentBase(name="Test Agent")
        task = {"required_domains": []}
        assert agent.should_i_initiate_collaboration(task) is False

    def test_rewrite_discovery_query(self):
        """Test discovery query rewriting."""
        agent = AgentBase(name="Test Agent")
        query = agent.rewrite_discovery_query("Test task", {"domain1", "domain2"})
        assert "Test task" in query
        assert "domain1" in query or "domain2" in query

    @pytest.mark.asyncio
    async def test_handle_single_task_not_implemented(self):
        """Test that handle_single_task raises NotImplementedError."""
        agent = AgentBase(name="Test Agent")
        with pytest.raises(NotImplementedError):
            await agent.handle_single_task({})

    @pytest.mark.asyncio
    async def test_handle_collaboration_message_not_implemented(self):
        """Test that handle_collaboration_message raises NotImplementedError."""
        agent = AgentBase(name="Test Agent")
        with pytest.raises(NotImplementedError):
            await agent.handle_collaboration_message(None, {})


class TestSchemaValidation:
    """Test _validate_against_schema function."""

    def test_validate_string(self):
        """Test string validation."""
        schema = {"type": "string"}
        assert _validate_against_schema("test", schema) == []
        assert len(_validate_against_schema(123, schema)) > 0

    def test_validate_integer(self):
        """Test integer validation."""
        schema = {"type": "integer"}
        assert _validate_against_schema(42, schema) == []
        assert len(_validate_against_schema(3.14, schema)) > 0
        assert len(_validate_against_schema("42", schema)) > 0

    def test_validate_number(self):
        """Test number validation."""
        schema = {"type": "number"}
        assert _validate_against_schema(42, schema) == []
        assert _validate_against_schema(3.14, schema) == []
        assert len(_validate_against_schema("42", schema)) > 0

    def test_validate_boolean(self):
        """Test boolean validation."""
        schema = {"type": "boolean"}
        assert _validate_against_schema(True, schema) == []
        assert _validate_against_schema(False, schema) == []
        assert len(_validate_against_schema(1, schema)) > 0

    def test_validate_array(self):
        """Test array validation."""
        schema = {"type": "array", "items": {"type": "string"}}
        assert _validate_against_schema(["a", "b"], schema) == []
        assert len(_validate_against_schema([1, 2], schema)) > 0
        assert len(_validate_against_schema("not array", schema)) > 0

    def test_validate_object(self):
        """Test object validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        assert _validate_against_schema({"name": "Alice", "age": 30}, schema) == []
        assert len(_validate_against_schema({"age": 30}, schema)) > 0
        assert len(_validate_against_schema({"name": 123}, schema)) > 0

    def test_validate_nested_object(self):
        """Test nested object validation."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
        }
        assert _validate_against_schema({"user": {"name": "Alice"}}, schema) == []
        assert len(_validate_against_schema({"user": {}}, schema)) > 0
