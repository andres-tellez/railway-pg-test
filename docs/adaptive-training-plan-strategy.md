# Strategy: Improved Adaptive Training Plan Logic

## Executive Summary

This document outlines a comprehensive strategy for improving the week-to-week adaptive training plan adjustment system. The current logic is too strict and fails to capture real-world training patterns. This proposal introduces multi-dimensional analysis, phase-aware adjustments, flexible matching algorithms, and enhanced refinements to create a more realistic and effective adaptive training system.

**Key Improvements:**

- Flexible matching (±2-3 days, ±30-40% distance) instead of exact day matching
- Multi-dimensional scoring (6 metrics: volume, intensity, consistency, pace, recovery, training load)
- Phase-aware adjustments (Base/Build/Peak/Taper have different priorities)
- Dynamic thresholds that adapt to individual athlete baselines
- Decision logging for explainability and debugging
- Training load delta tracking for better fatigue detection

---

## Current Problems Identified

1. **Overly Strict Matching**: Requires exact day + ±20% distance match, which fails when athletes shift runs to different days
2. **Binary Completion Logic**: Either "matched" or "not completed" - no partial credit for similar workouts
3. **Limited Data Analysis**: Only uses RPE and completion rate, ignores pace trends, volume patterns, and week-over-week progression
4. **No Phase Awareness**: Same adjustment logic in Base vs Peak vs Taper phases (should be different)
5. **No Trend Analysis**: Doesn't consider if performance is improving or declining over multiple weeks
6. **Fixed Thresholds**: Fatigue detection uses fixed values (10s, 5bpm) that don't scale across different athlete paces
7. **No Explainability**: Users don't know why their plan was adjusted

---

## Research-Based Best Practices

Based on research and proven coaching principles:

### 1. Holistic Week Analysis

- **Overall Volume**: Total miles vs planned
- **Intensity Distribution**: Easy vs hard days completion
- **Recovery Indicators**: Patterns of missed runs, fatigue markers
- **Trend Analysis**: 2-3 week trends vs single week snapshot
- **Training Load**: Proxy TSS calculation (distance × RPE) to track overall stress

### 2. Flexible Matching

- **Day Flexibility**: Match within ±2-3 days
- **Distance Flexibility**: ±30-40% for easy runs, tighter for quality workouts
- **Type Matching**: Focus on matching workout types (easy/steady/threshold) not just exact days

### 3. Phase-Aware Adjustments

- **Base Phase**: Focus on volume completion, be lenient on pace
- **Build Phase**: Balance volume and intensity adherence
- **Peak Phase**: Strict on quality workouts, allow easy run flexibility
- **Taper Phase**: Minimal changes, maintain intensity, reduce volume only if needed

### 4. Multi-Dimensional Scoring

- **Volume Score**: % of planned miles completed
- **Intensity Score**: Were quality workouts completed at target effort?
- **Consistency Score**: Days run vs planned
- **Pace Trend**: Is actual pace getting faster/slower vs planned?
- **Recovery Indicators**: Fatigue patterns, missed days
- **Training Load Delta**: Week-over-week load change (proxy TSS)

### 5. Realistic Constraints

- **Progressive Changes**: Max 5-10 seconds/mile adjustment per week
- **Weeks Remaining Factor**: Larger adjustments early, smaller near race
- **Safety Limits**: Never increase volume >15% week-over-week
- **Dynamic Thresholds**: Fatigue detection adapts to athlete's baseline pace/HR

---

## Proposed Multi-Dimensional Analysis

### Step 1: Enhanced Week Log Creation

**Instead of strict day matching, use flexible matching:**

Match workouts using:

1. Workout type matching (easy/steady/endurance/long/threshold)
2. Date proximity (within ±3 days)
3. Distance similarity (±40% for easy, ±20% for quality)
4. Time proximity (within same week, prefer closest)

**Scoring System:**

- Perfect match (same day, same distance, same type) = 1.0
- Good match (same type, within 2 days, ±30% distance) = 0.8
- Partial match (same type, within 3 days, ±40% distance) = 0.6
- Type match only (correct workout type, wrong day/distance) = 0.4
- No match = 0.0

For unmatched planned workouts, still create logs with `done_mi=0` but mark as "missed".

### Step 2: Multi-Dimensional Week Analysis

**Calculate 6 Key Metrics:**

#### 1. Volume Score (0-100%)

```
volume_score = min(100, (actual_total_miles / planned_total_miles) * 100)
```

#### 2. Intensity Adherence Score (0-100%)

```
quality_workouts_planned = count of threshold/tempo workouts
quality_workouts_completed = count completed (matched with correct type)
intensity_score = (quality_completed / quality_planned) * 100
```

#### 3. Consistency Score (0-100%)

```
days_planned = workouts scheduled
days_completed = days with at least one run
consistency_score = (days_completed / days_planned) * 100
```

#### 4. Pace Trend Analysis

```
For easy runs:
  avg_actual_pace = average pace of easy runs completed
  avg_planned_pace = average planned pace for easy runs
  pace_deviation = avg_actual_pace - avg_planned_pace
  (negative = faster than planned, positive = slower)

For quality runs:
  avg_actual_effort = average HR/pace for quality runs
  avg_planned_effort = target HR/pace for quality runs
  effort_deviation = avg_actual_effort - avg_planned_effort
```

#### 5. Recovery Indicators

- Consecutive missed days
- Declining pace trends
- Increasing HR at same pace
- Patterns of late-week fatigue

#### 6. Training Load Delta (NEW)

```
# Proxy TSS calculation
current_week_load = Σ(distance_mi × estimated_rpe)
prev_week_load = Σ(previous_week: distance_mi × estimated_rpe)

load_delta_pct = (current_week_load - prev_week_load) / max(prev_week_load, 1)
```

### Step 3: Dynamic Fatigue Detection (ENHANCED)

**Adaptive thresholds that scale with athlete baseline:**

Instead of fixed thresholds (10s slower, 5bpm higher), use percentage-based thresholds:

```python
# Calculate baseline from last 2-3 weeks
avg_pace_last_2weeks = calculate_average_pace(easy_runs, weeks=2)
avg_hr_last_2weeks = calculate_average_hr(easy_runs, weeks=2)

# Dynamic thresholds (2% pace slowdown, 3% HR increase)
pace_threshold = max(10, 0.02 * avg_pace_last_2weeks)  # Minimum 10s, or 2% of pace
hr_threshold = 0.03 * avg_hr_last_2weeks  # 3% of baseline HR

# Enhanced fatigue detection (load + pace + HR)
if (load_delta_pct > 0.15 AND  # Load spike >15%
    pace_trend > pace_threshold AND
    hr_trend > hr_threshold):
    trigger_fatigue_reduction(volume_reduction=10-15)
```

**Why Dynamic Thresholds Matter:**

- A 7:00/mi runner: 10s = 2.4% slowdown (significant)
- A 10:00/mi runner: 10s = 1.7% slowdown (less significant)
- Percentage-based thresholds normalize across all paces

### Step 4: Phase-Aware Adjustment Logic

**Different adjustment strategies per phase:**

#### BASE PHASE (weeks 1-40% of plan)

- **Focus**: Volume completion, building aerobic base
- **Adjustments**:
  - If volume_score < 70%: Reduce next week volume by 10-15%, slow paces by 5-10s
  - If volume_score >= 90% and pace_deviation < -10s: Volume increase OK, speeds up paces by 3-5s
  - If consistency_score < 60%: Simplify schedule, reduce quality workouts
- **Paces**: More lenient, allow ±15 seconds/mile without change

#### BUILD PHASE (weeks 40-70%)

- **Focus**: Balancing volume + intensity
- **Adjustments**:
  - If volume_score < 75% OR intensity_score < 60%: Reduce volume by 10%, slow paces by 10s
  - If volume_score >= 90% AND intensity_score >= 80%: Maintain or slightly increase volume
  - If pace_deviation consistently negative (faster): Gradually speed up paces by 5s
- **Paces**: Moderate strictness, allow ±10 seconds/mile

#### PEAK PHASE (weeks 70-90%)

- **Focus**: Quality workouts critical, volume maintenance
- **Adjustments**:
  - If intensity_score < 70%: Reduce easy run volume, keep quality workouts
  - If recovery indicators show fatigue: Reduce volume 10-15%, maintain paces
  - Only adjust paces if pace_deviation consistently >15s (too slow) or <-10s (too fast)
- **Paces**: Strict, only adjust if clear pattern (>2 weeks trend)

#### TAPER PHASE (weeks 90-100%)

- **Focus**: Maintain fitness, avoid overtraining
- **Adjustments**:
  - Minimal changes: Only if severe issues (volume_score < 50%)
  - If athlete struggling: Reduce volume further, maintain intensity
  - Never increase volume or speed up paces
- **Paces**: Very strict, no adjustments unless safety concern

### Step 5: Week-Over-Week Trend Analysis

**Don't just look at one week — analyze 2-3 week trends:**

```
For each metric (volume, intensity, pace, load):
  week_1_value = 2 weeks ago
  week_2_value = 1 week ago
  week_3_value = current week

  trend = calculate_trend([week_1, week_2, week_3])

  if trend == "declining":
    action = "reduce load, slow paces"
  elif trend == "improving":
    action = "maintain or slightly increase"
  elif trend == "stable":
    action = "maintain current plan"
```

### Step 6: Realistic Adjustment Constraints

**Safety Limits:**

- Max pace adjustment: ±10 seconds/mile per week
- Max volume adjustment: ±15% per week
- Weeks remaining factor:
  - > 8 weeks: Allow larger adjustments (±10s, ±15%)
  - 4-8 weeks: Moderate adjustments (±5s, ±10%)
  - <4 weeks: Minimal adjustments (±3s, ±5%)

**Grace Periods:**

- First 2 weeks of plan: Lenient matching, small adjustments
- After missed week: Gradual ramp-up (80% of previous load), not full load
- After recovery week: Resume normal progression

**Final Global Safety Check:**

```python
# Cap volume increases to +15% max (prevents cumulative overshoot)
if proposed_volume > (last_week_volume * 1.15):
    proposed_volume = last_week_volume * 1.15
    log_warning("Volume increase capped to +15% safety limit")
```

### Step 7: Weighted Composite Match Score (ENHANCEMENT)

**Single number to trigger adaptive thresholds:**

```python
match_score = (
    0.4 * volume_score +
    0.3 * intensity_score +
    0.2 * consistency_score +
    0.1 * recovery_score
) / 100

# Use match_score for decision thresholds
if match_score < 0.65:
    trigger_adjustment(severity="moderate")
elif match_score < 0.50:
    trigger_adjustment(severity="high")
```

**Phase-Based Weighting (Future Enhancement):**

- Base phase: `0.5*volume + 0.2*intensity + 0.2*consistency + 0.1*recovery`
- Peak phase: `0.3*volume + 0.4*intensity + 0.2*consistency + 0.1*recovery`

### Step 8: Context Score Modifier (FUTURE ENHANCEMENT)

**Placeholder for external factors:**

```python
context_score = {
    "weather": 1.0,      # 1.0 = normal, 0.8 = extreme heat/cold
    "travel": 1.0,      # 1.0 = normal, 0.5 = timezone change
    "life_stress": 1.0, # 1.0 = normal, 0.7 = high stress
    "race_week": False  # True during taper/race week
}

# Apply context modifier to volume adjustments
adjusted_volume = base_volume * context_score["weather"] * context_score["travel"]
```

**Implementation:**

- Phase 1: Add placeholder column in `weekly_metrics` table
- Phase 3: Add logic (weather API, travel detection, manual overrides)

---

## Decision Logging & Explainability

### Structured Decision Records

**Every adjustment must be logged with:**

```python
decision_log = {
    "week_num": 12,
    "timestamp": "2025-01-15T14:30:00Z",
    "decision": "Reduce volume 10%",
    "trigger": "Fatigue pattern detected",
    "metrics_used": {
        "volume_score": 73.0,
        "intensity_score": 50.0,
        "consistency_score": 75.0,
        "pace_trend": +12.0,  # seconds slower
        "hr_trend": +6.0,     # bpm higher
        "load_delta": +0.18   # 18% load increase
    },
    "adjustments_applied": {
        "volume_change_pct": -10.0,
        "pace_adjustment_sec": +5.0,
        "quality_workouts_removed": 0
    },
    "phase": "Build",
    "weeks_remaining": 8,
    "match_score": 0.68
}
```

### Database Schema

```sql
CREATE TABLE weekly_decision_log (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    week_num INTEGER NOT NULL,
    week_start_date DATE NOT NULL,
    decision_type VARCHAR(50),  -- "fatigue_reduction", "volume_increase", etc.
    trigger_reason TEXT,
    metrics_json JSONB,  -- All 6 metrics + trends
    adjustments_json JSONB,  -- Volume, pace, quality changes
    match_score DECIMAL(4,2),
    phase VARCHAR(20),
    weeks_remaining INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Integration Points

**Email Notifications:**

```
"Your plan was adjusted because:
- Volume completion: 73% (target: 90%+)
- Fatigue pattern detected (pace +12s, HR +6bpm over 2 weeks)
- Training load increased 18% from previous week
- Adjustment: Reduce volume 10%, maintain paces"
```

**UI Feedback:**

- "Why did my plan change?" button → show decision log
- Analytics dashboard: visualize decision history
- Trend graphs: overlay decision points

**Benefits:**

- **Explainability**: Users understand why adjustments were made
- **Debugging**: Developers can trace decision logic
- **Learning**: Review past decisions to improve algorithm
- **Transparency**: Builds trust with athletes

---

## Implementation Structure

### New Components Needed:

1. **Enhanced Week Log Service** (`week_log_service.py`)

   - Flexible matching algorithm
   - Multi-match scoring
   - Unmatched workout handling

2. **Week Analysis Service** (`week_analysis_service.py`) - NEW

   - Calculate 6 metrics (volume, intensity, consistency, pace, recovery, load)
   - Generate trend analysis (2-3 week lookback)
   - Calculate dynamic thresholds
   - Calculate weighted match_score

3. **Adaptive Adjustment Service** (`adaptive_adjustment_service.py`) - NEW

   - Phase-aware adjustment rules
   - Safety constraint checking
   - Grace period handling
   - Progressive change limits
   - Final global safety check

4. **Metrics Storage Service** (`weekly_metrics_service.py`) - NEW

   - Persistent storage of weekly metrics
   - Historical querying for trends
   - Decision log storage

5. **Integration with Weekly Rebuild** (`weekly_rebuild_service.py`)
   - Use enhanced analysis instead of simple completion/RPE
   - Apply phase-aware adjustments
   - Update pace seed with constraints
   - Generate decision logs

---

## Implementation Phases

### Phase 1: Core Improvements (Weeks 1-2)

**Goal**: Establish baseline adaptive loop

**Deliverables:**

- ✅ Flexible matching algorithm (±2-3 days, ±30-40% distance)
- ✅ Multi-dimensional scoring (6 metrics: volume, intensity, consistency, pace, recovery, load)
- ✅ Phase-aware adjustment rules (Base/Build/Peak/Taper)
- ✅ Final global safety check (cap volume +15%)
- ✅ Grace period logic (80% rebuild ramp after missed weeks)
- ✅ Dynamic fatigue detection (percentage-based thresholds)
- ✅ Training load delta (proxy TSS calculation)
- ✅ Decision logging (structured decision records)

**Success Criteria:**

- System adjusts plans based on weekly performance
- No dangerous volume spikes (>15% increase)
- All adjustments logged with reasons
- Dynamic thresholds work across different athlete paces

**Files to Create/Modify:**

- `src/services/training_plan/week_log_service.py` - Enhance matching
- `src/services/training_plan/week_analysis_service.py` - NEW
- `src/services/training_plan/adaptive_adjustment_service.py` - NEW
- `src/services/training_plan/weekly_rebuild_service.py` - Integrate new services

---

### Phase 2: Refinements (Weeks 3-4)

**Goal**: Introduce learning behavior

**Deliverables:**

- ✅ Persistent metrics storage (`weekly_metrics` table)
- ✅ Weighted composite match_score (0.4*volume + 0.3*intensity + 0.2*consistency + 0.1*recovery)
- ✅ 3-week rolling trend analysis (moving averages)
- ✅ Enhanced fatigue detection (load delta + pace + HR)
- ✅ Decision log UI integration ("Why did my plan change?")

**Success Criteria:**

- System identifies multi-week trends
- Match_score accurately predicts adjustment needs
- Historical metrics queryable for analytics
- Users can see why adjustments were made

**Files to Create/Modify:**

- `src/db/models/weekly_metrics.py` - NEW model
- `src/services/training_plan/weekly_metrics_service.py` - NEW
- `src/routes/metrics_routes.py` - Add decision log endpoint
- Frontend: Add decision log UI component

---

### Phase 3: Advanced Features (Weeks 5-6+)

**Goal**: Individualized automation

**Deliverables:**

- ✅ Context score integration (weather, travel, life stress)
- ✅ HRV/sleep data integration (if available)
- ✅ Z-score pace normalization (adaptive across runners)
- ✅ Adaptive phase boundaries (base on actual volume, not static %)
- ✅ Intensity score granularity (weight workouts by training stress)
- ✅ Phase-based match_score weighting

**Success Criteria:**

- System adapts to external factors
- Physiological data enhances decisions
- Phase timing responsive to athlete progress
- Workout stress properly weighted

**Files to Create/Modify:**

- `src/services/training_plan/context_service.py` - NEW
- `src/services/training_plan/phase_calculator.py` - Enhance
- Integration with HRV/sleep APIs (if available)

---

## Example Scenario

**Your Current Situation (from email):**

- Last week actual: Tue 6.8mi @ 9:27, Thu 6.0mi @ 10:18, Sat 15.0mi @ 9:35
- Planned: Mon 7.0mi easy, Wed 7.0mi steady, Thu 9.0mi endurance, Sat 15.0mi long

**New Logic Would:**

1. **Match workouts:**

   - Tue 6.8mi → Mon 7.0mi easy (0.8 score - same type, 1 day off, similar distance)
   - Thu 6.0mi → Wed 7.0mi steady (0.7 score - close type, 1 day off)
   - No match for Thu 9.0mi endurance (0.0 - no endurance run completed)
   - Sat 15.0mi → Sat 15.0mi long (1.0 score - perfect match)

2. **Calculate metrics:**

   - Volume score: 27.8mi / 38.0mi = 73% (moderate)
   - Intensity score: 1 quality (long) / 2 quality (steady + endurance) = 50%
   - Consistency score: 3 days / 4 days = 75%
   - Pace trend: Easy runs faster than planned (9:27 vs ~10:15 target)
   - Recovery indicators: 1 missed workout, pace faster (good sign)
   - Load delta: Calculate proxy TSS for current vs previous week

3. **Calculate dynamic thresholds:**

   - Baseline pace: ~9:45/mi (from last 2 weeks)
   - Baseline HR: ~145 bpm (from last 2 weeks)
   - Pace threshold: max(10s, 0.02 \* 585s) = max(10, 11.7) = 11.7s
   - HR threshold: 0.03 \* 145 = 4.35 bpm

4. **Apply adjustments (assuming Build phase, 8 weeks remaining):**

   - Volume score 73%: Reduce next week volume by ~8%
   - Intensity score 50%: Keep quality workouts but may reduce one
   - Pace trend: Speed up easy paces by 3-5 seconds (faster than planned consistently)
   - Match score: 0.68 (0.4*0.73 + 0.3*0.50 + 0.2*0.75 + 0.1*0.80)
   - **Result**: Adjust pace zones slightly faster, reduce volume slightly, maintain quality focus

5. **Log decision:**
   ```json
   {
     "decision": "Reduce volume 8%, speed up paces 3-5s",
     "trigger": "Moderate volume completion (73%), intensity below target (50%)",
     "match_score": 0.68,
     "adjustments": {
       "volume_change_pct": -8.0,
       "pace_adjustment_sec": -4.0
     }
   }
   ```

---

## Key Benefits

1. **More Realistic**: Handles real-world scheduling (runs on different days)
2. **Better Analysis**: Uses 6 data points, not just completion
3. **Phase-Appropriate**: Adjustments match training phase goals
4. **Trend-Aware**: Considers multi-week patterns, not just one week
5. **Safe**: Progressive adjustments with safety limits
6. **Flexible**: Accommodates life events while maintaining training structure
7. **Explainable**: Users understand why adjustments were made
8. **Scalable**: Dynamic thresholds work across all athlete paces
9. **Learning**: System can improve based on historical decisions

---

## Coaching Science Perspective

### What Works Extremely Well

1. **Phase-aware adjustments** - Matches real training theory. Each phase has different adaptation goals.

   - Example: Letting easy runs be flexible during Base but enforcing pace discipline in Peak = spot on.

2. **Flexible matching window (±2–3 days, ±30–40%)** - Reflects real-life schedule drift.

   - Avoids punishing consistent runners who just rearrange days.

3. **Multi-dimensional scoring** - Volume / Intensity / Consistency / Pace trend / Recovery / Load = perfect set.

   - These six together create a full "training stress fingerprint."

4. **Trend-based decisions (2–3 week lookback)** - Essential. Coaches don't react to one bad week — they look for patterns.

5. **Safety limits and progressive constraints** - The 10–15% volume and ±10s/mile pace boundaries are textbook Daniels + modern adaptive AI coaching safety standards.

6. **Phase priorities** - Build and Peak logic particularly good: maintain quality, protect recovery.

   - "Never increase volume or speed during taper" = critical safeguard.

7. **Decision logging** - Gold for debugging, explainability, or UI feedback ("why did my plan change?").

8. **Dynamic thresholds** - Scales across 7:00/mi and 10:00/mi runners without manual tuning.

### Minor Refinements to Consider

| Area                            | Suggestion                                                                        | Rationale                                                         |
| ------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Intensity Score Granularity     | Weight workouts by training stress (e.g., long tempo = 1.5x easy run)             | Avoid equal weighting for short vs major workouts                 |
| Pace Trend Analysis             | Use rolling z-score (vs absolute deviation)                                       | Makes it adaptive across runners with different baseline paces    |
| Recovery Indicators             | Incorporate HRV / sleep data (optional)                                           | Opens future integration for physiological data                   |
| Grace Period After Missed Weeks | Add "rebuild ramp" logic — e.g., resume at 80% previous load                      | Prevents accidental overload after illness/vacation               |
| Fatigue Detection               | Add rule: if pace slows >10s over 2 weeks and HR rises, auto-reduce volume 10–15% | Codifies real fatigue pattern                                     |
| Adaptive Phase Boundaries       | Base on actual training volume achieved, not static % of plan                     | Makes phase timing responsive (e.g., extend Base if inconsistent) |

### Technical/Structural Comments

1. **Perfect modular decomposition** - The architecture (week_log_service → week_analysis_service → adaptive_adjustment_service → weekly_rebuild_service) is clean and future-proof for ML-driven adjustment later.

2. **Matching Algorithm** - The scoring scale (1.0 → 0.4 → 0.0) is intuitive and can evolve easily. The weighted composite `match_score` provides a single number to trigger adaptive thresholds.

3. **Trend Analysis** - Storing each week's 5 metrics in a persistent table enables rolling 3-week moving averages for trends.

4. **Safety Layer** - The final global check (cap volume +15%) guarantees no cumulative overshoot.

---

## Technical Notes

### Current File Locations

- `src/services/training_plan/week_log_service.py` - Week log creation
- `src/services/training_plan/weekly_adjuster.py` - Pace adjustment logic
- `src/services/training_plan/weekly_rebuild_service.py` - Main rebuild service
- `src/services/training_plan/pace_seed_service.py` - Pace zone definitions

### Data Available

- `Activity` model: distance, pace, HR, date, splits
- `PlanWorkout` model: planned workouts with dates, types, segments
- `Splits` model: Per-mile data (currently not used but available)

### Phase Detection

Currently uses: `_determine_phase(week_num, total_weeks)` in `weekly_rebuild_service.py`

- Base: 0-40% of plan
- Build: 40-70%
- Peak: 70-90%
- Taper: 90-100%

### New Database Tables Needed

```sql
-- Weekly metrics storage
CREATE TABLE weekly_metrics (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    week_num INTEGER NOT NULL,
    week_start_date DATE NOT NULL,
    volume_score DECIMAL(5,2),
    intensity_score DECIMAL(5,2),
    consistency_score DECIMAL(5,2),
    pace_deviation DECIMAL(6,2),  -- seconds
    hr_deviation DECIMAL(6,2),    -- bpm
    load_delta_pct DECIMAL(6,2),
    match_score DECIMAL(4,2),
    context_score JSONB,
    phase VARCHAR(20),
    weeks_remaining INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plan_id, week_num)
);

-- Decision log
CREATE TABLE weekly_decision_log (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    week_num INTEGER NOT NULL,
    week_start_date DATE NOT NULL,
    decision_type VARCHAR(50),
    trigger_reason TEXT,
    metrics_json JSONB,
    adjustments_json JSONB,
    match_score DECIMAL(4,2),
    phase VARCHAR(20),
    weeks_remaining INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Future Enhancements (Post-Phase 3)

1. **Intensity Score Granularity**: Weight workouts by training stress (e.g., long tempo = 1.5x easy run)
2. **Z-Score Pace Normalization**: Use rolling z-score (vs absolute deviation) for adaptive analysis across runners
3. **HRV/Sleep Integration**: Incorporate physiological data when available
4. **Adaptive Phase Boundaries**: Base phase timing on actual volume achieved, not static %
5. **ML-Driven Adjustments**: Use historical decision logs to train adjustment models
6. **Real-Time Adjustments**: Allow mid-week plan modifications based on daily readiness

---

_Document created: January 2026_
_Last updated: January 2026_
_Author: SmartCoach Development Team_
_Status: Ready for Implementation_
