-- Table: activities

CREATE TABLE IF NOT EXISTS activities (
    id BIGINT PRIMARY KEY,  -- internal surrogate PK
    activity_id BIGINT UNIQUE,  -- Strava ID
    athlete_id BIGINT,

    -- Core fields
    name TEXT,
    distance FLOAT,
    moving_time INT,
    elapsed_time INT,
    total_elevation_gain FLOAT,
    type TEXT,
    sport_type TEXT,
    start_date TEXT,
    start_date_local TEXT,
    timezone TEXT,
    utc_offset FLOAT,

    -- Engagement
    achievement_count INT,
    kudos_count INT,
    comment_count INT,
    athlete_count INT,
    photo_count INT,

    -- Flags
    trainer BOOLEAN,
    commute BOOLEAN,
    manual BOOLEAN,
    private BOOLEAN,
    flagged BOOLEAN,
    visibility TEXT,

    -- Gear
    gear_id TEXT,

    -- Performance
    average_speed FLOAT,
    max_speed FLOAT,
    average_cadence FLOAT,
    average_temp INT,
    average_heartrate FLOAT,
    max_heartrate FLOAT,

    -- Fields that caused your previous test failures:
    suffer_score INT,
    hr_zone_1 INT,
    hr_zone_2 INT,
    hr_zone_3 INT,
    hr_zone_4 INT,
    hr_zone_5 INT,

    -- Derived fields for unit conversions / downstream reporting
    conv_distance FLOAT,
    conv_elevation_feet FLOAT,
    conv_avg_speed FLOAT,
    conv_max_speed FLOAT,
    hr_zone_1_pct FLOAT,
    hr_zone_2_pct FLOAT,
    hr_zone_3_pct FLOAT,
    hr_zone_4_pct FLOAT,
    hr_zone_5_pct FLOAT,
    calories FLOAT,
    external_id TEXT
);

-- Table: tokens

CREATE TABLE IF NOT EXISTS tokens (
    athlete_id TEXT PRIMARY KEY,
    access_token TEXT,
    refresh_token TEXT,
    expires_at BIGINT
);

-- Table: splits

CREATE TABLE IF NOT EXISTS splits (
    id SERIAL PRIMARY KEY,
    activity_id BIGINT,
    lap_index INT,
    distance FLOAT,
    elapsed_time INT,
    moving_time INT,
    average_speed FLOAT,
    max_speed FLOAT,
    start_index INT,
    end_index INT,
    split BOOLEAN,
    created_at TEXT
);
