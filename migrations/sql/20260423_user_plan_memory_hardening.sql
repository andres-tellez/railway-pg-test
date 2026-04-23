-- Phase F hardening — memory_type on user_plan_memories
-- Apply: psql "$DATABASE_URL" -f migrations/sql/20260423_user_plan_memory_hardening.sql

ALTER TABLE user_plan_memories
    ADD COLUMN IF NOT EXISTS memory_type VARCHAR(32) NULL;

-- Rollback:
-- ALTER TABLE user_plan_memories DROP COLUMN IF EXISTS memory_type;
