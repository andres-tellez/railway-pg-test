# Training Plan Creation Process - High-Level Overview

## ✅ **What Works: All-Code Deterministic Process**

This document describes the **current working plan generation process** that runs entirely in code (no LLM for plan generation).

---

## Entry Point

**Route:** `POST /api/plan/draft`
**File:** `src/routes/plan_routes.py` → `create_plan_draft_route()`

---

## Process Flow (Step-by-Step)

### **Phase 1: Data Collection & Insights**

1. **Layer 1: DataCollectionService**

   - Collects user profile data
   - Fetches Strava activities (last 12 weeks)
   - **Output:** Raw data dictionary

2. **Layer 2: InsightsCalculationService**

   - Calculates current fitness metrics:
     - `weekly_mileage`
     - `longest_run`
     - Recent activity patterns
   - **Output:** Insights dictionary

3. **Pass1WeeksSelectorV2** (optional weeks recommendation)
   - Fitness-based mapping for plan duration (12/16/20/24 weeks); orchestrator applies calendar constraints
   - Based on `weekly_mileage` (materialized view in V2)
   - **Output:** Recommended weeks count

---

### **Phase 2: Long Run Progression (Pass 1 Long Run First)**

4. **Pass1LongRunFirst**
   - **Input:** User's recent 3-week longest run
   - **Logic:**
     - Week 1 = `max(recent_3w_longest + 1.0 mile)` (rounded to 0.5)
     - Dynamic plan length: Calculates weeks-to-peak based on starting LR
     - Builds progression: +1 mile/week, cutback every 4 weeks (~30% reduction)
     - Single peak at 20 miles
     - 3-week taper: 70%, 50%, 25% of peak
   - **Output:** List of weeks with `long_run_miles` + `phase` (Base/Build/Peak/Taper)
   - **File:** `src/services/training_plan/v2/marathon/v2/marathon/pass1_longrun_first_v2.py`
   - **Core Logic:** `src/services/training_plan/v2/shared_v2/shared_v2/long_run_spine_v2.py` → `generate_v2/shared_v2/long_run_spine_v2()`

---

### **Phase 3: Weekly Total Miles (Pass 2)**

5. **WeeklyTotalCalculator**
   - **Input:** Long run miles for each week + `runs_per_week` (3/4/5)
   - **Logic:**
     - Target long run % of total:
       - 3 days/week: 40-50% (target 45%)
       - 4 days/week: 35-45% (target 40%)
       - 5 days/week: 30-40% (target 33%)
     - Safety caps:
       - Weekly increase: +8% max vs. previous week
       - Peak caps: 42/46/50 miles (for 3/4/5 days)
       - Minimum: ≥3 miles per non-long run
   - **Output:** `weekly_mileage` for each week
   - **File:** `src/services/training_plan/v2/marathon/weekly_total_calculator_v2.py` → `calculate_weekly_totals_from_long_runs()`

---

### **Phase 4: Workout Distribution (Pass 3)**

6. **Pass3WorkoutDistribution**
   - **Input:** `long_run_miles` + `weekly_mileage` + `training_days` (e.g., ["Mon", "Wed", "Thu", "Sat"])
   - **Logic:**
     - Calculate non-long-run total: `weekly_mileage - long_run_miles`
     - Distribute across remaining days using percentages:
       - 3 days: Medium (55%), Easy (45%)
       - 4 days: Medium (40%), Easy (30%), Easy/Tempo (30%)
       - 5 days: Medium (32%), Easy (25%), Tempo (23%), Easy (20%)
     - Assign days with recovery-aware ordering:
       - **Monday** (day after LR): Shortest → "Easy/Recovery"
       - **Thursday**: Medium → "Aerobic"
       - **Wednesday**: Longest weekday → "Endurance"
       - Ensures: Mon < Thu < Wed by distance
     - Place long run on weekend (Sat preferred, then Sun)
     - Minimum 3 miles per non-long run
     - Adjust rounding to match `total_weekly_miles` exactly
   - **Output:** `workouts` array with `{day, workout_type, distance_miles}` for each week
   - **File:** `src/services/training_plan/v2/pass3_workout_distribution_v2.py` → `calculate_workout_distribution()`

---

### **Phase 5: Validation & Time Assessment**

7. **In-Route Validation Checks**

   - Week 1 baseline check: `Week 1 LR == recent_3w_longest + 1.0`
   - Sustained high-mileage check: ≥5 of 6 consecutive weeks at ≥19 miles
   - Taper quality: Post-peak must be non-increasing; last 3 weeks ≈ 70%/50%/25% of peak
   - High LR too close to race: ≥18 miles within last 5 weeks (outside taper)
   - **Output:** `violations` array with `{code, rule, details, suggestion, severity, week}`

8. **Time Assessment**
   - Calculates weeks available until race date
   - If extra weeks available → **Recovery Week Insertion**
     - Inserts recovery weeks into Build/Peak phases
     - Recalculates workouts for inserted weeks using Pass3
   - **Output:** `time_assessment` message + `start_date` (next Monday)

---

### **Phase 6: Response Formatting**

9. **Final Response Structure**
   ```json
   {
     "status": "success",
     "generated_plan": {
       "weeks": [
         {
           "week_number": 1,
           "phase": "Base",
           "long_run_miles": 15.0,
           "weekly_mileage": 30,
           "workouts": [
             {"day": "Mon", "workout_type": "Easy/Recovery", "distance_miles": 5},
             {"day": "Wed", "workout_type": "Endurance", "distance_miles": 10},
             {"day": "Thu", "workout_type": "Aerobic", "distance_miles": 7},
             {"day": "Sat", "workout_type": "Long Run", "distance_miles": 15}
           ],
           "week_start_date": "2025-11-03",
           "week_label": "11/03/25"
         },
         ...
       ],
       "plan_duration_weeks": 14,
       "race_metadata": {
         "race_date": "2026-02-15",
         "race_distance": "26.2 mi Marathon"
       }
     },
     "validation": {
       "valid": true/false,
       "violations": [...]
     },
     "time_assessment": "14 weeks needed, 16 weeks available. Inserted 2 recovery weeks."
   }
   ```

---

## Key Characteristics

### ✅ **All Deterministic (No LLM for Plan Generation)**

- Long run progression: Pure formula based on starting point
- Weekly totals: Percentage-based calculation
- Workout distribution: Percentage-based allocation
- All rounding/pacing: Mathematical, predictable

### ✅ **Safety-First Rules**

- Week 1 starts at user's baseline + 1 mile
- Weekly increase cap: +8% max
- Long run progression: +1 mile/week max (except cutbacks)
- Minimum 3 miles per non-long run
- Peak caps based on runs/week
- Cutback weeks every 4 weeks
- Single peak before taper
- 3-week taper pattern

### ✅ **Recovery-Aware Ordering**

- Monday (day after LR): Shortest run, easiest type
- Thursday: Medium distance, aerobic type
- Wednesday: Longest weekday run, endurance type
- Ensures proper recovery progression

### ✅ **Dynamic Plan Length**

- Calculated from starting long run
- Not hardcoded (was 14 weeks, now dynamic)
- Adapts to user's baseline fitness

---

## Files Involved

### **Routes:**

- `src/routes/plan_routes.py` → `create_plan_draft_route()` (lines 529-1089)

### **Core Services:**

- `src/services/training_plan/data_collection_service.py` (Layer 1)
- `src/services/training_plan/insights_calculation_service.py` (Layer 2)
- `src/services/training_plan/v2/shared_v2/pass1_weeks_selector_v2.py` (weeks recommendation)
- `src/services/training_plan/v2/marathon/v2/marathon/pass1_longrun_first_v2.py` (Pass 1: Long runs)
- `src/services/training_plan/v2/shared_v2/shared_v2/long_run_spine_v2.py` (LR progression logic)
- `src/services/training_plan/v2/marathon/weekly_total_calculator_v2.py` (Pass 2: Weekly totals)
- `src/services/training_plan/v2/pass3_workout_distribution_v2.py` (Pass 3: Workout distribution)
- `src/services/training_plan/recovery_week_insertion_service.py` (Recovery week insertion)

### **Legacy (Not Used in This Flow):**

- `src/services/training_plan/gpt_coach_pass1_weekly.py` (old LLM-based Pass 1)
- `src/services/training_plan/gpt_coach_pass2_longrun.py` (old LLM-based Pass 2)
- `src/services/training_plan/training_plan_orchestrator_service.py` (old 6-layer orchestrator)
- `src/services/training_plan/v2/plan_generation_orchestrator_v2.py` (old 3-pass orchestrator - not used in draft route)

---

## Summary

**The working process:**

1. **Collect** user data (L1) → **Calculate** insights (L2)
2. **Generate** long run progression deterministically (Pass 1 LR-first)
3. **Calculate** weekly totals from long runs (Pass 2)
4. **Distribute** workouts across days with recovery-aware ordering (Pass 3)
5. **Validate** for safety issues
6. **Assess** time and insert recovery weeks if needed
7. **Return** draft plan with all fields populated

**All steps are 100% code-based, deterministic, and testable.**
