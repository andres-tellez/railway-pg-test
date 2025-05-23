-- Tokens table
CREATE TABLE IF NOT EXISTS tokens (
    athlete_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL
);

-- Activities table
CREATE TABLE IF NOT EXISTS activities (
    activity_id BIGINT PRIMARY KEY,
    athlete_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    distance REAL,
    moving_time INTEGER,
    elapsed_time INTEGER,
    total_elevation_gain REAL,
    type TEXT,
    workout_type TEXT,
    average_speed REAL,
    max_speed REAL,
    average_heartrate REAL,
    max_heartrate REAL
);

-- Run splits table
CREATE TABLE IF NOT EXISTS run_splits (
    activity_id BIGINT NOT NULL,
    split_index INTEGER NOT NULL,
    split_distance REAL NOT NULL,
    split_time INTEGER NOT NULL,
    split_pace REAL,
    PRIMARY KEY (activity_id, split_index),
    FOREIGN KEY (activity_id) REFERENCES activities (activity_id)
);

-- Tasks table for coaching task tracking
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);