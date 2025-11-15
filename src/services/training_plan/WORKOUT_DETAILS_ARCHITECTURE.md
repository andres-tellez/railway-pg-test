# Workout Details Architecture

## Overview

This document describes the architecture for adding detailed workout segments, pace guidance, and cues to training plans. The system supports both **prefill mode** (all weeks at creation) and **rolling mode** (week-by-week with adjustments).

## Architecture Components

### 1. Pace Seed Service (`pace_seed_service.py`)

**Purpose:** Generate initial pace zones (E, S, M, T) from Strava data or calibration.

**Two-Path Logic:**

1. **Strava Data Path** (preferred):

   - Fetches last 6 weeks of Strava activities
   - Calculates median easy pace from runs ≥2 miles
   - Derives pace zones: E = median ±15-45s, S = E ±15s, M = E -60s, T = M -20-30s
   - Caps Week 1 long run based on recent longest run

2. **Calibration Path** (fallback):
   - Uses conservative default (10:00/mi for "Just Finish" runners)
   - Derives zones from marathon pace using standard relationships
   - Safe defaults when no Strava data available

**Integration:**

- Uses `DataCollectionService.fetch_strava_activities()` for Strava data
- Called by Pass 4 to initialize pace zones

**Output:** `PaceSeed` dataclass with all pace zones in seconds per mile.

---

### 2. Weekly Adjuster (`weekly_adjuster.py`)

**Purpose:** Adjust pace seed based on week completion logs (RPE + completion rate).

**Adjustment Logic:**

- **Low completion (<60%)**: Slow all paces +15s, disable quality workouts
- **Very easy (RPE ≤2) + good completion (≥80%)**: Speed up -5s (runner is fitter)
- **Too hard (RPE ≥5)**: Slow all paces +10s, disable quality workouts

**Integration:**

- Called in rolling mode when rebuilding upcoming weeks
- Takes previous week's logs (`List[WeekLogRun]`) and adjusts `PaceSeed`

**Future Enhancement:**

- Can be extended to use HR zones if available
- Can add phase-aware adjustments (Base vs Peak)

---

### 3. Pass 4 Workout Details (`v2/v2/pass4_workout_details_v2_v2.py`)

**Purpose:** Generate detailed segments, pace guidance, and cues for each workout.

**Features:**

- **Segments**: Warmup, main effort, cooldown (with distances and paces)
- **Cues**: Workout-specific guidance and tips
- **Pace Labels**: All pace zones (E, S, M, T) formatted as "mm:ss–mm:ss/mi"

**Workout Types:**

- **EASY**: Minimal warmup/cooldown, mostly easy pace
  - Optional: 4×20s strides in Build/Peak phases
- **STEADY**: Warmup → steady pace → cooldown
  - Optional: 4×20s strides mid-run in Build/Peak
- **ENDURANCE**: Longer steady effort at easy-steady pace
  - Optional: Last 2-3mi at marathon pace in Peak phase (if ≥6mi main)
- **LONG**: Mostly easy; in Peak optionally finish ~25% at marathon pace (if ≥16mi)

**Quality Workouts:**

- Only allowed in Build/Peak phases
- Automatically disabled if week completion <60% or RPE ≥5

**Integration:**

- Uses existing `workout_types.py` constants (EASY, STEADY, ENDURANCE, LONG)
- Called by `v2/plan_generation_orchestrator_v2.py` after Pass 3
- Supports both "prefill" and "rolling" modes

---

### 4. Orchestrator Integration (`v2/plan_generation_orchestrator_v2.py`)

**Flow:**

1. Pass 1: Long-run progression
2. Pass 2: Weekly totals calculation
3. Pass 3: Workout distribution across days
4. **Pass 4: Add detailed segments and pace guidance** ← NEW
5. Validation

**Modes:**

- **`mode="prefill"`** (default): Generate details for all weeks using initial seed
- **`mode="rolling"`**: Generate details for Week 1 only; future weeks rebuilt weekly

**Future Enhancement:**

- Weekly rebuild endpoint: `/api/plan/<id>/week/<num>/rebuild`
- Uses `weekly_adjuster.py` to adjust paces based on completion logs

---

## Usage Examples

### Prefill Mode (All Weeks)

```python
from src.services.training_plan.v2/plan_generation_orchestrator_v2 import ThreePassOrchestrator

orchestrator = ThreePassOrchestrator()
result = orchestrator.generate_longrun_first(
    runner_ctx={
        "session": session,
        "user_id": user_id,
        "plan_request": plan_request,
        "training_days": ["Mon", "Wed", "Thu", "Sat"],
    },
    mode="prefill",  # Generate details for all weeks
)
```

### Rolling Mode (Week-by-Week)

```python
# Week 1 only
result = orchestrator.generate_longrun_first(
    runner_ctx={...},
    mode="rolling",  # Only week 1 now
)

# Later: rebuild Week 2 based on Week 1 logs
from src.services.training_plan.weekly_adjuster import adjust_seed_from_week, WeekLogRun
from src.services.training_plan.v2/pass4_workout_details_v2 import Pass4WorkoutDetails

week1_logs = [
    WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=3),
    WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=4),
    WeekLogRun(run_type="long", planned_mi=8.0, done_mi=8.0, rpe=3),
]

adjusted_seed, disable_quality = adjust_seed_from_week(initial_seed, week1_logs)
pass4 = Pass4WorkoutDetails()
week2_with_details = pass4.add_details_to_week(
    week=week2,
    seed=adjusted_seed,
    allow_quality=not disable_quality,
)
```

---

## Data Structure

### Workout with Details

```json
{
  "day": "Mon",
  "type": "easy",
  "miles": 4.0,
  "segments": [
    { "name": "Warm-up", "mi": 0.5, "pace": "10:00–10:45/mi" },
    { "name": "Easy", "mi": 3.0, "pace": "10:00–10:45/mi" },
    { "name": "Cool-down", "mi": 0.5, "pace": "10:00–10:45/mi" }
  ],
  "cues": "Conversational effort; keep it relaxed. Optional: 4×20s relaxed strides with 40s easy jog.",
  "pace_labels": {
    "E": "10:00–10:45/mi",
    "S": "9:30–10:00/mi",
    "M": "9:00/mi",
    "T": "8:30–8:40/mi"
  }
}
```

---

## Future Enhancements

1. **Weekly Rebuild Endpoint**: Automatically rebuild upcoming week each Sunday
2. **HR Zone Integration**: Use HR zones in addition to RPE for adjustments
3. **Phase-Aware Adjustments**: Different adjustment logic for Base vs Peak
4. **Terrain-Aware Paces**: Adjust paces based on race terrain metadata
5. **Recovery Day Detection**: Automatically detect if runner needs easier paces

---

## Testing

See:

- `tests/services/training_plan/test_pace_seed_service.py`
- `tests/services/training_plan/test_weekly_adjuster.py`
- `tests/services/training_plan/test_v2/v2/pass4_workout_details_v2_v2.py`

---

## Notes

- **Safety First**: All defaults are conservative for "Just Finish" runners
- **Extensibility**: Easy to add new workout types or segments
- **Modularity**: Each component can be tested and modified independently
- **Backward Compatible**: Existing plans without details still work
