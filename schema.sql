-- Tokens table
CREATE TABLE IF NOT EXISTS tokens (
    athlete_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL
);

-- Activities table (aligned to ORM model)
CREATE TABLE IF NOT EXISTS activities (
    activity_id BIGINT PRIMARY KEY,
    athlete_id BIGINT NOT NULL,
    name TEXT,
    start_date TIMESTAMP,
    distance_mi FLOAT,
    moving_time_min FLOAT,
    pace_min_per_mile FLOAT,
    data JSONB
);
