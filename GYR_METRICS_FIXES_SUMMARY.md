# GYR Metrics Calculation & Tooltip Fixes

## Changes Made

### 1. ✅ Fixed Total Runs Calculation (Backend)

**File:** `src/services/gyr_metrics_service.py`

**Problem:**

- Was converting planned miles → estimated run count
- Compared actual run count to estimated run count
- Inaccurate because run distribution varies (4 runs @ 10mi ≠ 8 runs @ 5mi)

**Solution:**

- Now compares **actual miles to planned miles** directly
- `completion_pct = (actual_miles / planned_miles) × 100`
- Leftmost tick = sum of all miles run in previous week
- More accurate reflection of training plan adherence

**Code Changes:**

```python
# Before:
planned_runs = max(1, round(planned_miles / 7.5)) if planned_miles > 0 else 0
completion_pct = (actual_runs / planned_runs) * 100

# After:
actual_miles = trend.get("distance", 0)
planned_miles = goals_by_week.get(week_normalized, 0)
completion_pct = (actual_miles / planned_miles) * 100
```

### 2. ✅ Added Detailed Explanatory Tooltips (Frontend)

**File:** `frontend/src/utils/gyrCardUtils.ts`

**Problem:**

- Basic tooltip: `"Week 1: 2025-10-06 - 85% (yellow)"`
- Didn't explain WHY it got that score
- No context on actual vs planned

**Solution:**

- Created utility function similar to bar charts
- Shows actual data (miles, runs, pace, HR zones)
- Explains status criteria
- Uses emojis for quick visual feedback

**Example Tooltip for Total Runs:**

```
🟡 Week of 10/6
Actual: 28.5 mi (5 runs)
Planned: 35.0 mi
Completion: 81.4%
⚠ Below plan (70-90%)
```

**Example Tooltip for Weekly Pace:**

```
🟢 Week of 10/6
Current: 8:45/mi
3-wk Avg: 8:52/mi
✓ Same or faster than 3-wk avg
```

**Example Tooltip for HR Zones:**

```
🟢 Week of 10/6
Z1-Z2 Time: 78.5%
80/20 Training
✓ Good 80/20 balance (75-85%)
```

### 3. ✅ Updated Component Integration

**Files:**

- `frontend/src/components/cards/GYRMetricCard.tsx`
- `frontend/src/pages/GYRMetricsDemo.tsx`

**Changes:**

- Added `metricType` prop to GYRMetricCard
- Each card passes its type: `'totalRuns' | 'weeklyPace' | 'weeklyHRZones'`
- Tooltip generator uses type to show relevant data

### 4. ✅ Updated Criteria Text

**File:** `src/services/gyr_metrics_service.py`

**Changed:**

- Green: "90–110% of plan" → "90–110% of planned miles"
- Makes it clearer that we're comparing mileage, not run counts

## How It Works Now

### Data Flow:

1. **Database** (materialized view) aggregates actual miles per week
2. **Backend** compares actual miles vs planned miles from training plan
3. **Frontend** displays:
   - Visual GYR status (color-coded bars)
   - Detailed tooltip on hover with explanation
   - Legend showing criteria

### Leftmost Tick:

- Represents **previous week** (e.g., Monday Oct 6 - Sunday Oct 12)
- Shows sum of all miles run during that week
- Compared against planned miles for that week from training plan

### GYR Status Logic (Total Runs):

- 🟢 **Green**: 90-110% of planned miles (on track)
- 🟡 **Yellow**: 70-90% or 110-130% (slight deviation)
- 🔴 **Red**: <70% or >130% (significant deviation)
- ⚪ **Gray**: No data or no active plan

## Testing Verification

To verify the calculation is correct, hover over the leftmost bar and check:

1. "Actual" should match sum of miles from previous week's runs
2. "Planned" should match training plan's weekly mileage goal
3. "Completion %" should be (Actual / Planned) × 100
4. Status color should match the percentage ranges

## Benefits

✅ **Accurate**: Compares miles to miles (what plans specify)
✅ **Transparent**: Tooltips explain the "why" behind each status
✅ **User-Friendly**: Easy to understand hover explanations
✅ **Consistent**: Follows same pattern as other bar charts in the app
