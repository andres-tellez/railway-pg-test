# Training Plan Generation Services

## Overview

This directory contains shared services and the **V2 deterministic** training plan pipeline under `v2/`.

## Architecture Layers

### Layer 1: Data Collection (`data_collection_service.py`)

**Purpose:** Fetch raw data from the database

**Methods:**

- `fetch_user_profile()` - Uses existing `user_profile_dao.get_user_profile()`
- `fetch_strava_activities()` - Custom query for user_id + date range filtering
- `collect_all_data()` - Main entry point that aggregates all data

**Design Note:** This layer leverages existing DAOs where possible to avoid code duplication. Activity fetching uses custom logic because it requires specific filtering (by user_id + date range) that the existing `ActivityDAO` doesn't provide.

### Layer 2: Insights ~~(`insights_calculation_service.py`)~~ **LEGACY REMOVED**

The old **InsightsCalculationService** (L2 activity-list insights) has been removed. V2 plan generation uses the **materialized view** for Step 1 fitness (`get_weekly_fitness_from_materialized_view`), not L2.

### Layer 3 & 4: Removed (LLM-based)

This project now uses a fully deterministic pipeline (no LLM in generation).

### Layer 5: Plan Validation (V2)

**Purpose:** Validate generated plans for safety before persistence.

**Implementation:** `v2/plan_validation_service_v2.py` — class **`PlanValidationServiceV2`**, used by **`PlanGenerationOrchestratorV2`**.

~~**LEGACY:** `plan_validation_service.py` (v1 `PlanValidationService`) — **removed**.~~

### Layer 6: Plan Storage (`plan_storage_service.py`)

**Purpose:** Save validated plan to database

- TODO: To be implemented

## Testing

See `tests/services/training_plan/` for unit tests.

## Documentation

- Product spec (normative): `docs/SMARTCOACH_SYSTEM_SPEC_V1.md`
- HTTP / API surface: `docs/API_DOCUMENTATION.md`
