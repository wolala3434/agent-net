"""
Constants and enumerations for the Platform.

Centralizes status enums and business constants to eliminate
hardcoded strings and magic numbers throughout the codebase.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Status Enums
# ---------------------------------------------------------------------------

class AgentStatus(str, Enum):
    """Agent lifecycle status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class TrialStatus(str, Enum):
    """Agent trial/verification status."""
    TRIAL = "trial"
    VERIFIED = "verified"
    PROBATION = "probation"
    LOW_QUALITY = "low_quality"


class HealthStatus(str, Enum):
    """Agent health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SessionStatus(str, Enum):
    """Collaboration session status."""
    INITIATED = "initiated"
    NEGOTIATING = "negotiating"
    CONVERGING = "converging"
    COMPLETED = "completed"
    DEADLOCKED = "deadlocked"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    DISCOVERED = "discovered"
    ASSIGNED = "assigned"
    RUNNING = "running"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Business Constants
# ---------------------------------------------------------------------------

# User
DEFAULT_USER_ID = "anonymous"

# Free quota
DEFAULT_FREE_QUOTA = 100

# Monetary amounts
DEFAULT_SIGNUP_CREDIT = 5.00
DEFAULT_AUTO_AMOUNT = 20.00
DEFAULT_AUTO_THRESHOLD = 5.00

# UUID truncation lengths
UUID_TRUNCATE_LEN = 12
LOG_ID_TRUNCATE_LEN = 30
DESCRIPTION_TRUNCATE_LEN = 200

# Time
SECONDS_PER_DAY = 86400

# Rating factors (default values, can be overridden by settings)
RATING_EXCELLENT_THRESHOLD = 4.5
RATING_GOOD_THRESHOLD = 3.5
RATING_POOR_THRESHOLD = 2.5
RATING_EXCELLENT_MULTIPLIER = 1.15
RATING_GOOD_MULTIPLIER = 1.00
RATING_POOR_MULTIPLIER = 0.85
RATING_BAD_MULTIPLIER = 0.60
LOW_REVIEW_COUNT_THRESHOLD = 10
LOW_REVIEW_PENALTY = 0.90
