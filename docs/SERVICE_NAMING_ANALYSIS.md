# Service File Naming Analysis

**Date:** November 2025
**Status:** Analysis Complete

---

## Overview

Analysis of service file naming consistency in `src/services/` directory.

---

## Current Naming Patterns

### ✅ Following Standard Pattern (`{domain}_service.py`)

**13 files following the standard:**
1. `activity_service.py` ✅
2. `email_service.py` ✅
3. `gyr_metrics_service.py` ✅
4. `ingestion_orchestrator_service.py` ✅
5. `metrics_cache_service.py` ✅
6. `optimized_metrics_service.py` ✅
7. `smart_data_service.py` ✅
8. `strava_access_service.py` ✅
9. `sync_queue_service.py` ✅
10. `sync_tracking_service.py` ✅
11. `token_service.py` ✅
12. `user_identity_service.py` ✅

### ⚠️ Inconsistent Naming (5 files)

**Files NOT following `_service.py` pattern:**

1. **`athlete_readiness_assessment.py`**
   - **Current:** `athlete_readiness_assessment.py`
   - **Suggested:** `athlete_readiness_service.py`
   - **Type:** Service (contains business logic)
   - **Usage:** Used in training plan generation
   - **Reason:** This is a service that assesses athlete readiness

2. **`webhook_processor.py`**
   - **Current:** `webhook_processor.py`
   - **Suggested:** `webhook_service.py` or `webhook_processor_service.py`
   - **Type:** Service (processes webhook events)
   - **Usage:** Used by `webhook_routes.py`
   - **Reason:** This is a service that processes webhooks

3. **`training_profile_normalizer.py`**
   - **Current:** `training_profile_normalizer.py`
   - **Suggested:** `training_profile_normalizer_service.py`
   - **Type:** Service (normalizes training profiles)
   - **Usage:** Used in training plan generation
   - **Reason:** This is a service that normalizes profiles

4. **`pace_zone_mapper.py`**
   - **Current:** `pace_zone_mapper.py`
   - **Suggested:** `pace_zone_mapper_service.py` OR move to `src/utils/pace_zone_mapper.py`
   - **Type:** Could be utility or service
   - **Usage:** Used in training plan generation
   - **Reason:** This maps paces/zones - could be a utility or service

5. **`rate_limiter.py`**
   - **Current:** `rate_limiter.py`
   - **Suggested:** `rate_limiter_service.py` OR move to `src/utils/rate_limiter.py`
   - **Type:** Could be utility or service
   - **Usage:** Used by `strava_access_service.py` and `sync_queue_service.py`
   - **Reason:** This is a utility that limits API rates - could be in utils/

---

## Recommendations

### High Priority: Services That Should Be Renamed

These are clearly services and should follow the `_service.py` pattern:

1. **`athlete_readiness_assessment.py` → `athlete_readiness_service.py`**
   - Impact: Medium (used in training plan generation)
   - Breaking change: Yes (imports need updating)

2. **`webhook_processor.py` → `webhook_processor_service.py`**
   - Impact: Low (only used by webhook_routes.py)
   - Breaking change: Yes (imports need updating)

3. **`training_profile_normalizer.py` → `training_profile_normalizer_service.py`**
   - Impact: Medium (used in training plan generation)
   - Breaking change: Yes (imports need updating)

### Medium Priority: Utilities That Could Move

These are more utility-like and could be moved to `src/utils/`:

4. **`pace_zone_mapper.py` → `src/utils/pace_zone_mapper.py`**
   - Impact: Medium (used in training plan generation)
   - Breaking change: Yes (imports need updating)
   - **Alternative:** Keep in services but rename to `pace_zone_mapper_service.py`

5. **`rate_limiter.py` → `src/utils/rate_limiter.py`**
   - Impact: Low (used by 2 services)
   - Breaking change: Yes (imports need updating)
   - **Alternative:** Keep in services but rename to `rate_limiter_service.py`

---

## Standard Naming Convention

### Services (`src/services/`)
**Pattern:** `{domain}_service.py` or `{function}_service.py`

**Examples:**
- ✅ `activity_service.py` - Activity management
- ✅ `token_service.py` - Token management
- ✅ `strava_access_service.py` - Strava API access
- ✅ `metrics_cache_service.py` - Metrics caching

### Utilities (`src/utils/`)
**Pattern:** `{function}_utils.py` or `{function}.py`

**Examples:**
- ✅ `response_utils.py` - Response formatting
- ✅ `auth0_jwt.py` - JWT validation
- ✅ `date_helpers.py` - Date manipulation

---

## Implementation Plan

### Phase 1: Rename Clear Services (High Priority)

1. **Rename `athlete_readiness_assessment.py` → `athlete_readiness_service.py`**
   - Update imports in training plan services
   - Test: Verify training plan generation still works

2. **Rename `webhook_processor.py` → `webhook_processor_service.py`**
   - Update import in `webhook_routes.py`
   - Test: Verify webhook processing still works

3. **Rename `training_profile_normalizer.py` → `training_profile_normalizer_service.py`**
   - Update imports in training plan services
   - Test: Verify training plan generation still works

### Phase 2: Decide on Utilities (Medium Priority)

4. **Decide on `pace_zone_mapper.py`:**
   - Option A: Move to `src/utils/pace_zone_mapper.py`
   - Option B: Rename to `src/services/pace_zone_mapper_service.py`
   - **Recommendation:** Keep in services (it's used in business logic)

5. **Decide on `rate_limiter.py`:**
   - Option A: Move to `src/utils/rate_limiter.py`
   - Option B: Rename to `src/services/rate_limiter_service.py`
   - **Recommendation:** Move to utils (it's a pure utility, no business logic)

---

## Files to Update After Renaming

### After renaming `athlete_readiness_assessment.py`:
- All training plan services that import it

### After renaming `webhook_processor.py`:
- `src/routes/webhook_routes.py`

### After renaming `training_profile_normalizer.py`:
- All training plan services that import it

### After moving/renaming `pace_zone_mapper.py`:
- All training plan services that import it

### After moving/renaming `rate_limiter.py`:
- `src/services/strava_access_service.py`
- `src/services/sync_queue_service.py`

---

## Usage Analysis

### Currently Used Files

1. **`webhook_processor.py`** ✅ **ACTIVELY USED**
   - Used by: `src/routes/webhook_routes.py`
   - Import: `from src.services.webhook_processor import process_webhook_event`
   - **Action Required:** Rename to `webhook_processor_service.py`

2. **`rate_limiter.py`** ✅ **ACTIVELY USED**
   - Used by:
     - `src/services/strava_access_service.py`
     - `src/services/sync_queue_service.py`
   - **Action Required:** Move to `src/utils/rate_limiter.py` (it's a utility)

### Potentially Legacy/Unused Files

3. **`athlete_readiness_assessment.py`** ⚠️ **NOT CURRENTLY IMPORTED**
   - **Status:** Not found in any imports
   - **Likely:** Legacy code from old plan generation system
   - **Action:** Verify if needed, then rename or remove

4. **`training_profile_normalizer.py`** ⚠️ **NOT CURRENTLY IMPORTED**
   - **Status:** Not found in any imports
   - **Likely:** Legacy code from old plan generation system
   - **Action:** Verify if needed, then rename or remove

5. **`pace_zone_mapper.py`** ⚠️ **NOT CURRENTLY IMPORTED**
   - **Status:** Not found in any imports
   - **Likely:** Legacy code from old plan generation system
   - **Action:** Verify if needed, then rename or remove

---

## Summary

**Current State:**
- ✅ 13 files following standard naming
- ⚠️ 5 files with inconsistent naming
- ⚠️ 3 files appear to be unused/legacy

**After Standardization:**
- ✅ All active services will follow `_service.py` pattern
- ✅ Utilities will be in `src/utils/` with appropriate naming
- ✅ Legacy files will be either renamed or removed

**Impact:** Low-Medium - Only 2 files are actively used, others may be legacy

---

**Status:** Analysis Complete
**Recommendation:**
1. Rename active files (webhook_processor, rate_limiter)
2. Verify if legacy files are needed
3. Either rename or remove legacy files

**Next Step:** Start with renaming actively used files
