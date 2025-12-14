# Heart Rate Zone Service Guardrails

**Purpose:** Prevent code drift, ensure centralization, and maintain architectural consistency.

**Status:** ✅ Active
**Last Updated:** December 2025

---

## Core Principles

1. **Single Source of Truth** - All constants in `hr_zone_constants.py`
2. **Service Purity** - Pure services have no DB access, no cross-imports
3. **Separation of Concerns** - Orchestration vs pure calculation
4. **Consistent Patterns** - Standardized return types and error handling

---

## Rules and Enforcement

### Rule 1: Constants MUST Live in hr_zone_constants.py ONLY

**Rule:** All constants, thresholds, and magic numbers MUST be in `src/utils/hr_zone_constants.py`

**Enforcement:**
- ✅ Code Review: Reject PRs with constants in service files
- ✅ Import check: Services import from constants file only
- ❌ NO constants allowed in validation.py
- ❌ NO constants allowed in service files

**Example Violations:**
```python
# ❌ FORBIDDEN
# In validation.py or any service
MIN_ACTIVITIES = 5  # Should be in hr_zone_constants.py

# ❌ FORBIDDEN
if count < 5:  # Magic number
```

**Correct Pattern:**
```python
# ✅ CORRECT
from src.utils.hr_zone_constants import HRMAX_ESTIMATION

if count < HRMAX_ESTIMATION["MIN_ACTIVITIES_REQUIRED"]:
```

**Action Required:**
If you need a new constant:
1. Add it to `src/utils/hr_zone_constants.py`
2. Update this guardrail document
3. Import it in the service that needs it

---

### Rule 2: Pure Services MUST NOT Import Each Other

**Rule:** Pure calculation services MUST remain independent.

**Forbidden Imports (in pure services):**
- ❌ Other heart_rate services (estimation, karvonen, resolution, orchestration)
- ❌ DAO files
- ❌ Route files
- ❌ Models
- ❌ Database sessions
- ❌ Any orchestration logic

**Allowed Imports (in pure services):**
- ✅ `src.utils.hr_zone_constants` - Constants only
- ✅ `dataclasses` - Standard library
- ✅ `numpy` - Math operations
- ✅ `typing` - Type hints
- ✅ `logging` - Logging (NO user_id in logs)
- ✅ `src.services.heart_rate.validation` - Shape/type validation only

**Pure Service Files:**
- `hrmax_estimation_service.py` - MUST follow above rules
- `karvonen_zone_service.py` - MUST follow above rules

**Example Violations:**
```python
# ❌ FORBIDDEN in hrmax_estimation_service.py
from .hrmax_resolution_service import HRMaxResolutionService
from .heart_rate_orchestration_service import HeartRateZoneOrchestrationService
from src.db.dao.user_profile_dao import get_user_profile
```

**Correct Pattern:**
```python
# ✅ CORRECT in hrmax_estimation_service.py
from src.utils.hr_zone_constants import HRMAX_ESTIMATION
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import logging
```

---

### Rule 3: Data Fetching Lives in Orchestration ONLY

**Rule:** Pure services NEVER fetch data from database.

**Enforcement:**
- ✅ Orchestration service handles all data fetching
- ✅ DAOs are called only by orchestration service
- ❌ Pure services never receive `session` parameter
- ❌ Pure services never import DAOs

**Correct Pattern:**
```python
# ✅ CORRECT
# Orchestration service
class HeartRateZoneOrchestrationService:
    @staticmethod
    def fetch_activities_for_hrmax(session, user_id):
        # Fetch from DB here
        activities = ...
        # Then call pure service
        result = HRMaxEstimationService.estimate_hrmax(activities)

# ✅ CORRECT
# Pure service
class HRMaxEstimationService:
    @staticmethod
    def estimate_hrmax(activities: List[Dict]) -> HRMaxEstimationResult:
        # No session, no DB access
        pass
```

---

### Rule 4: NEVER Call calculate_zones() Directly from Route

**Rule:** Zones must be calculated through orchestration service only.

**Required Flow:**
1. Route → Orchestration Service
2. Orchestration → HRMax Resolution (get effective HRmax)
3. Orchestration → HRMax Estimation (if needed)
4. Orchestration → Karvonen Zone Calculation
5. Route → Response

**Forbidden:**
```python
# ❌ FORBIDDEN in route
from .karvonen_zone_service import KarvonenZoneService

zones = KarvonenZoneService.calculate_zones(hrmax, resting_hr)
```

**Correct:**
```python
# ✅ CORRECT in route
from .heart_rate_orchestration_service import HeartRateZoneOrchestrationService

result = HeartRateZoneOrchestrationService.calculate_zones_for_user(session, user_id)
```

---

### Rule 5: Circular Dependency Prevention

**This directory MUST NOT import from:**
- ❌ `src/routes/`
- ❌ `src/db/` (models, dao)
- ❌ `src/services/heart_rate/heart_rate_orchestration_service.py` (from pure services)

**Dependency Graph:**
```
Orchestration Service
  ↓ imports
Resolution Service (✅ OK - orchestration can import resolution)
  ↓ imports
Pure Services (estimation, karvonen) (✅ OK - resolution can import pure)
  ↓ imports
Constants, Validation (✅ OK)

Pure Services
  ❌ DO NOT import orchestration
  ❌ DO NOT import resolution
```

---

### Rule 6: Service Layer Logging Rules

**Allowed in Service Layer:**
- ✅ Activity counts, metrics, calculation parameters
- ✅ Filtering results (removed_outliers, filtered_count)
- ✅ Warnings about data quality

**Forbidden in Service Layer:**
- ❌ user_id (route layer responsibility)
- ❌ Personal identifiers
- ❌ Sensitive user data

**Example:**
```python
# ✅ CORRECT in service
logger.info("Estimating HRmax", extra={"activity_count": 25})

# ❌ FORBIDDEN in service
logger.info("Estimating HRmax", extra={"user_id": user_id})
```

**Route Layer:**
- ✅ Can log user_id
- ✅ Can log user context

---

### Rule 7: Error Handling Semantics

**ValueError:**
- Raised for developer/user input errors
- Invalid parameter types (e.g., activities not a list)
- Invalid parameter ranges (e.g., hrmax < 120)
- Should be caught at route layer and return 400

**Structured Error (success=False dataclass):**
- Returned for valid input but calculation failures
- Insufficient data (e.g., < 5 activities)
- Poor-quality data (e.g., all values filtered out)
- Should be handled as 400 with error_code for user messaging

**Service methods NEVER throw structured errors as exceptions.**
**They ALWAYS return dataclasses with success=False.**

---

### Rule 8: Validation Scope

**validation.py Responsibilities:**
- ✅ Validate input SHAPES and TYPES only
- ✅ Pre-service validation (before calling pure services)
- ❌ NEVER validate physiological ranges (services do this)
- ❌ NEVER duplicate service-level validation

**Physiological range validation MUST stay in pure services**
**so it cannot be bypassed.**

---

### Rule 9: Resting HR Estimation Persistence

**Rule:** Estimated RHR is automatically persisted to the database unless user provides manual value.

**Behavior:**
- When `use_estimate=True` and `resting_hr` is missing → estimate and store
- When user later enters manual `resting_hr` → clear `resting_hr_source` to "USER" and update timestamp
- Estimated values are overwritten by manual input without warning
- Estimated RHR is persisted with `resting_hr_source="ESTIMATED"` and `resting_hr_updated_at` timestamp

**Rationale:**
Enables immediate zone calculation without blocking UX. Manual input always takes precedence.

**Enforcement:**
- ✅ Profile save route must check if user is setting manual RHR
- ✅ When manual RHR is set, clear estimated values and set `resting_hr_source="USER"`
- ✅ Update `resting_hr_updated_at` timestamp when RHR changes
- ❌ Never persist estimated RHR without user consent when `use_estimate=False`

**Example:**
```python
# ✅ CORRECT - Clear estimated values when user enters manual RHR
if new_resting_hr is not None and new_resting_hr != old_resting_hr:
    user_dict["resting_hr_source"] = "USER"
    user_dict["resting_hr_updated_at"] = datetime.now()
```

---

### Rule 10: Status Endpoint Purity

**Rule:** `/api/heart-rate/zones/status` MUST NEVER trigger HRmax or zone calculation.

**Enforcement:**
- ✅ Status endpoint is READ-ONLY diagnostics
- ✅ NEVER call `HRMaxEstimationService.estimate_hrmax()` from status
- ✅ NEVER call `KarvonenZoneService.calculate_zones()` from status
- ✅ Status reports readiness only, never computes zones
- ❌ Status endpoint must not have side effects (no DB writes)

**Correct Pattern:**
```python
# ✅ CORRECT - status only reports stored values
def get_hr_zone_status(session, user_id):
    profile = get_user_profile(session, user_id)
    # Check stored values only
    # Return readiness info
    # NEVER calculate zones here
```

**Forbidden:**
```python
# ❌ FORBIDDEN - status calculating zones
def get_hr_zone_status(session, user_id):
    zones = calculate_zones_for_user(session, user_id)  # NO!
    # Status must not trigger calculation
```

**Rationale:**
Status endpoint is lightweight diagnostics for UI state. Actual zone calculation happens in `/zones/calculate` endpoint. Keeping them separate ensures:
- Status checks are fast and cacheable
- UI can check readiness without triggering expensive calculations
- Clear separation of concerns

---

## Code Review Checklist

When reviewing PRs that touch HR zone services:

### Pre-Merge Checklist

- [ ] **Constants location**
  - [ ] No magic numbers in service files
  - [ ] All constants in `hr_zone_constants.py`
  - [ ] No duplicate constant definitions

- [ ] **Service purity**
  - [ ] Pure services have no DB access
  - [ ] Pure services don't import orchestration
  - [ ] No user_id in service layer logs

- [ ] **Import rules**
  - [ ] Pure services only import allowed modules
  - [ ] No circular dependencies
  - [ ] Orchestration imports pure services (not reverse)

- [ ] **Data fetching**
  - [ ] Only orchestration service accesses DB/DAOs
  - [ ] Pure services receive data, don't fetch it

- [ ] **Zone calculation flow**
  - [ ] Routes call orchestration service only
  - [ ] No direct calls to KarvonenZoneService from routes

- [ ] **Error handling**
  - [ ] ValueError for invalid inputs
  - [ ] Structured errors (dataclass) for calculation failures
  - [ ] Route layer converts to HTTP responses

- [ ] **Resting HR estimation**
  - [ ] Estimated RHR is persisted only when `use_estimate=True`
  - [ ] Manual RHR input clears estimated values
  - [ ] `resting_hr_source` is set correctly (USER vs ESTIMATED)
  - [ ] `resting_hr_updated_at` timestamp is updated on changes

- [ ] **Status endpoint**
  - [ ] Status endpoint never calculates zones
  - [ ] Status endpoint is read-only (no DB writes)
  - [ ] Status reports readiness only, not actual zones

---

## Violations Log

Track known violations that need to be fixed:

- None currently (all code follows guardrails ✅)

---

## Questions?

If you're unsure whether your code follows the guardrails:

1. Check this document for the rule
2. Review existing service code for patterns
3. Ask for architecture review before implementing
