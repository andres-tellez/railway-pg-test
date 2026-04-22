-- Migration: create user_phase_goals table (V1.6 Phase D / 3D.1)
--
-- Author:  SmartCoach — PHASE_3_IMPLEMENTATION_CHECKLIST 3D.1
-- Date:    2026-04-21
--
-- Purpose:
--   Store each athlete's current focus/goal for a single training
--   phase (Base / Build / Peak / Taper) of a single plan. One active
--   goal per (user, plan, phase); supersede-then-insert pattern keeps
--   goal history without a partial unique index (SQLite-portable).
--
--   See src/db/models/user_phase_goals.py for the ORM model + column
--   rationale, and SMARTCOACH_SYSTEM_SPEC_V1.md §19.4 for the UX
--   contract that consumes this table.
--
-- Apply (Railway / Postgres):
--   psql "$DATABASE_URL" -f migrations/sql/20260421_create_user_phase_goals.sql
--
-- Rollback: see bottom of file (commented DOWN section).

BEGIN;

CREATE TABLE IF NOT EXISTS user_phase_goals (
    id           SERIAL PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES user_identity(user_id) ON DELETE CASCADE,
    plan_id      INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    phase        VARCHAR(16) NOT NULL,
    goal_text    TEXT NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'active',
    source       VARCHAR(32) NOT NULL DEFAULT 'auto_proposed',
    confirmed_at TIMESTAMP NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- Hot-path lookup: "give me the latest active goal for (user, plan,
-- phase)". The descending created_at keeps the supersede history
-- neighbour cheap.
CREATE INDEX IF NOT EXISTS ix_user_phase_goals_lookup
    ON user_phase_goals (user_id, plan_id, phase, status, created_at DESC);

-- Guardrail check constraints — stored as text columns (not native
-- ENUMs) so the allowed set can evolve without a second migration,
-- but we still refuse bogus writes at the DB level. App-layer enum
-- modules (src/db/models/user_phase_goals.py) remain the single
-- source of truth; these constraints just ward against direct
-- psql writes.
ALTER TABLE user_phase_goals
    ADD CONSTRAINT ck_user_phase_goals_status
        CHECK (status IN ('active', 'superseded', 'completed', 'dropped'));

ALTER TABLE user_phase_goals
    ADD CONSTRAINT ck_user_phase_goals_source
        CHECK (source IN ('auto_proposed', 'coach_refined', 'user_stated'));

ALTER TABLE user_phase_goals
    ADD CONSTRAINT ck_user_phase_goals_phase
        CHECK (phase IN ('Base', 'Build', 'Peak', 'Taper'));

COMMIT;

-- --------------------------------------------------------------------
-- DOWN (manual rollback — uncomment to apply):
-- --------------------------------------------------------------------
-- BEGIN;
-- DROP INDEX IF EXISTS ix_user_phase_goals_lookup;
-- DROP TABLE IF EXISTS user_phase_goals;
-- COMMIT;
