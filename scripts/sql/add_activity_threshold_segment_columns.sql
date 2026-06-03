-- Manual migration (Railway): Threshold/Z4 segment columns on activities (A1).
-- Prefer scripts/sql/apply_manual_schema.sql for full idempotent sync.

ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_pace_min_per_mi DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_avg_hr_bpm DOUBLE PRECISION;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_pace_source VARCHAR(32);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_split_count INTEGER;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_segment_confidence VARCHAR(8);
ALTER TABLE activities ADD COLUMN IF NOT EXISTS threshold_qualifying_distance_mi DOUBLE PRECISION;
