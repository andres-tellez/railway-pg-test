# Week Analysis Logic - Easy to Understand Explanation

## Quick Answer: Which Week Are We Analyzing?

| What We're Doing | Week (by Monday Date) | Why |
|------------------|----------------------|-----|
| **Rebuilding/Updating** | Week of **Nov 3** (Nov 3-9) | The upcoming week that starts next Monday |
| **Analyzing** | Week of **Oct 27** (Oct 27-Nov 2) | The week that just ended (this week) |
| **Logic** | We analyze the current week to adjust next week | We look at this week's performance to adjust next week |

**Simple Explanation:**
- When scheduler runs on Sunday Nov 3, we're preparing **next week** (week of Nov 3)
- To decide how to adjust next week, we look at **this week's** performance (week of Oct 27)
- This is like a coach reviewing last week's training before planning next week

---

## The Complete Analysis Flow

### Step 1: What Happened This Week (Week of Oct 27)?

| Data | From Logs | What It Means |
|------|-----------|---------------|
| **Week Date** | Week of Oct 27 (Oct 27-Nov 2) | The week that just ended (this week) |
| **Planned Workouts** | 4 workouts | There were 4 runs planned |
| **Matched Workouts** | 0 out of 4 | 0 of the planned runs matched actual Strava runs |
| **Actual Miles Completed** | 0 miles | No miles were completed from the planned workouts |

**Why 0 matches?**
- The system tries to match planned workouts with actual Strava runs
- If you ran on different days, different distances, or didn't run, they don't match
- Logs say: "Matched 0/4 workouts for week 12"

### Step 2: Calculate Scores (Why 0.0%?)

| Score | Formula | Your Values | Result | Why |
|-------|---------|-------------|--------|-----|
| **Volume Score** | `(actual miles / planned miles) × 100` | `(0 / planned) × 100` | **0.0%** | 0 miles completed |
| **Intensity Score** | `(quality workouts completed / quality planned) × 100` | `(0 / quality planned) × 100` | **0.0%** | No quality workouts matched |
| **Consistency Score** | `(days completed / days planned) × 100` | `(0 / 4) × 100` | **0.0%** | 0 days with matched runs |

**Simple Explanation:**
- You had 4 workouts planned
- 0 of them matched your actual runs
- So: 0 miles completed / planned miles = 0%
- Result: All scores = 0.0%

### Step 3: Decision Logic (Why -5.0%?)

| Phase | Rule | Your Score | Check | Result |
|-------|------|------------|-------|--------|
| **Taper** | If volume < 50%, reduce by 5% | 0.0% | `0.0% < 50%` ✅ | Reduce volume by 5% |

**Decision Flow Table:**

| Step | Condition | Check | Result | Action Taken |
|------|-----------|-------|--------|--------------|
| 1 | Is volume_score < 50%? | `0.0% < 50%` | ✅ YES | Trigger volume reduction |
| 2 | What's the reduction? | Taper phase rule | `-5.0%` | Apply 5% reduction |
| 3 | Change pace? | Fatigue check | No fatigue | `0.0s` (no pace change) |
| 4 | Final Decision | Combined logic | `volume_decrease` | Reduce volume by 5% |

**Final Decision:**
- `decision_type`: `volume_decrease`
- `volume_change_pct`: `-5.0%`
- `pace_adjustment_sec`: `0.0s`

### Step 4: What Should Happen vs What Actually Happens

#### Row 2: Original Plan (Week of Nov 3 - Before Rebuild)

| Day | Distance | Workout Type | Pace Zone | Source |
|-----|----------|--------------|-----------|--------|
| Mon | 7.0 mi | Easy | @9:56-10:26/mi | From database |
| Tue | 0 mi | Rest | - | From database |
| Wed | 7.0 mi | Steady | @9:26-9:56/mi | From database |
| Thu | 10.0 mi | Endurance | @9:26-9:56/mi | From database |
| Fri | 0 mi | Rest | - | From database |
| Sat | 16.0 mi | Long | @9:56-10:26/mi | From database |
| Sun | 0 mi | Rest | - | From database |
| **Total** | **40.0 mi** | | | |

#### Row 3: Expected Updated Plan (What SHOULD Happen)

| Day | Original | Calculation | Adjusted | Logic |
|-----|----------|-------------|----------|-------|
| Mon | 7.0 mi | `7.0 × 0.95 = 6.65` | **6.65 mi** | Apply -5% volume reduction |
| Tue | 0 mi | Rest days not adjusted | 0 mi | Rest stays same |
| Wed | 7.0 mi | `7.0 × 0.95 = 6.65` | **6.65 mi** | Apply -5% volume reduction |
| Thu | 10.0 mi | `10.0 × 0.95 = 9.5` | **9.5 mi** | Apply -5% volume reduction |
| Fri | 0 mi | Rest days not adjusted | 0 mi | Rest stays same |
| Sat | 16.0 mi | `16.0 × 0.95 = 15.2` | **15.2 mi** | Apply -5% volume reduction |
| Sun | 0 mi | Rest days not adjusted | 0 mi | Rest stays same |
| **Total** | **40.0 mi** | `40.0 × 0.95 = 38.0` | **38.0 mi** | Overall 5% reduction |

#### Row 3: Actual Updated Plan (What ACTUALLY Happens)

| Day | Distance | Changed? | Why Same? | Code Issue |
|-----|----------|---------|-----------|------------|
| Mon | 7.0 mi | ❌ NO | Volume adjustment code missing | `miles` not modified |
| Tue | 0 mi | - | Rest days | (Expected) |
| Wed | 7.0 mi | ❌ NO | Volume adjustment code missing | `miles` not modified |
| Thu | 10.0 mi | ❌ NO | Volume adjustment code missing | `miles` not modified |
| Fri | 0 mi | - | Rest days | (Expected) |
| Sat | 16.0 mi | ❌ NO | Volume adjustment code missing | `miles` not modified |
| Sun | 0 mi | - | Rest days | (Expected) |
| **Total** | **40.0 mi** | ❌ NO | Same as original | No volume reduction applied |

### Step 5: Why Rows 2 and 3 Are Identical

| Component | Row 2 Value | Row 3 Value | Changed? | Reason |
|-----------|-------------|-------------|----------|--------|
| **Distances** | 7, 0, 7, 10, 0, 16, 0 mi | 7, 0, 7, 10, 0, 16, 0 mi | ❌ **NO** | Code doesn't apply volume adjustment |
| **Workout Types** | Easy, Rest, Steady... | easy, Rest, steady... | ✅ **YES** | Normalized (capitalization) |
| **Pace Zones** | @9:56-10:26/mi, etc. | @9:56-10:26/mi, etc. | ❌ **NO** | `pace_adjustment = 0.0s` (no change) |
| **Descriptions** | From database | Regenerated | ✅ **Maybe** | Pass4 regenerates cues/segments |

## Summary Table: Complete Logic Flow

| Step | Input | Logic | Output | Status | Code Location |
|------|-------|-------|--------|--------|---------------|
| **1. Analyze Week of Oct 27** | 0/4 workouts matched | `volume_score = (0 / planned) × 100` | Volume: 0.0% | ✅ Done | `week_analysis_service.py` |
| **2. Check Taper Rules** | Volume: 0.0% < 50% | If `< 50%` → reduce volume | Decision: `-5.0%` | ✅ Done | `adaptive_adjustment_service.py` |
| **3. Save Decision** | Decision calculated | Save to database | Saved to DB | ✅ Done | `weekly_metrics_service.py` |
| **4. Apply to Distances** | `volume_change = -5.0%` | `miles × (1 + -5.0/100)` | **NOT APPLIED** | ❌ **Missing** | `weekly_rebuild_service.py` line 433 |
| **5. Regenerate Details** | Same distances + pace seed | Pass4 regenerates | Details updated | ✅ Done | `v2/v2/pass4_workout_details_v2_v2.py` |

## The Missing Code (Line 433)

**Current Code (NOT applying volume adjustment):**
```python
# Line 425-438 in weekly_rebuild_service.py
week_plan = {
    'workouts': [
        {
            'miles': float(w.miles),  # ❌ Original distance (not adjusted)
            ...
        }
        for w in week_workouts  # From database - original distances
    ]
}
# ❌ No code applies volume_change_pct here!
```

**What Should Be There (Missing Code):**
```python
# After creating week_plan, BEFORE passing to Pass4:
if decision and decision.volume_change_pct != 0:
    # Apply volume adjustment to each workout
    for workout in week_plan['workouts']:
        if workout['miles'] > 0:  # Don't adjust rest days
            workout['miles'] *= (1 + decision.volume_change_pct / 100)
            workout['distance_miles'] = workout['miles']  # Keep in sync
```

## Final Answers

| Question | Answer | Explanation |
|----------|--------|-------------|
| **Why Week of Oct 27?** | We're rebuilding week of Nov 3, analyze week of Oct 27 (this week) | Code: `previous_week_num = week_num - 1` analyzes the previous week |
| **Why 0.0% scores?** | 0 out of 4 workouts matched actual runs | Formula: `(0 miles / planned miles) × 100 = 0%` |
| **Why -5.0% decision?** | Taper phase rule: if volume < 50%, reduce 5% | Rule: `0.0% < 50%` → reduce by 5% |
| **Why rows 2 & 3 same?** | Volume adjustment **calculated but NOT applied** | Code at line 433 doesn't modify distances |
