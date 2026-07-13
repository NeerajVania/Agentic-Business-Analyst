-- database/init.sql
-- PostgreSQL schema for Agentic Data Analyst

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Sessions ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     TEXT,
    metadata    JSONB DEFAULT '{}'
);

-- ── Datasets ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS datasets (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id   UUID REFERENCES sessions(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    rows         INTEGER,
    columns      INTEGER,
    schema       JSONB DEFAULT '{}',
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Analyses ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id     UUID REFERENCES sessions(id) ON DELETE CASCADE,
    query          TEXT NOT NULL,
    execution_plan JSONB DEFAULT '[]',
    insights       JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    kpi_summary    JSONB DEFAULT '{}',
    anomaly_count  INTEGER DEFAULT 0,
    report_path    TEXT,
    processing_sec FLOAT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Reports ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID REFERENCES sessions(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,
    format      TEXT NOT NULL,   -- html | markdown | pdf
    file_path   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        TEXT UNIQUE NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_session ON analyses(session_id);
CREATE INDEX IF NOT EXISTS idx_datasets_session ON datasets(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_session ON reports(session_id);