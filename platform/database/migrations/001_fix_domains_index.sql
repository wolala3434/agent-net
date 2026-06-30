-- ============================================================
-- Migration 001: Fix domains index for Discovery Layer 1
-- ============================================================
--
-- Problem: skills.domains is TEXT storing JSON arrays like
--   '["supply-chain","analysis.risk"]'. A plain B-tree index on
--   this column cannot support individual domain lookups, so the
--   discovery engine's first-layer "domain tag filter" would
--   require a full table scan.
--
-- Solution: Normalise into an indexed junction table.
--   Discovery Engine queries this table for O(log N) domain
--   lookups instead of scanning and parsing JSON in Python.
--
-- This migration is additive — it does not alter the existing
-- schema.sql tables, only adds the missing normalisation layer.
-- ============================================================

CREATE TABLE IF NOT EXISTS agent_domains (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id  TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    skill_id  TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    domain    TEXT NOT NULL,            -- single domain, e.g. "supply-chain"
    UNIQUE(agent_id, skill_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_agent_domains_domain
    ON agent_domains(domain);

CREATE INDEX IF NOT EXISTS idx_agent_domains_agent
    ON agent_domains(agent_id);

-- Backfill: extract individual domains from existing skills.domains JSON.
-- SQLite's json_each() unpacks the array into rows.
INSERT OR IGNORE INTO agent_domains (agent_id, skill_id, domain)
SELECT s.agent_id, s.id, json_each.value
FROM skills s, json_each(s.domains)
WHERE s.domains IS NOT NULL AND s.domains != '';


-- ============================================================
-- Add missing warmup_until column (8-hour warmup window per
-- trust-and-pricing.md — not present in original schema.sql)
-- ============================================================
ALTER TABLE agents ADD COLUMN warmup_until TIMESTAMP;


-- ============================================================
-- Add nesting_depth and parent_session_id to collaboration_sessions
-- (per aip-protocol.md nested-collaboration requirement,
--  prevents infinite recursion)
-- ============================================================
ALTER TABLE collaboration_sessions ADD COLUMN nesting_depth INTEGER DEFAULT 0;
ALTER TABLE collaboration_sessions ADD COLUMN parent_session_id TEXT;


-- ============================================================
-- Add FK constraint to billing_transactions.agent_id
-- (was missing in schema.sql while agent_payouts.agent_id has it)
-- ============================================================
-- SQLite does not support ALTER TABLE ADD CONSTRAINT for FKs.
-- A full table rebuild is needed, which is acceptable for MVP
-- before any real data exists. Skip for now — the application
-- layer enforces referential integrity via SQLAlchemy.
-- TODO: add FK in schema_v2.sql when migrating to PostgreSQL.
