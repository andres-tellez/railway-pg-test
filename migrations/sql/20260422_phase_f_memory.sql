-- Phase F — session summaries (Layer B) + user plan memories (Layer C)
-- Apply: psql "$DATABASE_URL" -f migrations/sql/20260422_phase_f_memory.sql

CREATE TABLE IF NOT EXISTS session_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_identity(user_id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    summary_text TEXT NOT NULL,
    thread_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_session_summaries_user_created
    ON session_summaries (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_plan_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_identity(user_id) ON DELETE CASCADE,
    memory_text TEXT NOT NULL,
    source VARCHAR(32) NOT NULL,
    memory_type VARCHAR(32) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_user_plan_memories_source
        CHECK (source IN ('coach_tool', 'session_summary'))
);

CREATE INDEX IF NOT EXISTS ix_user_plan_memories_user_created
    ON user_plan_memories (user_id, created_at DESC);

-- Rollback (manual):
-- DROP TABLE IF EXISTS user_plan_memories;
-- DROP TABLE IF EXISTS session_summaries;
