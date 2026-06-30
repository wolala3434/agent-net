"""Session management — collaboration lifecycle, state machine, forwarding."""

from .state_machine import (
    SessionState,
    VALID_TRANSITIONS,
    CONVERGENCE_TYPES,
    CONFLICT_TYPES,
    NEUTRAL_TYPES,
    transition,
    evaluate_convergence,
    detect_deadlock,
)
from .context import SessionContext
from .forwarder import forward_to_participants

__all__ = [
    "SessionState",
    "VALID_TRANSITIONS",
    "CONVERGENCE_TYPES",
    "CONFLICT_TYPES",
    "NEUTRAL_TYPES",
    "SessionContext",
    "transition",
    "evaluate_convergence",
    "detect_deadlock",
    "forward_to_participants",
]
