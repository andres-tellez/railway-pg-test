# Activity-to-Day Matching: Research & Better Approaches

## Problem Statement

The current frontend implementation treats activities as a **shared pool** that can be matched to multiple days, causing:
- Activities appearing on both their actual date AND nearby dates
- Duplicate displays when an activity matches multiple workouts
- Unclear user experience about which date an activity "belongs" to

## Current Architecture Issues

### Frontend (`weekTimelineUtils.ts`)
```typescript
// Current approach: Each day independently searches for activities
return weekDays.map(dateStr => {
  // Day 1: Finds activity on exact date → assigns it
  const activityOnThisDate = normalizedActivities.find(...);

  // Day 2: Also finds same activity via ±1 day tolerance → assigns it AGAIN
  activity = normalizedActivities.find(act => matchActivityToWorkout(act, workout));
});
```

**Problem**: No deduplication mechanism. Same activity can be assigned to multiple days.

### Backend (`week_log_service.py`) - Better Pattern
```python
matched_activity_ids = set()  # Prevent double-matching

for workout in week_workouts:
    for activity in week_activities:
        if activity_id in matched_activity_ids:
            continue  # Skip already matched

        # ... match logic ...

        if best_match:
            matched_activity_ids.add(activity_id)  # Mark as used
```

**Key Insight**: Uses a **deduplication set** to ensure one-to-one matching.

---

## Research: Better Approaches

### 1. **One-to-One Assignment Pattern** (Recommended)
**Pattern**: Treat this as an assignment problem where each activity can only be assigned to one day.

**Algorithm**:
1. **First Pass**: Assign activities to their exact date (date-based assignment)
2. **Second Pass**: For unmatched workouts, find best matching activity from remaining pool
3. **Deduplication**: Track used activities to prevent double-assignment

**Benefits**:
- ✅ Activities always appear on their actual date first
- ✅ Prevents duplicates
- ✅ Clear ownership model
- ✅ Matches backend pattern already in codebase

**Implementation**:
```typescript
function processWeekData(workouts, activities, weekStart, weekEnd) {
  const matchedActivityIds = new Set<string>();

  return weekDays.map(dateStr => {
    // First: Check exact date match (highest priority)
    const exactMatch = activities.find(act =>
      toDateString(act.date) === dateStr &&
      !matchedActivityIds.has(act.activity_id.toString())
    );

    if (exactMatch) {
      matchedActivityIds.add(exactMatch.activity_id.toString());
      return { activity: exactMatch, ... };
    }

    // Second: Check workout match (only if no exact match)
    if (workout) {
      const workoutMatch = activities.find(act =>
        !matchedActivityIds.has(act.activity_id.toString()) &&
        matchActivityToWorkout(act, workout)
      );

      if (workoutMatch) {
        matchedActivityIds.add(workoutMatch.activity_id.toString());
        return { activity: workoutMatch, ... };
      }
    }

    return { activity: undefined, ... };
  });
}
```

---

### 2. **Bipartite Matching Algorithm**
**Pattern**: Use graph theory to find optimal one-to-one matching.

**Algorithm**: Hungarian Algorithm or Maximum Bipartite Matching

**When to Use**:
- Complex scoring systems (multiple criteria)
- Need optimal global matching (not greedy)
- Performance matters for large datasets

**Complexity**: O(n³) for Hungarian, O(n²) for bipartite matching

**Benefits**:
- ✅ Mathematically optimal matching
- ✅ Handles complex scoring
- ✅ Prevents duplicates by design

**Drawbacks**:
- ❌ More complex implementation
- ❌ Overkill for simple date-based matching
- ❌ Harder to debug

**Example Libraries**:
- `hungarian-algorithm` (npm)
- `munkres-js` (npm)

---

### 3. **Date-First Assignment with Conflict Resolution**
**Pattern**: Assign by date first, then resolve conflicts.

**Algorithm**:
1. Group activities by date
2. For each date, assign activity to that date
3. If multiple activities on same date, use scoring to pick best match
4. For unmatched workouts, search remaining activities

**Benefits**:
- ✅ Date is primary key (intuitive)
- ✅ Handles multiple activities per day
- ✅ Clear conflict resolution

**Implementation**:
```typescript
// Group activities by date
const activitiesByDate = new Map<string, Activity[]>();
activities.forEach(act => {
  const date = toDateString(act.date);
  if (!activitiesByDate.has(date)) {
    activitiesByDate.set(date, []);
  }
  activitiesByDate.get(date)!.push(act);
});

// Assign with conflict resolution
return weekDays.map(dateStr => {
  const dateActivities = activitiesByDate.get(dateStr) || [];

  if (dateActivities.length === 1) {
    return { activity: dateActivities[0], ... };
  } else if (dateActivities.length > 1 && workout) {
    // Multiple activities: pick best match to workout
    const bestMatch = findBestMatch(dateActivities, workout);
    return { activity: bestMatch, ... };
  }
  // ... rest of logic
});
```

---

### 4. **Database-Level Assignment** (Alternative)
**Pattern**: Store explicit `workout_id → activity_id` mapping in database.

**Schema Addition**:
```sql
CREATE TABLE workout_activity_matches (
  workout_id INT PRIMARY KEY,
  activity_id BIGINT UNIQUE,
  match_score FLOAT,
  matched_at TIMESTAMP DEFAULT NOW()
);
```

**Benefits**:
- ✅ Single source of truth
- ✅ Persists across sessions
- ✅ Can be manually adjusted
- ✅ Audit trail

**Drawbacks**:
- ❌ Requires schema migration
- ❌ More complex sync logic
- ❌ Overhead for simple matching

**When to Use**:
- Need manual override capability
- Matching is expensive to compute
- Want historical matching data

---

## Recommended Solution

### **Option 1: One-to-One Assignment Pattern** (Best for Current Architecture)

**Why**:
1. ✅ Matches existing backend pattern (`week_log_service.py`)
2. ✅ Simple to implement (add deduplication set)
3. ✅ Solves duplicate display issue
4. ✅ Maintains date-first priority
5. ✅ No schema changes needed

**Implementation Steps**:
1. Add `matchedActivityIds` Set to `processWeekData`
2. Check set before assigning activity
3. Add activity ID to set after assignment
4. Test with edge cases (multiple activities per day, overlapping dates)

**Code Changes**:
- Modify `frontend/src/utils/weekTimelineUtils.ts`
- Add deduplication logic similar to backend pattern
- Ensure activities are marked as "used" after first assignment

---

### **Option 2: Date-First with Conflict Resolution** (If Multiple Activities Per Day)

**When to Use**: If users commonly have multiple activities per day (e.g., morning run + evening run).

**Implementation**: Combine date-first grouping with scoring-based conflict resolution.

---

## Comparison Matrix

| Approach | Complexity | Duplicates | Date Priority | Performance | Best For |
|----------|-----------|------------|---------------|-------------|----------|
| **One-to-One Assignment** | Low | ✅ Prevents | ✅ High | O(n) | Current use case |
| **Bipartite Matching** | High | ✅ Prevents | Medium | O(n²) | Complex scoring |
| **Date-First + Conflicts** | Medium | ✅ Prevents | ✅ Highest | O(n) | Multiple/day |
| **DB-Level Assignment** | Medium | ✅ Prevents | Configurable | O(1) lookup | Persistent matching |

---

## Edge Cases to Handle

1. **Multiple activities on same date**
   - Solution: Pick best match to workout, or show all (UI decision)

2. **Activity matches multiple workouts**
   - Solution: Deduplication set ensures only first match wins

3. **No activity on exact date, but matches nearby**
   - Solution: ±1 day tolerance only if no exact match exists

4. **Activity outside week range**
   - Solution: Filter before processing (already handled)

5. **Workout with no matching activity**
   - Solution: Show workout as uncompleted (already handled)

---

## References

- **Backend Pattern**: `src/services/training_plan/week_log_service.py::_match_workouts_flexible()`
- **Assignment Problem**: https://en.wikipedia.org/wiki/Assignment_problem
- **Bipartite Matching**: https://en.wikipedia.org/wiki/Matching_(graph_theory)
- **Hungarian Algorithm**: https://en.wikipedia.org/wiki/Hungarian_algorithm

---

## Conclusion

The **One-to-One Assignment Pattern** is the best fit because:
1. It solves the duplicate display issue
2. It matches the existing backend architecture
3. It's simple to implement and maintain
4. It preserves date-first priority (activities show on their actual date)
5. It requires minimal code changes

The key insight is that activities should be treated as **consumable resources** in an assignment problem, not as a shared pool that can be matched multiple times.
