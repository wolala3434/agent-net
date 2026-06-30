"""SessionContext — shared whiteboard for collaboration sessions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionContext:
    """Shared whiteboard for a collaboration session."""
    goal: str
    data: dict[str, Any] = field(default_factory=dict)
    agreed_facts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
