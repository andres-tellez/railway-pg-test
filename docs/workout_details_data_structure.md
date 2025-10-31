# Workout Details Data Structure

## What Pass4 Generates

When `Pass4WorkoutDetails.add_details_to_plan()` runs, it adds three fields to each workout:

```python
workout = {
    "day": "Mon",
    "type": "easy",
    "distance_miles": 4.0,
    # NEW FIELDS FROM PASS4:
    "segments": [
        {
            "name": "Warm-up",
            "mi": 0.5,
            "pace": "10:00–10:45/mi"
        },
        {
            "name": "Easy",
            "mi": 3.0,
            "pace": "10:00–10:45/mi"
        },
        {
            "name": "Cool-down",
            "mi": 0.5,
            "pace": "10:00–10:45/mi"
        }
    ],
    "cues": "Conversational effort; keep it relaxed.",
    "pace_labels": {
        "E": "10:00–10:45/mi",
        "S": "9:30–10:30/mi",
        "M": "9:00/mi",
        "T": "8:30–8:40/mi"
    }
}
```

## Example: Long Run in Peak Phase

```python
{
    "day": "Sat",
    "type": "long",
    "distance_miles": 18.0,
    "segments": [
        {
            "name": "Easy",
            "mi": 14.0,
            "pace": "10:00–10:45/mi"
        },
        {
            "name": "Marathon finish",
            "mi": 4.0,
            "pace": "9:00/mi"
        }
    ],
    "cues": "Fuel 30–40g carbs every 30–40 min; sip fluids regularly. Finish last 25% at marathon pace if feeling strong.",
    "pace_labels": {
        "E": "10:00–10:45/mi",
        "S": "9:30–10:30/mi",
        "M": "9:00/mi",
        "T": "8:30–8:40/mi"
    }
}
```

## Database Schema (plan_workouts table)

```sql
CREATE TABLE plan_workouts (
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    date DATE NOT NULL,
    workout_type VARCHAR NOT NULL,      -- "Easy / Recovery", "Long Run", etc.
    description TEXT NOT NULL,           -- Currently set to workout description
    miles FLOAT NOT NULL,                -- Total distance
    intensity VARCHAR NOT NULL,          -- "Easy", "Steady", etc.
    target_zone VARCHAR NULL,            -- Optional
    target_hr VARCHAR NULL,              -- Optional
    focus VARCHAR NULL,                   -- Optional
    segments JSON NULL,                  -- ⚠️ SET TO NULL in plan_storage_service.py
    created_at TIMESTAMP NOT NULL
);
```

## ⚠️ PROBLEM: Segments Not Saved!

In `plan_storage_service.py` line 231:

```python
"segments": None,  # Optional JSON field
```

**The segments are generated but NOT saved to the database!**

The generated data structure has:

- `workout["segments"]` - List of segment objects
- `workout["cues"]` - String with guidance
- `workout["pace_labels"]` - Dict of pace zones

But when saving to database, only basic fields are saved:

- `workout_type`, `description`, `miles`, `intensity`
- `segments` is hardcoded to `None`

## Recommendation: Update plan_storage_service.py

The `_convert_workouts_to_db_format` function should extract and save:

1. **segments** - Save `workout.get("segments")` to `segments` JSON column
2. **cues** - Could save to `description` field or add new `cues` column
3. **pace_labels** - Could save as JSON or add separate columns

Example fix:

```python
workout_db = {
    "plan_id": plan_id,
    "date": workout_date,
    "workout_type": workout.get("workout_type", "Easy Run"),
    "description": workout.get("cues", ""),  # Use cues as description
    "miles": distance_miles,
    "intensity": workout.get("pace_guidance", "Easy"),
    "segments": workout.get("segments"),  # ✅ Save segments JSON!
    # Could also add pace_labels to description or as separate JSON
}
```
