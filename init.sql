-- Conditionally create the smartcoach_db if it doesn't exist
DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database WHERE datname = 'smartcoach_db'
    ) THEN
        CREATE DATABASE smartcoach_db;
    END IF;
END
$$;

-- Set the password for the smartcoach user
ALTER USER smartcoach WITH PASSWORD 'devpass';

-- Switch to the smartcoach_db to run any schema/test statements
\connect smartcoach_db

-- Create a dummy table to verify this script ran
CREATE TABLE IF NOT EXISTS verify_init (
    id SERIAL PRIMARY KEY,
    note TEXT
);