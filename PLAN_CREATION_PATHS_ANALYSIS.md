# Plan Creation Paths Analysis

## ✅ **Path We Want to Keep: All-Code Deterministic Draft**

**Route:** `POST /api/plan/draft`
**File:** `src/routes/plan_routes.py` → `create_plan_draft_route()` (lines 529-1089)

**Flow:**

1. L1 (DataCollection) + L2 (Insights) → raw data + insights
2. **Pass1LongRunFirst** (deterministic long-run progression)
3. **WeeklyTotalCalculator** (deterministic weekly totals)
4. **Pass3WorkoutDistribution** (deterministic workout distribution)
5. Validation + time assessment + recovery week insertion
6. Returns draft (no save)

**Status:** ✅ **WORKING - KEEP THIS**

---

## ❌ **Alternative Paths (NOT the One We Want to Keep)**

### **Path 1: Legacy LLM-Based Single Pass**

**Route:** `POST /api/plan/create`
**Condition:** `TRAINING_PLAN_ORCHESTRATOR_ENABLED=false` (or unset)

**Flow:**

1. `create_training_plan()` from `src/services/plan_generation_service.py`
2. `fetch_user_context()` - basic user profile + Strava data
3. `generate_plan_with_gpt()` - **CALLS LLM** with Jack Daniels prompt
4. `save_workouts()` - saves plan + workouts to DB

**Files:**

- `src/services/plan_generation_service.py`
- `src/utils/gpt_ops.py` (likely used for GPT calls)

**Status:** ❌ **LEGACY - Uses LLM for entire plan generation**

---

### **Path 2: Old 6-Layer Orchestrator with LLM** _(LEGACY / historical)_

**Route:** `POST /api/plan/create` (when flags routed here historically)
**Condition:** `TRAINING_PLAN_ORCHESTRATOR_ENABLED=true` AND `TRAINING_PLAN_GENERATION_MODE=one_pass` (or unset)

**Implementation:** `training_plan_orchestrator_service.py` and **`TrainingPlanOrchestratorService`** are **not present** in this repository anymore. The flow below documents the old design only.

**Flow (historical):**

1. `TrainingPlanOrchestratorService.create_default()`
2. **Layer 1:** DataCollectionService
3. **Layer 2:** InsightsCalculationService
4. **Layer 3:** PromptBuilderService → builds GPT prompt
5. **Layer 4:** GptCoachService → **CALLS LLM** (gpt-4o)
6. **Layer 5:** ~~`PlanValidationService` (v1)~~ **(removed)** — current product uses `PlanValidationServiceV2` in the v2 pipeline
7. **Layer 6:** PlanStorageService → saves to DB

**Files (historical):**

- ~~`src/services/training_plan/training_plan_orchestrator_service.py`~~ **(removed)**
- `src/services/training_plan/prompt_builder_service.py` (may still exist; not used by V2 draft/LR-first path)
- `src/services/training_plan/gpt_coach_service.py`

**Status:** ❌ **LEGACY — not runnable as documented; use V2 LR-first paths**

---

### **Path 3: Three-Pass Orchestrator (Weekly-First)**

**Route:** `POST /api/plan/create`
**Condition:** `TRAINING_PLAN_ORCHESTRATOR_ENABLED=true` AND `TRAINING_PLAN_GENERATION_MODE=three_pass`

**Flow:**

1. `ThreePassOrchestrator.generate()` (NOT `generate_longrun_first()`)
2. Pass1WeeksSelectorV2 (when used) → recommends weeks
3. **Pass 1:** `GptCoachPass1Weekly` → **DETERMINISTIC NOW** (generates weekly mileage skeleton)
4. **Pass 2:** `GptCoachPass2LongRun` → **DETERMINISTIC NOW** (adds long run miles)
5. **Pass 3:** `Pass3WorkoutDistribution` → deterministic workout distribution
6. Validation + saves to DB

**Files:**

- `src/services/training_plan/v2/plan_generation_orchestrator_v2.py` → `generate()` method
- `src/services/training_plan/gpt_coach_pass1_weekly.py` (deterministic, not LLM)
- `src/services/training_plan/gpt_coach_pass2_longrun.py` (deterministic, not LLM)

**Status:** ⚠️ **PARTIALLY DETERMINISTIC - But uses weekly-totals-first approach, not LR-first**

**Note:** This path is similar to the draft path BUT uses a different ordering:

- **This path:** Weekly totals → Long runs → Workouts
- **Draft path:** Long runs → Weekly totals → Workouts (LR-first)

---

### **Path 4: Three-Pass Orchestrator (Long-Run-First) with Save**

**Route:** `POST /api/plan/create`
**Condition:** `TRAINING_PLAN_ORCHESTRATOR_ENABLED=true` AND `TRAINING_PLAN_GENERATION_MODE=three_pass` AND `use_longrun_first=true` (hardcoded)

**Flow:**

1. `ThreePassOrchestrator.generate_longrun_first()`
2. **Pass1LongRunFirst** → deterministic long-run progression
3. **WeeklyTotalCalculator** → deterministic weekly totals
4. **Pass3WorkoutDistribution** → deterministic workout distribution
5. Validation → saves to DB

**Files:**

- `src/services/training_plan/v2/plan_generation_orchestrator_v2.py` → `generate_longrun_first()` method
- Same deterministic services as draft path

**Status:** ✅ **SAME LOGIC AS DRAFT - But saves immediately (no preview)**

**Note:** This path uses the **same deterministic logic** as the draft path, but:

- Draft path: Returns preview without saving
- This path: Saves directly to database

---

## Summary of Paths

| Path        | Route                                         | LLM Used? | Order        | Saves?        | Status              |
| ----------- | --------------------------------------------- | --------- | ------------ | ------------- | ------------------- |
| **✅ KEEP** | `/api/plan/draft`                             | ❌ No     | LR-first     | ❌ No (draft) | **Working**         |
| Path 4      | `/api/plan/create` (three_pass + LR-first)    | ❌ No     | LR-first     | ✅ Yes        | Same logic as draft |
| Path 3      | `/api/plan/create` (three_pass, weekly-first) | ❌ No     | Weekly-first | ✅ Yes        | Different ordering  |
| Path 2      | `/api/plan/create` (orchestrator, one_pass)   | ✅ Yes    | Single pass  | ✅ Yes        | Uses LLM Layer 4    |
| Path 1      | `/api/plan/create` (legacy)                   | ✅ Yes    | Single pass  | ✅ Yes        | Old LLM-based       |

---

## Recommendation

### **Paths to Keep:**

1. ✅ **`/api/plan/draft`** - Current working all-code deterministic draft
2. ✅ **`/api/plan/create` with `three_pass` + LR-first** - Same logic, but saves immediately

### **Paths to Consider Removing/Deprecating:**

1. ❌ **Path 1:** Legacy `create_training_plan()` - Old LLM-based single pass
2. ❌ **Path 2:** Old 6-layer orchestrator (module removed; historical only)
3. ⚠️ **Path 3:** `ThreePassOrchestrator.generate()` (weekly-first) - Different ordering, might cause confusion

### **Questions to Consider:**

1. Should `/api/plan/create` always use the LR-first deterministic path?
2. Should we remove the old LLM-based paths (Path 1 & 2)?
3. Should we consolidate `ThreePassOrchestrator.generate()` to only use LR-first?

---

## Feature Flags Currently Used

- `TRAINING_PLAN_ORCHESTRATOR_ENABLED` - Controls whether to use orchestrator or legacy service
- `TRAINING_PLAN_GENERATION_MODE` - Controls one_pass vs three_pass
- `TRAINING_PLAN_LONGRUN_FIRST` - Not used in routes (hardcoded in code)
- `TRAINING_PLAN_LR_ONLY_DRAFT` - Not used in routes (hardcoded in code)

**Note:** In the draft route, these flags are essentially hardcoded to use the deterministic LR-first path.
