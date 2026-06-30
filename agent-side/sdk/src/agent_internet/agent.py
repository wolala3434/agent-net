"""
Agent wrapper — decorator-based and class-based Agent definitions.

Per sdk-guide.md:
  - Mode A: @Agent decorator for pure-function agents
  - Mode B: AgentBase subclass for collaboration-capable agents
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Skill — mirrors ADL capabilities
# ---------------------------------------------------------------------------
@dataclass
class Skill:
    """A single skill/capability exposed by an agent (matches ADL capabilities[])."""
    id: str
    name: str
    domains: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    execution_type: str = "synchronous"
    estimated_cost: str = "low"
    estimated_duration: str = "short"


# ---------------------------------------------------------------------------
# JSON Schema validation helpers
# ---------------------------------------------------------------------------
def _validate_against_schema(data: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """Validate *data* against a minimal JSON Schema.

    Handles the common patterns used in ADL skills: required fields, type
    checks (string / number / integer / boolean / array / object), nested
    object properties, and array item schemas.
    """
    errors: list[str] = []
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(data, dict):
            return [f"{path}expected object, got {type(data).__name__}"]

        # required fields
        for field in schema.get("required", []):
            if field not in data:
                errors.append(f"{path}missing required field: '{field}'")

        # property types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in data:
                sub_path = f"{path}{field}." if path else f"{field}."
                errors.extend(
                    _validate_against_schema(data[field], field_schema, sub_path)
                )
        return errors

    if schema_type == "array":
        if not isinstance(data, list):
            return [f"{path}expected array, got {type(data).__name__}"]
        items_schema = schema.get("items", {})
        for i, item in enumerate(data):
            errors.extend(
                _validate_against_schema(item, items_schema, f"{path}[{i}].")
            )
        return errors

    # Scalar types
    if schema_type == "string":
        if not isinstance(data, str):
            return [f"{path}expected string, got {type(data).__name__}"]
    elif schema_type == "number":
        if not isinstance(data, (int, float)):
            return [f"{path}expected number, got {type(data).__name__}"]
    elif schema_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            return [f"{path}expected integer, got {type(data).__name__}"]
    elif schema_type == "boolean":
        if not isinstance(data, bool):
            return [f"{path}expected boolean, got {type(data).__name__}"]

    return errors


# ---------------------------------------------------------------------------
# Agent config (decorator mode)
# ---------------------------------------------------------------------------
@dataclass
class AgentConfig:
    """Stores the static metadata that describes an agent's identity and
    capabilities.  Used by both the decorator and class-based modes."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    provider: dict[str, str] = field(default_factory=dict)
    skills: list[Skill] = field(default_factory=list)
    pricing: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    authentication: dict[str, Any] = field(default_factory=lambda: {"type": "none"})


# ---------------------------------------------------------------------------
# Decorator: @Agent(...)
# ---------------------------------------------------------------------------
def Agent(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    provider: dict[str, str] | None = None,
    skills: list[Skill] | None = None,
    pricing: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    authentication: dict[str, Any] | None = None,
) -> Callable:
    """
    Decorator that wraps a plain function into a registrable Agent.

    The decorated function's signature is validated against Skill.input_schema
    and its return value against Skill.output_schema at runtime.
    """
    config = AgentConfig(
        name=name,
        version=version,
        description=description,
        provider=provider or {},
        skills=skills or [],
        pricing=pricing or {"model": "per_call", "unit_price": 0.0},
        tags=tags or {},
        authentication=authentication or {"type": "none"},
    )

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)
        wrapper._agent_config = config
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Base class: AgentBase (collaboration-capable)
# ---------------------------------------------------------------------------
class AgentBase:
    """
    Base class for agents that participate in multi-agent collaboration.

    Override:
      - handle_single_task()          for single-agent invocations
      - handle_collaboration_message() for multi-agent collaboration sessions
      - should_i_initiate_collaboration() to self-assess capability gaps
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        provider: dict[str, str] | None = None,
        skills: list[Skill] | None = None,
        pricing: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ):
        self.config = AgentConfig(
            name=name,
            version=version,
            description=description,
            provider=provider or {},
            skills=skills or [],
            pricing=pricing or {"model": "per_call", "unit_price": 0.0},
            tags=tags or {},
        )
        # Collect all domain tags from skills for self-assessment
        self.my_domains: set[str] = set()
        for skill in self.config.skills:
            self.my_domains.update(skill.domains)

    @property
    def agent_id(self) -> str:
        """Build the standard ADL agent ID: {provider}.{name}@{version}."""
        provider_name = self.config.provider.get("name", "unknown")
        provider_slug = provider_name.lower().replace(" ", "-")
        name_slug = self.config.name.lower().replace(" ", "-")
        return f"{provider_slug}.{name_slug}@{self.config.version}"

    async def handle_single_task(self, task: dict) -> dict:
        """Override: process a single-agent task, return result dict."""
        raise NotImplementedError

    async def handle_collaboration_message(
        self, session, message: dict
    ) -> dict:
        """Override: handle one turn of a multi-agent collaboration."""
        raise NotImplementedError

    async def request_collaboration(
        self,
        goal: str,
        required_domains: list[str] | None = None,
        shared_context: dict[str, Any] | None = None,
        parent_task_id: str | None = None,
        platform_url: str = "http://localhost:8000",
        original_task: str | None = None,
    ) -> dict[str, Any]:
        """
        Proactively create a collaboration session via the Session Manager.

        Before calling the platform, rewrites the discovery query via
        :meth:`rewrite_discovery_query` so the Discovery Engine can find
        the best-fitting collaborators — not just keyword-match on the
        raw task description.
        """
        from .collaboration import CollaborationClient

        required_domains = required_domains or []
        gaps = set(required_domains)
        original = original_task or goal
        discovery_query = self.rewrite_discovery_query(original, gaps)

        client = CollaborationClient(platform_url)
        return await client.create_session(
            initiator_agent=self.agent_id,
            goal=goal,
            discovery_query=discovery_query,
            required_domains=required_domains,
            shared_context=shared_context,
            parent_task_id=parent_task_id,
        )

    def should_i_initiate_collaboration(self, task: dict) -> bool:
        """
        Self-assessment: does this task need collaboration?

        Compares the task's ``required_domains`` against the domains the
        agent advertises through its skills.
        """
        required = set(task.get("required_domains", []))
        gaps = required - self.my_domains
        return len(gaps) > 0

    def rewrite_discovery_query(self, original_task: str, gaps: set[str]) -> str:
        """
        Rewrite the discovery query to better find collaborators.

        The default implementation constructs a query from the domain gaps
        and the original task. Override this to use an LLM or domain-specific
        terminology expansion.

        Args:
            original_task: The original user request / task description.
            gaps: The set of domains this agent cannot cover.

        Returns:
            A rewritten query string optimised for agent discovery.

        Example::

            original_task = "评估特斯拉 Q2 供应链风险"
            gaps = {"supply-chain"}
            → "电动车行业锂、钴等关键原材料供应链分析"
        """
        gap_labels = ", ".join(sorted(gaps))
        return f"{original_task}\n\n需要以下领域专家协助: {gap_labels}"
