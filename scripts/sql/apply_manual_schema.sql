-- Manual schema sync for Railway staging/prod (TablePlus / Railway Query).
-- Safe to re-run: uses IF NOT EXISTS / ON CONFLICT where possible.
--
-- Workflow:
--   1. Run scripts/sql/diagnose_schema.sql
--   2. Run this file against the SAME database the app uses
--   3. Re-run diagnose_schema.sql to confirm gaps are closed
--   4. For full coach_tools seed (all tools), use scripts/setup_coach_tools.py
--
-- This replaces Alembic for environments where alembic upgrade head is unreliable.

-- =============================================================================
-- A. activities — detail enrichment + execution scoring (f014) + analytics (Tier 2)
-- =============================================================================

ALTER TABLE activities ADD COLUMN IF NOT EXISTS detail_enriched_at TIMESTAMPTZ;

ALTER TABLE activities ADD COLUMN IF NOT EXISTS matched_plan_workout_id INTEGER;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS planned_type VARCHAR(32);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS executed_type VARCHAR(32);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS zone_compliance_pct DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS pct_above_zone DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS pct_below_zone DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS run_score VARCHAR(16);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS scoring_detail JSONB;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS planned_miles DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS actual_miles DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS completion_pct DOUBLE PRECISION;

ALTER TABLE activities ADD COLUMN IF NOT EXISTS insights_system VARCHAR(16);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS easy_pct DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS z2_band_pct DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS hr_drift_pct DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS pace_spread DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS tempo_segment_pace_min_per_mi DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS tempo_segment_avg_hr_bpm DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS tempo_segment_pace_source VARCHAR(32);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS tempo_segment_split_count INTEGER;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS tempo_segment_confidence VARCHAR(8);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS tempo_qualifying_distance_mi DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_pace_min_per_mi DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_avg_hr_bpm DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_pace_source VARCHAR(32);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_split_count INTEGER;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_confidence VARCHAR(8);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_qualifying_distance_mi DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS execution_kpis_computed_at TIMESTAMPTZ;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS execution_zone_profile_at TIMESTAMPTZ;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS execution_analytics_version VARCHAR(8);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS execution_compute_status VARCHAR(24);

CREATE INDEX IF NOT EXISTS ix_activities_matched_plan_workout_id
    ON activities (matched_plan_workout_id);

DO $$
BEGIN
    ALTER TABLE activities
        ADD CONSTRAINT fk_activities_matched_plan_workout_id
        FOREIGN KEY (matched_plan_workout_id)
        REFERENCES plan_workouts (id)
        ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_activities_user_insights_system
    ON activities (user_id, insights_system)
    WHERE insights_system IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_activities_execution_stale
    ON activities (user_id, execution_kpis_computed_at)
    WHERE type = 'Run';

-- =============================================================================
-- B. user_identity — Strava onboarding gate
-- =============================================================================

ALTER TABLE user_identity
    ADD COLUMN IF NOT EXISTS initial_strava_import_completed_at TIMESTAMPTZ;

UPDATE user_identity ui
SET initial_strava_import_completed_at = now()
FROM user_athletes ua
WHERE ua.user_id = ui.user_id
  AND ui.initial_strava_import_completed_at IS NULL;

-- =============================================================================
-- C. user_profile — dual max HR (f011) + birth_year (f017)
-- Adds new columns only; does NOT drop legacy max_hr / max_hr_source.
-- =============================================================================

ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS max_hr_manual INTEGER;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS max_hr_auto INTEGER;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS max_hr_active VARCHAR(16);
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS birth_year INTEGER;

-- =============================================================================
-- D. plans — context snapshot (f015)
-- =============================================================================

ALTER TABLE plans ADD COLUMN IF NOT EXISTS context_snapshot JSONB;

-- =============================================================================
-- E. Coach + Insights tables
-- =============================================================================

CREATE TABLE IF NOT EXISTS coach_tools (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR NOT NULL UNIQUE,
    display_name      VARCHAR NOT NULL,
    category          VARCHAR NOT NULL,
    description       TEXT NOT NULL,
    when_to_call      TEXT,
    parameters_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    returns_description TEXT,
    data_source       VARCHAR,
    is_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    call_count        INTEGER NOT NULL DEFAULT 0,
    last_called_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS weekly_training_insights (
    id                 SERIAL PRIMARY KEY,
    user_id            UUID NOT NULL,
    week_start         DATE NOT NULL,
    week_end           DATE NOT NULL,
    hr_drift_pct       DOUBLE PRECISION,
    z2_pace_min_per_mi DOUBLE PRECISION,
    efficiency         DOUBLE PRECISION,
    hr_drift_band      VARCHAR(10),
    z2_pace_band       VARCHAR(10),
    efficiency_band    VARCHAR(10),
    overall_band       VARCHAR(10) NOT NULL,
    hr_drift_delta     DOUBLE PRECISION,
    z2_pace_delta      DOUBLE PRECISION,
    efficiency_delta   DOUBLE PRECISION,
    easy_avg_hr        DOUBLE PRECISION,
    easy_avg_hr_band   VARCHAR(10),
    easy_avg_hr_delta  DOUBLE PRECISION,
    easy_run_count     INTEGER NOT NULL DEFAULT 0,
    total_run_count    INTEGER NOT NULL DEFAULT 0,
    summary_text       TEXT,
    action_text        TEXT,
    kpi_snapshot       JSONB,
    generated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_insights_user_week
    ON weekly_training_insights (user_id, week_start DESC);

CREATE TABLE IF NOT EXISTS user_coach_preferences (
    user_id                   UUID PRIMARY KEY,
    coaching_level            VARCHAR NOT NULL DEFAULT 'beginner',
    run_summary_priority      JSONB,
    training_summary_priority JSONB,
    verbosity                 VARCHAR NOT NULL DEFAULT 'normal',
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runner_zone_profiles (
    user_id           UUID PRIMARY KEY NOT NULL,
    hr_z1_low         INTEGER,
    hr_z1_high        INTEGER,
    hr_z2_low         INTEGER,
    hr_z2_high        INTEGER,
    hr_z3_low         INTEGER,
    hr_z3_high        INTEGER,
    hr_z4_low         INTEGER,
    hr_z4_high        INTEGER,
    hr_z5_low         INTEGER,
    hr_z5_high        INTEGER,
    hrmax_used        INTEGER,
    resting_hr_used   INTEGER,
    zone_method       VARCHAR(16),
    pace_z2_low       INTEGER,
    pace_z2_high      INTEGER,
    pace_z3_low       INTEGER,
    pace_z3_high      INTEGER,
    pace_z4_low       INTEGER,
    pace_z4_high      INTEGER,
    pace_source       VARCHAR(20),
    pace_computed_at  TIMESTAMPTZ,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- F. Memory v2 (f016) + Phase F session/plan memory
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_state_observations (
    id                UUID PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    tag               VARCHAR(64) NOT NULL,
    body_area         VARCHAR(64),
    intensity         SMALLINT,
    text              TEXT NOT NULL,
    captured_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until       TIMESTAMPTZ NOT NULL,
    source            VARCHAR(32) NOT NULL,
    confidence        DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    conversation_id   UUID REFERENCES conversations (id) ON DELETE SET NULL,
    evidence_excerpt  TEXT
);

CREATE INDEX IF NOT EXISTS ix_user_state_observations_user_valid_until
    ON user_state_observations (user_id, valid_until);

CREATE TABLE IF NOT EXISTS user_open_threads (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    topic           VARCHAR(64) NOT NULL,
    text            TEXT NOT NULL,
    due_at          TIMESTAMPTZ NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'open',
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          VARCHAR(32) NOT NULL,
    conversation_id UUID REFERENCES conversations (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_user_open_threads_user_status_due_at
    ON user_open_threads (user_id, status, due_at);

CREATE TABLE IF NOT EXISTS coach_interactions (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    flag            VARCHAR(64) NOT NULL,
    key             VARCHAR(128) NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_coach_interactions_scope
        UNIQUE (user_id, conversation_id, flag, key)
);

CREATE INDEX IF NOT EXISTS ix_coach_interactions_user_conversation_captured_at
    ON coach_interactions (user_id, conversation_id, captured_at);

CREATE TABLE IF NOT EXISTS session_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations (id) ON DELETE SET NULL,
    summary_text    TEXT NOT NULL,
    thread_tags     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_session_summaries_user_created
    ON session_summaries (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_plan_memories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    memory_text TEXT NOT NULL,
    source      VARCHAR(32) NOT NULL,
    memory_type VARCHAR(32),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_user_plan_memories_user_created
    ON user_plan_memories (user_id, created_at DESC);

DO $$
BEGIN
    ALTER TABLE user_plan_memories
        ADD CONSTRAINT ck_user_plan_memories_source
        CHECK (source IN ('coach_tool', 'session_summary'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- G. user_phase_goals
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_phase_goals (
    id           SERIAL PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    plan_id      INTEGER NOT NULL REFERENCES plans (id) ON DELETE CASCADE,
    phase        VARCHAR(16) NOT NULL,
    goal_text    TEXT NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'active',
    source       VARCHAR(32) NOT NULL DEFAULT 'auto_proposed',
    confirmed_at TIMESTAMP,
    created_at   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_user_phase_goals_lookup
    ON user_phase_goals (user_id, plan_id, phase, status, created_at DESC);

DO $$
BEGIN
    ALTER TABLE user_phase_goals
        ADD CONSTRAINT ck_user_phase_goals_status
        CHECK (status IN ('active', 'superseded', 'completed', 'dropped'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE user_phase_goals
        ADD CONSTRAINT ck_user_phase_goals_source
        CHECK (source IN ('auto_proposed', 'coach_refined', 'user_stated'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE user_phase_goals
        ADD CONSTRAINT ck_user_phase_goals_phase
        CHECK (phase IN ('Base', 'Build', 'Peak', 'Taper'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- H. Strava ingestion retry queue (f012)
-- =============================================================================

CREATE TABLE IF NOT EXISTS strava_ingestion_retry (
    id         SERIAL PRIMARY KEY,
    user_id    VARCHAR NOT NULL REFERENCES user_identity (user_id) ON DELETE CASCADE,
    athlete_id INTEGER NOT NULL,
    run_after  TIMESTAMPTZ NOT NULL,
    attempt    INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    claimed_at TIMESTAMPTZ,
    CONSTRAINT uq_strava_ingestion_retry_user_athlete UNIQUE (user_id, athlete_id)
);

CREATE INDEX IF NOT EXISTS ix_strava_ingestion_retry_user_id
    ON strava_ingestion_retry (user_id);

CREATE INDEX IF NOT EXISTS ix_strava_ingestion_retry_athlete_id
    ON strava_ingestion_retry (athlete_id);

CREATE INDEX IF NOT EXISTS ix_strava_ingestion_retry_run_after
    ON strava_ingestion_retry (run_after);

-- =============================================================================
-- I. Product analytics (optional pilot)
-- =============================================================================

CREATE TABLE IF NOT EXISTS product_analytics_event (
    id              UUID PRIMARY KEY,
    user_id         VARCHAR,
    event_name      VARCHAR(120) NOT NULL,
    outcome         VARCHAR(64) NOT NULL,
    source          VARCHAR(32) NOT NULL DEFAULT 'server',
    correlation_id  VARCHAR(120),
    client_event_id VARCHAR(120),
    properties      JSONB,
    created_at      TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_product_analytics_event_user_created
    ON product_analytics_event (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_product_analytics_event_name_created
    ON product_analytics_event (event_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_product_analytics_event_outcome
    ON product_analytics_event (outcome);

CREATE INDEX IF NOT EXISTS idx_product_analytics_event_correlation
    ON product_analytics_event (correlation_id)
    WHERE correlation_id IS NOT NULL;

-- =============================================================================
-- J. Coach tool seed — get_training_targets (Phase 0+1)
-- =============================================================================

INSERT INTO coach_tools (
    name,
    display_name,
    category,
    description,
    when_to_call,
    parameters_schema,
    returns_description,
    data_source,
    is_enabled,
    sort_order
) VALUES (
    'get_training_targets',
    'Get Training Targets',
    'plan_creation',
    'Official training targets from canonical backend producers (same as runner-profile zones and Insights). Returns goal-aligned marathon/easy/tempo/threshold bands from the user''s target time, current-fitness pace zones from recent activities, HR guardrails, pace_authorities (plan=activity, insights=marathon goal), baseline_status, and ambition_gap summary. Never invent paces in prose — cite this tool''s numbers only. Plan prescription stays activity-calibrated; goal bands are the destination for Insights progress.',
    'After the user states a marathon target time (e.g. 3:40), before final plan confirmation, and when explaining goal pace vs this week''s plan paces. Also after successful generate_training_plan (payload may be attached to that tool result).',
    '{"type": "object", "properties": {}}'::jsonb,
    'training_target_context: schema_version, inputs (goal_aligned_status, target_time), training_pace_recommendations, pace_authorities, current_fitness, hr_guardrails, plan_phase, evidence, gap_summary.',
    'build_training_target_context → get_runner_training_pace_recommendations + get_runner_profile + compute_baseline_status_for_athlete + evaluate_ambition_gap',
    TRUE,
    38
)
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    when_to_call = EXCLUDED.when_to_call,
    parameters_schema = EXCLUDED.parameters_schema,
    returns_description = EXCLUDED.returns_description,
    data_source = EXCLUDED.data_source,
    is_enabled = EXCLUDED.is_enabled,
    sort_order = EXCLUDED.sort_order,
    updated_at = now();
