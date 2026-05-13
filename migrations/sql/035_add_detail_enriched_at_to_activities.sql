-- Activities: mark when Strava detail API enrichment (zones, etc.) completed.
-- Safe to run more than once.
ALTER TABLE activities
    ADD COLUMN IF NOT EXISTS detail_enriched_at TIMESTAMPTZ NULL;
