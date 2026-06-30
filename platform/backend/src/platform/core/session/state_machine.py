"""Session state machine — pure logic, zero external dependencies.

Extracted from session_manager.py to enable independent unit testing.
"""

from enum import Enum


class SessionState(str, Enum):
    initiated = "initiated"
    negotiating = "negotiating"
    converging = "converging"
    completed = "completed"
    deadlocked = "deadlocked"


# Valid transitions (per aip-protocol.md + api-spec.md bidirectional note)
VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.initiated:   {SessionState.negotiating},
    SessionState.negotiating: {SessionState.converging, SessionState.deadlocked},
    SessionState.converging:  {SessionState.completed, SessionState.negotiating,
                                SessionState.deadlocked},
    SessionState.completed:   set(),
    SessionState.deadlocked:  set(),
}

# Message types that indicate convergence (per aip-protocol.md L2)
CONVERGENCE_TYPES = {"agree", "synthesize"}
CONFLICT_TYPES = {"disagree"}
NEUTRAL_TYPES = {"propose", "critique", "clarify", "refine"}


def transition(
    current: SessionState,
    target: SessionState,
) -> SessionState:
    """Validate and execute a state transition."""
    valid = VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise ValueError(
            f"Invalid session state transition: {current.value} -> {target.value}"
        )
    return target


def evaluate_convergence(
    current_state: SessionState,
    recent_message_types: list[str],
) -> SessionState:
    """Determine if negotiating should transition to converging.

    Criteria:
      - At least one 'agree' or 'synthesize' message AND
      - No 'disagree' in the last 2 turns
    """
    if current_state != SessionState.negotiating:
        return current_state
    if not recent_message_types:
        return current_state
    has_agreement = any(t in CONVERGENCE_TYPES for t in recent_message_types[-3:])
    recent_conflict = any(t in CONFLICT_TYPES for t in recent_message_types[-2:])
    if has_agreement and not recent_conflict:
        return SessionState.converging
    return current_state


def detect_deadlock(
    recent_message_types: list[str],
    deadlock_threshold: int = 5,
) -> bool:
    """Check if the session is deadlocked.

    N consecutive 'disagree' messages without any 'propose', 'refine',
    or 'clarify' in between.
    """
    consecutive_disagree = 0
    for t in reversed(recent_message_types):
        if t == "disagree":
            consecutive_disagree += 1
        elif t in ("propose", "refine", "clarify"):
            break
    return consecutive_disagree >= deadlock_threshold
