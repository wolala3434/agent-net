"""
Unit tests for the Session Manager (state machine, deadlock detection, convergence).

Covers:
  - Valid state transitions
  - Invalid transitions are rejected
  - Convergence detection criteria
  - Deadlock detection threshold
  - Nesting depth limits
  - Timeout detection
"""

from __future__ import annotations

import time

import pytest

from src.platform.core.session_manager import (
    SessionManager,
    SessionState,
    VALID_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class TestStateMachine:
    @pytest.fixture
    def sm(self):
        return SessionManager()

    def test_valid_transitions(self, sm):
        """All documented transitions in aip-protocol.md must be accepted."""
        assert sm.transition(SessionState.initiated, SessionState.negotiating) == SessionState.negotiating
        assert sm.transition(SessionState.negotiating, SessionState.converging) == SessionState.converging
        assert sm.transition(SessionState.negotiating, SessionState.deadlocked) == SessionState.deadlocked
        assert sm.transition(SessionState.converging, SessionState.completed) == SessionState.completed
        assert sm.transition(SessionState.converging, SessionState.negotiating) == SessionState.negotiating
        assert sm.transition(SessionState.converging, SessionState.deadlocked) == SessionState.deadlocked

    def test_invalid_transitions_raise(self, sm):
        """Transitions not in the state diagram must be rejected."""
        invalid_pairs = [
            (SessionState.initiated, SessionState.completed),    # cannot skip
            (SessionState.negotiating, SessionState.initiated),  # cannot go back
            (SessionState.completed, SessionState.negotiating),  # terminal
            (SessionState.deadlocked, SessionState.negotiating), # terminal
        ]
        for current, target in invalid_pairs:
            with pytest.raises(ValueError, match="Invalid session state transition"):
                sm.transition(current, target)

    def test_terminal_states_have_no_exits(self):
        """Completed and deadlocked are terminal."""
        assert VALID_TRANSITIONS[SessionState.completed] == set()
        assert VALID_TRANSITIONS[SessionState.deadlocked] == set()


# ---------------------------------------------------------------------------
# Convergence detection
# ---------------------------------------------------------------------------

class TestConvergence:
    @pytest.fixture
    def sm(self):
        return SessionManager()

    def test_agreement_triggers_convergence(self, sm):
        """An 'agree' in recent messages should move negotiating → converging."""
        new_state = sm.evaluate_convergence(
            SessionState.negotiating,
            ["propose", "critique", "agree"],
        )
        assert new_state == SessionState.converging

    def test_synthesize_triggers_convergence(self, sm):
        new_state = sm.evaluate_convergence(
            SessionState.negotiating,
            ["propose", "critique", "refine", "synthesize"],
        )
        assert new_state == SessionState.converging

    def test_recent_disagree_blocks_convergence(self, sm):
        """Agreement followed by a disagree should NOT converge."""
        new_state = sm.evaluate_convergence(
            SessionState.negotiating,
            ["agree", "disagree"],
        )
        assert new_state == SessionState.negotiating

    def test_no_agreement_no_convergence(self, sm):
        new_state = sm.evaluate_convergence(
            SessionState.negotiating,
            ["propose", "critique", "propose"],
        )
        assert new_state == SessionState.negotiating

    def test_empty_history_no_change(self, sm):
        new_state = sm.evaluate_convergence(SessionState.negotiating, [])
        assert new_state == SessionState.negotiating

    def test_non_negotiating_unchanged(self, sm):
        """Convergence check only applies to negotiating state."""
        for state in [SessionState.initiated, SessionState.converging, SessionState.completed]:
            new_state = sm.evaluate_convergence(state, ["agree", "agree"])
            assert new_state == state

    def test_disagree_in_third_last_position_ok(self, sm):
        """Only last 2 turns are checked for recent conflict."""
        new_state = sm.evaluate_convergence(
            SessionState.negotiating,
            ["disagree", "refine", "agree"],  # disagree is at position -3
        )
        assert new_state == SessionState.converging


# ---------------------------------------------------------------------------
# Deadlock detection
# ---------------------------------------------------------------------------

class TestDeadlockDetection:
    @pytest.fixture
    def sm(self):
        return SessionManager(deadlock_threshold=5)

    def test_no_deadlock_with_few_disagrees(self, sm):
        assert not sm.detect_deadlock(["disagree", "disagree", "disagree", "propose"])

    def test_deadlock_with_consecutive_disagrees(self, sm):
        assert sm.detect_deadlock(["disagree", "disagree", "disagree", "disagree", "disagree"])

    def test_propose_resets_deadlock_counter(self, sm):
        """A 'propose' or 'refine' between disagrees resets the counter."""
        assert not sm.detect_deadlock([
            "disagree", "disagree", "propose", "disagree", "disagree"
        ])

    def test_refine_resets_deadlock_counter(self, sm):
        assert not sm.detect_deadlock([
            "disagree", "disagree", "disagree", "refine", "disagree"
        ])

    def test_clarify_resets_counter(self, sm):
        """A 'clarify' between disagrees shows the conversation is still productive."""
        assert not sm.detect_deadlock([
            "disagree", "disagree", "clarify", "disagree", "disagree"
        ])

    def test_exactly_at_threshold(self, sm):
        """At threshold, deadlock is detected."""
        sm.deadlock_threshold = 3
        assert sm.detect_deadlock(["disagree", "disagree", "disagree"])

    def test_below_threshold(self, sm):
        sm.deadlock_threshold = 5
        assert not sm.detect_deadlock(["disagree", "disagree", "disagree", "disagree"])

    def test_empty_history(self, sm):
        assert not sm.detect_deadlock([])

    def test_custom_threshold(self):
        sm = SessionManager(deadlock_threshold=3)
        assert sm.detect_deadlock(["disagree", "disagree", "disagree"])
        assert not sm.detect_deadlock(["disagree", "disagree"])


# ---------------------------------------------------------------------------
# Nesting depth
# ---------------------------------------------------------------------------

class TestNestingDepth:
    def test_within_limit(self):
        sm = SessionManager(max_nesting_depth=3)
        assert sm.check_nesting_depth(0) is True
        assert sm.check_nesting_depth(2) is True

    def test_at_limit(self):
        sm = SessionManager(max_nesting_depth=3)
        assert sm.check_nesting_depth(3) is False  # depth == max is rejected

    def test_beyond_limit(self):
        sm = SessionManager(max_nesting_depth=3)
        assert sm.check_nesting_depth(5) is False


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_not_timed_out(self):
        sm = SessionManager(timeout_seconds=600)
        now = time.monotonic()
        assert not sm.is_timed_out(now - 100)  # 100s ago, 600s timeout

    def test_timed_out(self):
        sm = SessionManager(timeout_seconds=600)
        now = time.monotonic()
        assert sm.is_timed_out(now - 601)

    def test_exactly_at_timeout(self):
        sm = SessionManager(timeout_seconds=600)
        now = time.monotonic()
        # is_timed_out uses strict > comparison; below timeout it is NOT timed out
        assert not sm.is_timed_out(now - 599)
        # One second more is timed out
        assert sm.is_timed_out(now - 601)


# ---------------------------------------------------------------------------
# Integration: full state machine walkthrough
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    """Simulate a realistic session through all states."""

    def test_happy_path(self):
        sm = SessionManager(deadlock_threshold=5, max_turns=50)

        # Create → initiated→negotiating (auto-transition)
        state = SessionState.initiated
        state = sm.transition(state, SessionState.negotiating)

        # Round 1: propose
        state = sm.evaluate_convergence(state, ["propose"])
        assert state == SessionState.negotiating

        # Round 2-6: negotiate with agreement
        history = ["propose", "critique", "refine", "agree"]
        state = sm.evaluate_convergence(state, history)
        assert state == SessionState.converging

        # Move to completed (via synthesize)
        state = sm.transition(state, SessionState.completed)
        assert state == SessionState.completed

    def test_deadlock_path(self):
        sm = SessionManager(deadlock_threshold=5, max_turns=50)

        state = SessionState.initiated
        state = sm.transition(state, SessionState.negotiating)

        # 5 consecutive disagrees → deadlocked
        assert sm.detect_deadlock(
            ["disagree", "disagree", "disagree", "disagree", "disagree"]
        )
