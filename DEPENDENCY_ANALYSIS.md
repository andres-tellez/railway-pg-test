# Dependency Analysis: Can We Delete Legacy Paths?

## ✅ **SAFE TO DELETE**

### **Draft Path (`/api/plan/draft`) - KEEP THIS**

**Direct Dependencies:**

- `Pass1LongRunFirst` from `v2/marathon/v2/marathon/pass1_longrun_first_v2_v2.py`
- `calculate_weekly_totals_from_long_runs` from `v2/marathon/weekly_total_calculator_v2.py`
- `Pass3WorkoutDistribution` from `v2/v2/pass3_workout_distribution_v2_v2.py`
- `DataCollectionService` (shared); ~~`InsightsCalculationService`~~ **LEGACY REMOVED**

**Does NOT use:**

- ❌ `create_training_plan` (Path 1)
- ❌ `TrainingPlanOrchestratorService` (Path 2 — **module removed**)
- ❌ `ThreePassOrchestrator.generate()` (Path 3)
- ❌ `ThreePassOrchestrator` at all (it's created but never used in draft path)

**Impact of deleting Paths 1, 2, 3:** ✅ **NONE** - Draft path doesn't use them

---

### **Path 4 (`/api/plan/create` with LR-first) - KEEP THIS**

**Direct Dependencies:**

- `ThreePassOrchestrator.generate_longrun_first()`
- Inside `generate_longrun_first()`:
  - `Pass1LongRunFirst` (same as draft path)
  - `calculate_weekly_totals_from_long_runs` (same as draft path)
  - `Pass3WorkoutDistribution` (same as draft path)
  - `PlanValidationServiceV2`

**Does NOT use:**

- ❌ `create_training_plan` (Path 1)
- ❌ `TrainingPlanOrchestratorService` (Path 2 — **module removed**)
- ❌ `ThreePassOrchestrator.generate()` (Path 3) - Different method, no dependency

**Impact of deleting Paths 1, 2, 3:** ✅ **NONE** - Path 4 doesn't use them

**Note:** `ThreePassOrchestrator.__init__()` creates `self.pass1` and `self.pass2` which are only used by `generate()` (Path 3), NOT by `generate_longrun_first()`. So even if we delete `generate()`, `generate_longrun_first()` will still work (those attributes just won't be used).

---

## ❌ **SAFE TO DELETE (Legacy Paths)**

### **Path 1: Legacy LLM Single Pass**

**File:** `src/services/plan_generation_service.py`

- `create_training_plan()` function
- `generate_plan_with_gpt()` function
- `fetch_user_context()` function

**Used by:** `src/routes/plan_routes.py` line 505 (only when `use_orchestrator = False`)

**Impact of deletion:** ✅ **SAFE**

- Not used by draft path
- Not used by Path 4
- Only used when feature flag is disabled (legacy mode)

**Dependencies on good path:** ❌ **NONE**

---

### **Path 2: Old 6-Layer Orchestrator with LLM** _(LEGACY — implementation removed)_

**File:** ~~`src/services/training_plan/training_plan_orchestrator_service.py`~~ **(not in repo)**

- `TrainingPlanOrchestratorService` class (historical; **removed**)
- Used L1-L6 with LLM at Layer 4 when it existed

**Used by:** *(historical)* Earlier `plan_routes` wiring when flags selected the 6-layer path. **Current** `src/routes/plan_routes.py` uses **`run_v2_plan_generation`** only for create/draft flows covered here.

**Impact:** ✅ **N/A for current code** — module absent; draft and create paths use V2.

**Dependencies on good path:** ❌ **NONE**

- Historically used L1 + L2; **L2 (`InsightsCalculationService`) is LEGACY REMOVED**. `DataCollectionService` remains for other callers.

---

### **Path 3: Three-Pass Weekly-First**

**Method:** `ThreePassOrchestrator.generate()` (same class as Path 4's `generate_longrun_first()`)

**Used by:**

- Potentially called if someone uses `ThreePassOrchestrator` and calls `generate()` instead of `generate_longrun_first()`
- Looking at routes, Path 4 always calls `generate_longrun_first()`, never `generate()`

**Impact of deletion:** ⚠️ **NEEDS CAREFUL CHECK**

- Path 4 uses `generate_longrun_first()` - different method
- `generate_longrun_first()` does NOT call `generate()` - they're separate methods
- But they're in the same class, so we'd need to remove the `generate()` method but keep the class

**Dependencies on good path:** ❌ **NONE**

- `generate()` uses different services (`GptCoachPass1Weekly`, `GptCoachPass2LongRun`)
- `generate_longrun_first()` uses `Pass1LongRunFirst`, `calculate_weekly_totals_from_long_runs`

**Note:** The `__init__()` creates both sets of services, but `generate_longrun_first()` doesn't use `self.pass1` or `self.pass2`.

---

## Summary

| Path                | Safe to Delete? | Impact on Draft Path | Impact on Path 4 | Dependencies                                                            |
| ------------------- | --------------- | -------------------- | ---------------- | ----------------------------------------------------------------------- |
| **✅ KEEP: Draft**  | N/A             | ✅ Safe              | ✅ Safe          | Uses Pass1LongRunFirst, WeeklyTotalCalculator, Pass3WorkoutDistribution |
| **✅ KEEP: Path 4** | N/A             | ✅ Safe              | ✅ Safe          | Uses ThreePassOrchestrator.generate_longrun_first()                     |
| **Path 1**          | ✅ **YES**      | ❌ None              | ❌ None          | Separate service file                                                   |
| **Path 2**          | ✅ **YES**      | ❌ None              | ❌ None          | Separate orchestrator class                                             |
| **Path 3**          | ⚠️ **CAREFUL**  | ❌ None              | ❌ None          | Same class as Path 4, but different method                              |

---

## Recommendation

### ✅ **SAFE TO DELETE:**

1. **Path 1:** `src/services/plan_generation_service.py`

   - Remove entire file or just the functions
   - Remove import and usage from `plan_routes.py` line 20, 505

2. **Path 2:** `training_plan_orchestrator_service.py`

   - **Done:** orchestrator file and `tests/services/training_plan/test_training_plan_orchestrator_service.py` removed from this repo.
   - If any environment still references Path 2 flags, confirm `plan_routes` no longer imports the missing module (already absent under `src/`).

3. **Path 3:** `ThreePassOrchestrator.generate()` method
   - Keep the class, just remove the `generate()` method (lines 40-79)
   - Remove `self.pass1` and `self.pass2` from `__init__` (lines 27-28) since they're only used by `generate()`
   - This will make `ThreePassOrchestrator` only support LR-first mode

### ⚠️ **What to Keep:**

- `ThreePassOrchestrator` class itself (needed for Path 4)
- `generate_longrun_first()` method (used by Path 4)
- `Pass1LongRunFirst`, `WeeklyTotalCalculator`, `Pass3WorkoutDistribution` (used by both draft and Path 4)

---

## Final Answer

**YES, it is safe to delete Paths 1, 2, and 3.**

**The good path (draft + Path 4) does NOT depend on them:**

- Draft path directly uses the services, not the orchestrators
- Path 4 uses `generate_longrun_first()` which doesn't call `generate()`
- Paths 1 and 2 are completely separate files/services

**Will deleting them break the good path?** ❌ **NO**

**Do the legacy paths have dependencies on the good path?** ⚠️ **Only shared services (L1/L2), but those won't break**
