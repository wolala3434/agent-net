"""
Agent Internet SDK — build and connect collaborative AI agents.

Usage (10-minute quickstart, per sdk-guide.md)::

    from agent_internet import Agent, Skill, serve

    @Agent(name="My Expert", skills=[Skill(...)])
    def my_agent(input_data: dict) -> dict:
        return {"result": "..."}

    # Set environment variables: AGENT_PORT=9121 REGISTRY_URL=http://localhost:8000
    serve()
"""

from .agent import Agent, AgentBase, Skill
from .runtime import serve
from .registry import RegistryClient
from .discovery import DiscoveryClient
from .collaboration import CollaborationClient

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentBase",
    "Skill",
    "serve",
    "RegistryClient",
    "DiscoveryClient",
    "CollaborationClient",
]
