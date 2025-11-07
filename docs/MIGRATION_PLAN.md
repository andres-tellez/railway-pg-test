# Training Plan Service Migration Plan

## Overview

We are building a new 6-layer architecture for training plan generation to replace the existing monolithic `plan_generation_service.py`.

## Current State

### Old Service (Active in Production)

**File:** `src/services/plan_generation_service.py`

**Status:** ⚠️ **IN USE - DO NOT DELETE**

**Used By:**

- `src/routes/plan_routes.py` (line 19, 387)
- `/api/plan/create` endpoint

**Limitations:**

- Hardcoded TODOs for Strava data calculations
- Minimal user context gathering
- Simple, unstructured GPT prompt
- No validation or safety checks
- No insights calculation

### New Service (Under Development)

**Location:** `src/services/training_plan/`

**Status:** 🚧 **BUILDING**

**Architecture:**

```
Layer 1: Data Collection Service        ✅ COMPLETE (100% tested)
Layer 2: Insights Calculation Service   ⏳ TODO
Layer 3: Prompt Builder Service         ⏳ TODO
Layer 4: GPT Coach Service              ⏳ TODO
Layer 5: Plan Validation Service        ⏳ TODO
Layer 6: Plan Storage Service           ⏳ TODO
```

## Migration Phases

### Phase 1: Build New Architecture ← **WE ARE HERE**

**Goal:** Implement all 6 layers with comprehensive testing

**Tasks:**

- [x] Layer 1: Data Collection (Complete)
- [ ] Layer 2: Insights Calculation
- [ ] Layer 3: Prompt Builder
- [ ] Layer 4: GPT Coach
- [ ] Layer 5: Plan Validation
- [ ] Layer 6: Plan Storage
- [ ] Create orchestrator service to coordinate all layers

**Deliverable:** Fully tested, production-ready new service

### Phase 2: Integration Testing

**Goal:** Validate new service works end-to-end

**Tasks:**

- [ ] Create integration tests for full plan generation flow
- [ ] Test with real user data (anonymized)
- [ ] Compare output quality: old vs new service
- [ ] Performance benchmarking
- [ ] Edge case testing

**Deliverable:** Confidence that new service is ready for production

### Phase 3: Route Migration

**Goal:** Swap production routes to use new service

**Tasks:**

- [ ] Create new route handler using new layered service
- [ ] Update `src/routes/plan_routes.py`:

  ```python
  # OLD (line 19):
  from src.services.plan_generation_service import create_training_plan

  # NEW:
  from src.services.training_plan.orchestrator import create_training_plan
  ```

- [ ] Deploy with feature flag (optional: A/B testing)
- [ ] Monitor error rates and performance

**Deliverable:** New service active in production

### Phase 4: Cleanup

**Goal:** Remove old service after successful migration

**Tasks:**

- [ ] Archive old service to `/docs/archived_code/`
- [ ] Delete `src/services/plan_generation_service.py`
- [ ] Update all documentation
- [ ] Remove old service from imports

**Deliverable:** Clean codebase with only new architecture

## Decision Points

### When to Delete Old Service?

**Delete when ALL of these are true:**

- ✅ All 6 layers implemented and tested
- ✅ Integration tests passing
- ✅ Routes migrated to new service
- ✅ New service deployed and stable in production
- ✅ No rollback needed for at least 2 weeks

**DO NOT delete if:**

- ❌ Any layer is incomplete
- ❌ New service not yet deployed
- ❌ Migration issues or bugs found
- ❌ Need to rollback to old service

## Comparison: Old vs New

| Feature             | Old Service            | New Service                  |
| ------------------- | ---------------------- | ---------------------------- |
| **Data Collection** | Minimal, hardcoded     | Comprehensive Layer 1        |
| **Strava Analysis** | TODO comments          | Full historical analysis     |
| **Insights**        | None                   | Smart calculations (Layer 2) |
| **GPT Prompt**      | Simple string template | Modular, optimized structure |
| **Validation**      | None                   | Safety checks (Layer 5)      |
| **Testing**         | No tests               | 100% coverage per layer      |
| **Maintainability** | Monolithic             | Modular, well-documented     |

## Current Answer to "What to Delete?"

**For Layer 1:** ✅ **Nothing to delete**

We cleaned up:

- ✓ Unused imports in Layer 1 service
- ✓ Outdated documentation

We're keeping:

- ✓ Old `plan_generation_service.py` (still in production use)
- ✓ All routes (will migrate later)

---

**Last Updated:** October 29, 2025
**Phase:** Phase 1 - Building New Architecture (Layer 1 Complete)
