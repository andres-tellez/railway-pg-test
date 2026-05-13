-- Per-user gate for persisting mile splits after first full Strava onboarding.
-- Apply: psql "$DATABASE_URL" -f migrations/sql/20260428_initial_strava_import_completed_at.sql

ALTER TABLE user_identity
    ADD COLUMN IF NOT EXISTS initial_strava_import_completed_at TIMESTAMPTZ NULL;

-- Existing Strava-linked users: treat onboarding as already done so splits stay enabled.
UPDATE user_identity ui
SET initial_strava_import_completed_at = now()
FROM user_athletes ua
WHERE ua.user_id = ui.user_id
  AND ui.initial_strava_import_completed_at IS NULL;

-- Rollback (manual):
-- ALTER TABLE user_identity DROP COLUMN IF EXISTS initial_strava_import_completed_at;
