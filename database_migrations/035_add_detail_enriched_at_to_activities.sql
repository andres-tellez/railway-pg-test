-- Migration: detail_enriched_at on activities
-- Set when Strava detail + HR zone enrichment has been persisted (see activity_service.update_activity_enrichment).

ALTER TABLE activities
ADD COLUMN IF NOT EXISTS detail_enriched_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN activities.detail_enriched_at IS
'UTC time when get_activity + zones enrichment was successfully written for this row; NULL means pending detail enrichment.';
