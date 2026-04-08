-- ═══════════════════════════════════════════════════════════════════════════════
--  SENTINEL v3.0 — Supabase Migration
-- ═══════════════════════════════════════════════════════════════════════════════
--  Run this in your Supabase SQL Editor to create the required tables.
--  Dashboard → SQL Editor → New Query → Paste → Run
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── Audit Events ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
    id              BIGSERIAL PRIMARY KEY,
    audit_id        VARCHAR(36) UNIQUE NOT NULL,
    request_id      VARCHAR(36) NOT NULL,
    tenant_id       VARCHAR(64) NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    decision        VARCHAR(10) NOT NULL,           -- ALLOW / REWRITE / BLOCK
    aggregate_score DOUBLE PRECISION NOT NULL,
    triggering_agent VARCHAR(64),
    agent_scores    TEXT,                            -- JSON
    compliance_tags TEXT,                            -- JSON array
    prompt_hash     VARCHAR(64) NOT NULL,            -- SHA-256
    rewritten       BOOLEAN DEFAULT FALSE,
    latency_ms      DOUBLE PRECISION,
    signature       TEXT,                            -- HMAC attestation
    explanation     TEXT                             -- v3: explainability engine
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_events(tenant_id, decision);

-- ── Tenant Records ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenant_records (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           VARCHAR(64) UNIQUE NOT NULL,
    name                VARCHAR(128) NOT NULL,
    email               VARCHAR(256) UNIQUE NOT NULL,
    password_hash       VARCHAR(256) NOT NULL,
    use_case            VARCHAR(64) DEFAULT 'general',
    stripe_customer_id  VARCHAR(64),
    plan                VARCHAR(32) DEFAULT 'oss_core',
    pricing_tier        VARCHAR(32) DEFAULT 'oss_core',
    compliance_region   VARCHAR(32) DEFAULT 'global',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_tenant_id ON tenant_records(tenant_id);

-- ── Policy Records ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS policy_records (
    id                        BIGSERIAL PRIMARY KEY,
    tenant_id                 VARCHAR(64) UNIQUE NOT NULL,
    use_case                  VARCHAR(64) DEFAULT 'general',
    injection_threshold       DOUBLE PRECISION DEFAULT 0.85,
    pii_threshold             DOUBLE PRECISION DEFAULT 0.70,
    toxicity_threshold        DOUBLE PRECISION DEFAULT 0.60,
    hallucination_threshold   DOUBLE PRECISION DEFAULT 0.50,
    jailbreak_threshold       DOUBLE PRECISION DEFAULT 0.75,
    response_safety_threshold DOUBLE PRECISION DEFAULT 0.50,
    multilingual_threshold    DOUBLE PRECISION DEFAULT 0.65,
    tool_call_threshold       DOUBLE PRECISION DEFAULT 0.60,
    brand_guard_threshold     DOUBLE PRECISION DEFAULT 0.50,
    token_anomaly_threshold   DOUBLE PRECISION DEFAULT 0.60,
    lower_threshold           DOUBLE PRECISION DEFAULT 0.35,
    upper_threshold           DOUBLE PRECISION DEFAULT 0.70,
    pii_action                VARCHAR(16) DEFAULT 'redact',
    allow_rewrite             BOOLEAN DEFAULT TRUE,
    compliance_region         VARCHAR(16) DEFAULT 'global',
    dpdp_enabled              BOOLEAN DEFAULT FALSE,
    rbi_framework_enabled     BOOLEAN DEFAULT FALSE,
    shadow_mode               BOOLEAN DEFAULT FALSE,
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_tenant ON policy_records(tenant_id);

-- ── Row Level Security (RLS) ─────────────────────────────────────────────────
-- Enable RLS on all tables. The service_role key bypasses RLS,
-- so the SENTINEL Gateway (using service_key) has full access.
-- The anon key is restricted.

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_records ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by SENTINEL Gateway)
CREATE POLICY "Service role full access on audit_events"
    ON audit_events FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on tenant_records"
    ON tenant_records FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on policy_records"
    ON policy_records FOR ALL
    USING (auth.role() = 'service_role');

-- ══════════════════════════════════════════════════════════════════════════════
--  Done! Your Supabase project is ready for SENTINEL.
--  Set these in your .env:
--    DATABASE_BACKEND=supabase
--    SUPABASE_URL=https://your-project.supabase.co
--    SUPABASE_SERVICE_KEY=your-service-role-key
-- ══════════════════════════════════════════════════════════════════════════════
