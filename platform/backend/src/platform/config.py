"""
Centralised configuration loaded from environment variables / .env file.

Covers gaps identified in doc review:
  - Auth settings (previously entirely missing)
  - Deadlock detection thresholds (previously undefined)
  - Session nesting depth limit (previously undefined)
  - Embedding model configuration
  - Billing parameters
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[4]  # agent-internet/


@dataclass
class Settings:
    # --- Server ---
    env: str = os.getenv("ENV", "dev")
    host: str = os.getenv("REGISTRY_HOST", "0.0.0.0")
    port: int = int(os.getenv("REGISTRY_PORT", "8000"))
    advertised_host: str = os.getenv("ADVERTISED_HOST", "127.0.0.1")
    database_url: str = os.getenv(
        "REGISTRY_DATABASE_URL",
        f"sqlite+aiosqlite:///{PROJECT_ROOT / 'data' / 'registry.db'}",
    )
    log_level: str = os.getenv("REGISTRY_LOG_LEVEL", "INFO")

    # --- Embedding ---
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    hf_endpoint: str = os.getenv("HF_ENDPOINT", "")

    # --- Discovery ---
    discovery_epsilon: float = float(os.getenv("DISCOVERY_EPSILON", "0.15"))
    discovery_newcomer_boost: float = float(os.getenv("DISCOVERY_NEWCOMER_BOOST", "0.10"))
    discovery_newcomer_days: int = int(os.getenv("DISCOVERY_NEWCOMER_DAYS", "30"))
    discovery_diversity_penalty: float = float(os.getenv("DISCOVERY_DIVERSITY_PENALTY", "0.05"))

    # --- Session ---
    session_max_turns: int = int(os.getenv("SESSION_MAX_TURNS", "50"))
    session_deadlock_threshold: int = int(os.getenv("SESSION_DEADLOCK_THRESHOLD", "5"))
    session_timeout_seconds: int = int(os.getenv("SESSION_TIMEOUT_SECONDS", "600"))
    session_max_nesting_depth: int = int(os.getenv("SESSION_MAX_NESTING_DEPTH", "3"))

    # --- Billing ---
    platform_fee_rate: float = float(os.getenv("BILLING_PLATFORM_FEE_RATE", "0.15"))
    payout_threshold: float = float(os.getenv("BILLING_PAYOUT_THRESHOLD", "50.0"))
    free_trial_quota: int = int(os.getenv("FREE_TRIAL_QUOTA", "100"))
    free_trial_extension: int = int(os.getenv("FREE_TRIAL_EXTENSION", "50"))
    user_signup_credit: float = float(os.getenv("USER_SIGNUP_CREDIT", "5.00"))

    # --- Trial warmup window (8 hours per trust-and-pricing.md) ---
    warmup_window_hours: int = 8

    # --- CORS ---
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501")

    # --- Auth ---
    disable_auth: bool = os.getenv("DISABLE_AUTH", "false").lower() == "true"
    agent_api_key_prefix: str = os.getenv("AGENT_API_KEY_PREFIX", "ait_")
    user_jwt_secret: str = os.getenv("USER_JWT_SECRET", "insecure-dev-secret")
    user_jwt_algorithm: str = os.getenv("USER_JWT_ALGORITHM", "HS256")
    user_jwt_expire_minutes: int = int(os.getenv("USER_JWT_EXPIRE_MINUTES", "1440"))

    # --- Stripe ---
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # --- Rate limiting ---
    rate_limit_requests_per_minute: int = 60
    rate_limit_window: float = float(os.getenv("RATE_LIMIT_WINDOW", "60.0"))
    rate_limit_cleanup_interval: int = int(os.getenv("RATE_LIMIT_CLEANUP_INTERVAL", "200"))
    rate_limit_max_buckets: int = int(os.getenv("RATE_LIMIT_MAX_BUCKETS", "50000"))
    agent_max_concurrent_sessions: int = 10


settings = Settings()
