-- Agent Internet Platform — Database Schema
-- SQLite with WAL mode for MVP

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ==========================================
-- 1. AGENTS
-- ==========================================
CREATE TABLE IF NOT EXISTS agents (
    id                      TEXT PRIMARY KEY,          -- "com.example.summarizer@1.0.0"
    name                    TEXT NOT NULL,
    version                 TEXT NOT NULL DEFAULT '1.0.0',
    provider_name           TEXT,
    provider_url            TEXT,
    description             TEXT,
    card_json               TEXT NOT NULL,             -- 完整 ADL JSON（权威数据源）
                                                    -- name/version/provider_* 列为反规范化缓存，
                                                    -- 由应用层在 register/update 时保持同步
    capability_embedding    BLOB,                      -- 384d float32 embedding
    status                  TEXT NOT NULL DEFAULT 'active',  -- active, inactive, suspended
    endpoint_url            TEXT,
    health_status           TEXT DEFAULT 'unknown',    -- healthy, degraded, unhealthy
    auth_type               TEXT DEFAULT 'none',

    -- 试用与信任
    free_quota_total        INTEGER DEFAULT 100,
    free_quota_used         INTEGER DEFAULT 0,
    trial_status            TEXT DEFAULT 'trial',      -- trial, verified, probation, low_quality

    -- 质量统计
    total_tasks             INTEGER DEFAULT 0,
    successful_tasks        INTEGER DEFAULT 0,
    failed_tasks            INTEGER DEFAULT 0,
    avg_rating              REAL DEFAULT 0.0,
    avg_latency_ms          REAL DEFAULT 0.0,
    credit_score            REAL DEFAULT 0.5,          -- [0, 1]

    registered_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat_at       TIMESTAMP
);

-- ==========================================
-- 2. SKILLS
-- ==========================================
CREATE TABLE IF NOT EXISTS skills (
    id                  TEXT PRIMARY KEY,       -- "agent_id/skill_id"
    agent_id            TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    description         TEXT,
    input_schema        TEXT NOT NULL,          -- JSON Schema
    output_schema       TEXT NOT NULL,          -- JSON Schema
    domains             TEXT NOT NULL,          -- JSON array: ["research.web", ...]
    execution_type      TEXT DEFAULT 'synchronous',
    estimated_cost      TEXT DEFAULT 'low',
    estimated_duration  TEXT DEFAULT 'short',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skills_agent ON skills(agent_id);
CREATE INDEX IF NOT EXISTS idx_skills_domains ON skills(domains);

-- ==========================================
-- 3. TASKS
-- ==========================================
CREATE TABLE IF NOT EXISTS tasks (
    id                  TEXT PRIMARY KEY,
    description         TEXT,
    input_json          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
                        -- pending → discovered → assigned → running → completed / failed / cancelled
    assigned_agent_id   TEXT,
    result_json         TEXT,
    error_json          TEXT,
    pipeline_json       TEXT,
    priority            TEXT DEFAULT 'normal',
    user_id             TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);

-- ==========================================
-- 4. TASK STEPS (sequential multi-agent pipeline)
--
-- 用于顺序流水线模式：Agent A → Agent B → Agent C，每步的输出
-- 是下一步的输入。与 collaboration_sessions 的区别：
--   - task_steps:     串行流水线（一个 Agent 完成后再调下一个）
--   - collaboration:  并行讨论（多个 Agent 同时参与多轮对话）
-- ==========================================
CREATE TABLE IF NOT EXISTS task_steps (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    sequence        INTEGER NOT NULL,
    agent_id        TEXT NOT NULL,
    skill_id        TEXT,
    input_json      TEXT,
    output_json     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    error_json      TEXT
);

CREATE INDEX IF NOT EXISTS idx_steps_task ON task_steps(task_id);

-- ==========================================
-- 5. MESSAGES (AIP audit log)
-- ==========================================
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT NOT NULL UNIQUE,
    correlation_id  TEXT,
    sender_type     TEXT NOT NULL,       -- agent, gateway, registry, dashboard
    sender_id       TEXT NOT NULL,
    recipient_type  TEXT NOT NULL,
    recipient_id    TEXT NOT NULL,
    message_type    TEXT NOT NULL,       -- L1 消息类型: register, deregister, heartbeat,
                                            --   task_assign, task_result, task_status,
                                            --   task_error, task_cancel
    body_json       TEXT,
    status          TEXT DEFAULT 'sent',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_correlation ON messages(correlation_id);

-- ==========================================
-- 6. COLLABORATION SESSIONS
-- ==========================================
CREATE TABLE IF NOT EXISTS collaboration_sessions (
    id                  TEXT PRIMARY KEY,          -- "sess_abc123"
    task_id             TEXT REFERENCES tasks(id),
    status              TEXT NOT NULL DEFAULT 'initiated',
                        -- initiated → negotiating → converging → completed / deadlocked
    goal                TEXT NOT NULL,
    shared_context      TEXT NOT NULL DEFAULT '{}',-- 共享白板 JSON
    participants_json   TEXT NOT NULL,             -- 参与者列表 JSON
    result_json         TEXT,
    turn_count          INTEGER DEFAULT 0,
    nesting_depth       INTEGER DEFAULT 0,         -- prevent infinite recursion
    parent_session_id   TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collab_sessions_task ON collaboration_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_collab_sessions_status ON collaboration_sessions(status);

-- ==========================================
-- 7. COLLABORATION MESSAGES
-- ==========================================
CREATE TABLE IF NOT EXISTS collaboration_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT NOT NULL UNIQUE,
    session_id      TEXT NOT NULL REFERENCES collaboration_sessions(id) ON DELETE CASCADE,
    turn_number     INTEGER NOT NULL,
    sender_id       TEXT NOT NULL,
    message_type    TEXT NOT NULL,       -- propose, critique, clarify, refine, agree, disagree, synthesize
    references_to   TEXT,                -- JSON array
    body_json       TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collab_msgs_session ON collaboration_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_collab_msgs_turn ON collaboration_messages(session_id, turn_number);

-- ==========================================
-- 8. USER PINNED AGENTS
-- ==========================================
CREATE TABLE IF NOT EXISTS user_pinned_agents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    pinned_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note            TEXT,
    UNIQUE(user_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_pinned_user ON user_pinned_agents(user_id);
CREATE INDEX IF NOT EXISTS idx_pinned_agent ON user_pinned_agents(agent_id);

-- ==========================================
-- 9. AGENT REVIEWS
-- ==========================================
CREATE TABLE IF NOT EXISTS agent_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    task_id         TEXT,
    session_id      TEXT,
    rating          INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    review_text     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_agent ON agent_reviews(agent_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON agent_reviews(agent_id, rating);

-- ==========================================
-- 10. BILLING ACCOUNTS
-- ==========================================
CREATE TABLE IF NOT EXISTS billing_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL UNIQUE,
    balance         REAL DEFAULT 0.0,
    total_deposited REAL DEFAULT 0.0,
    total_spent     REAL DEFAULT 0.0,
    free_credit     REAL DEFAULT 5.00,            -- 新用户 $5 赠金
    auto_recharge   INTEGER DEFAULT 0,
    auto_amount     REAL DEFAULT 20.00,
    auto_threshold  REAL DEFAULT 5.00,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 11. BILLING TRANSACTIONS
-- ==========================================
CREATE TABLE IF NOT EXISTS billing_transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    agent_id        TEXT NOT NULL,
    task_id         TEXT,
    session_id      TEXT,
    amount          REAL NOT NULL,              -- 用户实付（含平台费）
    agent_earning   REAL NOT NULL,              -- Agent 收入
    platform_fee    REAL NOT NULL,              -- 平台抽成
    pricing_model   TEXT NOT NULL,              -- per_call, per_minute, per_token
    unit_price      REAL NOT NULL,
    units           REAL NOT NULL,
    is_free         INTEGER DEFAULT 0,          -- 是否免费
    free_source     TEXT,                       -- 'agent_trial', 'user_credit'
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_billing_user ON billing_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_agent ON billing_transactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_billing_created ON billing_transactions(created_at DESC);

-- ==========================================
-- 12. AGENT PAYOUTS
-- ==========================================
CREATE TABLE IF NOT EXISTS agent_payouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    period_start    TIMESTAMP NOT NULL,
    period_end      TIMESTAMP NOT NULL,
    total_earned    REAL NOT NULL,
    platform_fee    REAL NOT NULL,
    net_amount      REAL NOT NULL,
    status          TEXT DEFAULT 'pending',     -- pending, paid, failed
    paid_at         TIMESTAMP,
    stripe_payout_id TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payouts_agent ON agent_payouts(agent_id);
CREATE INDEX IF NOT EXISTS idx_payouts_status ON agent_payouts(status);
