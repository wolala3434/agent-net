"""SQLAlchemy ORM models (mirrors database/schema.sql)."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    LargeBinary,
    REAL,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase

from .constants import (
    AgentStatus,
    TrialStatus,
    HealthStatus,
    TaskStatus,
    SessionStatus,
    DEFAULT_FREE_QUOTA,
)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
class Agent(Base):
    __tablename__ = "agents"

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    version = Column(Text, nullable=False, default="1.0.0")
    provider_name = Column(Text)
    provider_url = Column(Text)
    description = Column(Text)
    card_json = Column(Text, nullable=False)
    capability_embedding = Column(LargeBinary)  # Binary vector data
    status = Column(Text, nullable=False, default=AgentStatus.ACTIVE.value)
    endpoint_url = Column(Text)
    health_status = Column(Text, default=HealthStatus.UNKNOWN.value)
    auth_type = Column(Text, default="none")

    free_quota_total = Column(Integer, default=DEFAULT_FREE_QUOTA)
    free_quota_used = Column(Integer, default=0)
    trial_status = Column(Text, default=TrialStatus.TRIAL.value)
    warmup_until = Column(TIMESTAMP, nullable=True)  # 8h warmup window

    total_tasks = Column(Integer, default=0)
    successful_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    avg_rating = Column(REAL, default=0.0)
    avg_latency_ms = Column(REAL, default=0.0)
    credit_score = Column(REAL, default=0.5)

    registered_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    last_heartbeat_at = Column(TIMESTAMP)


# ---------------------------------------------------------------------------
# Skills (Agent capabilities)
# ---------------------------------------------------------------------------
class Skill(Base):
    __tablename__ = "skills"

    id = Column(Text, primary_key=True)
    agent_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    input_schema = Column(Text, nullable=False)
    output_schema = Column(Text, nullable=False)
    domains = Column(Text, nullable=False)
    execution_type = Column(Text, default="synchronous")
    estimated_cost = Column(Text, default="low")
    estimated_duration = Column(Text, default="short")
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Text, primary_key=True)
    description = Column(Text)
    input_json = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default=TaskStatus.PENDING.value)
    assigned_agent_id = Column(Text)
    result_json = Column(Text)
    error_json = Column(Text)
    pipeline_json = Column(Text)
    priority = Column(Text, default="normal")
    user_id = Column(Text)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(TIMESTAMP)


# ---------------------------------------------------------------------------
# Task Steps (sequential multi-agent pipeline)
# ---------------------------------------------------------------------------
class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(Text, primary_key=True)
    task_id = Column(Text, nullable=False)
    sequence = Column(Integer, nullable=False)
    agent_id = Column(Text, nullable=False)
    skill_id = Column(Text)
    input_json = Column(Text)
    output_json = Column(Text)
    status = Column(Text, nullable=False, default=TaskStatus.PENDING.value)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    error_json = Column(Text)


# ---------------------------------------------------------------------------
# Messages (AIP audit log)
# ---------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Text, nullable=False, unique=True)
    correlation_id = Column(Text)
    sender_type = Column(Text, nullable=False)
    sender_id = Column(Text, nullable=False)
    recipient_type = Column(Text, nullable=False)
    recipient_id = Column(Text, nullable=False)
    message_type = Column(Text, nullable=False)
    body_json = Column(Text)
    status = Column(Text, default="sent")
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Collaboration Sessions
# ---------------------------------------------------------------------------
class CollaborationSession(Base):
    __tablename__ = "collaboration_sessions"

    id = Column(Text, primary_key=True)
    task_id = Column(Text)
    status = Column(Text, nullable=False, default=SessionStatus.INITIATED.value)
    goal = Column(Text, nullable=False)
    shared_context = Column(Text, nullable=False, default="{}")
    participants_json = Column(Text, nullable=False)
    result_json = Column(Text)
    turn_count = Column(Integer, default=0)
    nesting_depth = Column(Integer, default=0)  # prevent infinite recursion
    parent_session_id = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(TIMESTAMP)


# ---------------------------------------------------------------------------
# Collaboration Messages
# ---------------------------------------------------------------------------
class CollaborationMessage(Base):
    __tablename__ = "collaboration_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Text, nullable=False, unique=True)
    session_id = Column(Text, nullable=False)
    turn_number = Column(Integer, nullable=False)
    sender_id = Column(Text, nullable=False)
    message_type = Column(Text, nullable=False)
    references_to = Column(Text)
    body_json = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# User Pinned Agents
# ---------------------------------------------------------------------------
class UserPinnedAgent(Base):
    __tablename__ = "user_pinned_agents"
    __table_args__ = (UniqueConstraint("user_id", "agent_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False)
    agent_id = Column(Text, nullable=False)
    pinned_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    note = Column(Text)


# ---------------------------------------------------------------------------
# Agent Reviews
# ---------------------------------------------------------------------------
class AgentReview(Base):
    __tablename__ = "agent_reviews"
    __table_args__ = (UniqueConstraint("user_id", "task_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    task_id = Column(Text)
    session_id = Column(Text)
    rating = Column(Integer, nullable=False)
    review_text = Column(Text)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Billing Accounts
# ---------------------------------------------------------------------------
class BillingAccount(Base):
    __tablename__ = "billing_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, unique=True)
    balance = Column(REAL, default=0.0)
    total_deposited = Column(REAL, default=0.0)
    total_spent = Column(REAL, default=0.0)
    free_credit = Column(REAL, default=5.00)
    auto_recharge = Column(Integer, default=0)
    auto_amount = Column(REAL, default=20.00)
    auto_threshold = Column(REAL, default=5.00)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Billing Transactions
# ---------------------------------------------------------------------------
class BillingTransaction(Base):
    __tablename__ = "billing_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False)
    agent_id = Column(Text, nullable=False)
    task_id = Column(Text)
    session_id = Column(Text)
    amount = Column(REAL, nullable=False)
    agent_earning = Column(REAL, nullable=False)
    platform_fee = Column(REAL, nullable=False)
    pricing_model = Column(Text, nullable=False)
    unit_price = Column(REAL, nullable=False)
    units = Column(REAL, nullable=False)
    is_free = Column(Integer, default=0)
    free_source = Column(Text)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Agent Payouts
# ---------------------------------------------------------------------------
class AgentPayout(Base):
    __tablename__ = "agent_payouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Text, nullable=False)
    period_start = Column(TIMESTAMP, nullable=False)
    period_end = Column(TIMESTAMP, nullable=False)
    total_earned = Column(REAL, nullable=False)
    platform_fee = Column(REAL, nullable=False)
    net_amount = Column(REAL, nullable=False)
    status = Column(Text, default=TaskStatus.PENDING.value)
    paid_at = Column(TIMESTAMP)
    stripe_payout_id = Column(Text)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
