# Training Plan Generation Services

## Overview
This directory contains the 6-layer architecture for GPT-based marathon training plan generation.

## Architecture Layers

### Layer 1: Data Collection (`data_collection_service.py`)
**Purpose:** Fetch raw data from the database

**Methods:**
- `fetch_user_profile()` - Uses existing `user_profile_dao.get_user_profile()`
- `fetch_strava_activities()` - Custom query for user_id + date range filtering
- `collect_all_data()` - Main entry point that aggregates all data

**Design Note:** This layer leverages existing DAOs where possible to avoid code duplication. Activity fetching uses custom logic because it requires specific filtering (by user_id + date range) that the existing `ActivityDAO` doesn't provide.

### Layer 2: Insights Calculation (`insights_calculation_service.py`)
**Purpose:** Calculate training insights from raw data
- TODO: To be implemented

### Layer 3: Prompt Builder (`prompt_builder_service.py`)
**Purpose:** Structure insights into GPT prompts
- TODO: To be implemented

### Layer 4: GPT Coach (`gpt_coach_service.py`)
**Purpose:** Interact with GPT model
- TODO: To be implemented

### Layer 5: Plan Validation (`plan_validation_service.py`)
**Purpose:** Validate GPT output for safety
- TODO: To be implemented

### Layer 6: Plan Storage (`plan_storage_service.py`)
**Purpose:** Save validated plan to database
- TODO: To be implemented

## Testing
See `tests/services/training_plan/` for unit tests.

## Documentation
- Full architectural specification: `docs/training-plan-architecture-v3.md`
- Quick start guide: `docs/QUICK_START.md`
