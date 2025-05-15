-- schema.sql

-- Tokens table
CREATE TABLE IF NOT EXISTS tokens (
    athlete_id     BIGINT PRIMARY KEY,
    access_token   TEXT NOT NULL,
    refresh_token  TEXT NOT NULL,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Activities table
CREATE TABLE IF NOT EXISTS activities (
    activity_id         BIGINT PRIMARY KEY,
    athlete_id          BIGINT NOT NULL,
    name                TEXT,
    start_date          TIMESTAMP,
    distance_mi         REAL,
    moving_time_min     REAL,
    pace_min_per_mile   REAL,
    data                JSONB
);

-- Run splits table
CREATE TABLE IF NOT EXISTS run_splits (
    activity_id       BIGINT,
    segment_index     INTEGER,
    distance_m         REAL,
    elapsed_time      REAL,
    pace              REAL,
    average_heartrate REAL,
    PRIMARY KEY (activity_id, segment_index)
);
