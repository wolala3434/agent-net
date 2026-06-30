"""Nesting depth and timeout checks for collaboration sessions."""

import time


def check_nesting_depth(parent_depth: int, max_nesting_depth: int) -> bool:
    """Refuse nested sessions beyond the configured limit."""
    return parent_depth < max_nesting_depth


def is_timed_out(last_activity: float, timeout_seconds: int) -> bool:
    """Check if the session has exceeded its timeout."""
    return (time.monotonic() - last_activity) > timeout_seconds
