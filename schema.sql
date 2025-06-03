-- tokens table
CREATE TABLE tokens (
    athlete_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL
);

-- activities table
CREATE TABLE activities (
    activity_id BIGINT PRIMARY KEY,
    athlete_id BIGINT NOT NULL,
    name TEXT,
    type TEXT,
    start_date TIMESTAMP,
    distance FLOAT,
    elapsed_time INTEGER,
    moving_time INTEGER,
    total_elevation_gain FLOAT,
    external_id TEXT,
    timezone TEXT
);
