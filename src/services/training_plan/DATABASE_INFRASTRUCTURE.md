# Database Infrastructure Usage

## Overview

This document outlines how the training plan services leverage existing database infrastructure and avoid duplication.

## Existing Database Tables

### `activities` Table

- **Purpose**: Stores Strava running activities with aggregated metrics
- **Key Columns**:
  - `user_id` (UUID) - Links to user identity
  - `activity_id` (bigint) - Strava's activity ID
  - `distance` (float) - Distance in meters
  - `conv_distance` (float) - Distance converted to miles
  - `moving_time` (int) - Moving time in seconds
  - `average_heartrate` (float) - Average HR in bpm
  - `start_date` (datetime) - Activity start date/time
  - `type` (string) - Activity type ("Run", "Ride", etc.)

### `splits` Table

- **Purpose**: Stores mile-by-mile split data for activities
- **Key Columns**:
  - `activity_id` (bigint) - Foreign key to activities
  - `lap_index` (int) - Split index
  - `distance`, `moving_time`, `average_speed`, `average_heartrate`, etc.
- **Note**: Not needed for pace seed/week logs (sufficient data in activities table)

### `plan_workouts` Table

- **Purpose**: Stores planned workouts for training plans
- **Key Columns**:
  - `plan_id` (int) - Foreign key to plans
  - `date` (date) - Workout date
  - `miles` (float) - Planned distance
  - `workout_type` (string) - Workout type (e.g., "Easy", "Long Run")

## Services Leveraging Existing Infrastructure

### 1. `DataCollectionService.fetch_strava_activities()`

- **Location**: `src/services/training_plan/data_collection_service.py`
- **Purpose**: Fetch activities from database via `user_id`
- **Implementation**:
  - Queries `activities` table directly using `user_id` (no `athlete_id` lookup needed)
  - Filters by date range, activity type ("Run")
  - Returns list of activity dictionaries with converted metrics
- **Usage**: Used by `week_log_service.py` and other services

### 2. Pace Calculation Module (`pace/`)

- **Purpose**: Generate initial pace zones (E, S, M, T) for workout details using performance-based calculation
- **Database Access**:
  - Uses direct SQL queries with `PERCENTILE_CONT` to calculate median easy pace from `activities` table
  - Queries by `user_id` directly (efficient, single-query approach)
  - Falls back to calibration if insufficient data (< 6 runs in last 6 weeks)
  - Extracts `conv_distance` (miles) and `moving_time` (seconds) for pace calculations
  - Uses efficient SQL aggregation instead of fetching all activities

### 3. `week_log_service.py`

- **Purpose**: Fetch week logs (completion data, RPE) for weekly rebuilds
- **Database Access**:
  - Uses `DataCollectionService.fetch_strava_activities()` to query `activities` table
  - Queries by `user_id` directly (leverages existing infrastructure)
  - Matches planned workouts (`plan_workouts` table) with completed activities (`activities` table)
  - Extracts `distance`, `average_heartrate` for completion tracking
- **Not Using**:
  - `ActivityStatsDAO` (uses `athlete_id`; we use `user_id` via DataCollectionService)
  - `splits` table (not needed for week-level completion tracking)

## What We're NOT Duplicating

### ✅ No Duplicate Queries

- **Before**: Incomplete logic in `week_log_service.py` that wasn't fully implemented
- **After**: Complete implementation leveraging `DataCollectionService.fetch_strava_activities()`

### ✅ No Unnecessary Lookups

- **Before**: Could have used `ActivityStatsDAO` which requires `athlete_id` lookup
- **After**: Uses `DataCollectionService` which queries by `user_id` directly (activities table has `user_id` column)

### ✅ No Unnecessary Table Access

- **Splits Table**: Not accessed for pace seed/week logs
  - Reason: Sufficient aggregated data in `activities` table (distance, moving_time, average_heartrate)
  - Future: Could be used for more granular pace analysis if needed (e.g., per-mile pace zones)

## Architecture Benefits

1. **Single Source of Truth**: All activity queries go through `DataCollectionService.fetch_strava_activities()`
2. **Consistent Query Pattern**: Uses `user_id` directly, no need to look up `athlete_id`
3. **No Duplication**: Services reuse existing infrastructure instead of creating new queries
4. **Maintainability**: Changes to activity query logic only need to be made in one place (`DataCollectionService`)

## Future Enhancements

If more granular pace analysis is needed:

- Could leverage `splits` table for per-mile pace zones
- Could use `ActivityStatsDAO.get_average_pace()` if switching to `athlete_id`-based queries
- Could add activity matching via workout notes/descriptions for better completion tracking
