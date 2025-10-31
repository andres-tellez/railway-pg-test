# Quick Launch Checklist ✅

## Migration Order

- [x] **Alembic migration created**: `7a8b9c0d1e2f_add_workout_metadata_columns.py`

  - Adds: `run_type_key`, `phase`, `pace_ranges`, `allow_quality`, `cues`, `quality_insert`
  - All columns are nullable for backward compatibility
  - Includes check constraint and index

- [ ] **Run migration**: `alembic upgrade head`
- [ ] **Verify existing rows still insert/read** (all new cols nullable)

## Logging & Validation

- [x] **plan_storage_service has module-level logger**: `logger = logging.getLogger(__name__)`
- [x] **Sum-of-steps vs miles check**: `_validate_row()` checks `abs(tot - miles) < SEGMENT_SUM_TOLERANCE`
- [x] **Target bounds check**: Validates `target.low <= target.high` for all steps

## End-to-End Smoke Tests

- [x] **Smoke test suite created**: `tests/services/training_plan/test_launch_smoke.py`

  - Tests segments spec compliance
  - Tests pace_ranges structure
  - Tests intensity mapping (M only when Marathon step exists)
  - Tests all metadata fields present
  - Tests sample row format matches spec

- [ ] **Run smoke tests**: `pytest tests/services/training_plan/test_launch_smoke.py -v`
- [ ] **Generate plans for 3/4/5-day frequencies**: Manual test across Base→Taper
- [ ] **Verify one example write per week**:
  - `segments.units == 'mi'`
  - `segments.targetType == 'PACE'`
  - Each step has `durationType`, `value`, `target.low/high` (int sec)
  - `intensity` is "M" only when a Marathon step exists
  - `pace_ranges` present with integer seconds

## Config Hygiene

- [x] **All knobs centralized**: `workout_detail_rules.py`
  - WU/CD distances
  - Strides configuration
  - Marathon finish rules
  - Phase definitions
  - Intensity mapping
  - Focus tags
  - Tolerance constants

## Unit Invariant Documentation

- [x] **Unit invariant documented**: Added to `pass4_workout_details.py` header
  - "All pace targets are in seconds per mile (sec/mi) as integers"
  - "If/when km support is added, convert centrally in this module"

## Device/Export Path (Future)

- [x] **Segments JSON maps cleanly to Garmin steps**: Spec-compliant format
- [ ] **Adapter module** (`to_garmin()`) - Create when ready for device sync

## Sample Row Format

The generated row should match this structure:

```json
{
  "plan_id": 42,
  "date": "2026-01-17",
  "workout_type": "Endurance (Medium-Long)",
  "run_type_key": "endurance",
  "phase": "Peak",
  "miles": 10.0,
  "intensity": "S",
  "target_zone": "10:15–10:30/mi",
  "focus": "Medium-Long",
  "description": "Medium-long run; builds fatigue tolerance...",
  "cues": "Medium-long run; builds fatigue tolerance...",
  "pace_ranges": {
    "E": [645, 705],
    "S": [615, 630],
    "M": [600, 600],
    "T": [570, 580]
  },
  "allow_quality": true,
  "quality_insert": null,
  "segments": {
    "units": "mi",
    "targetType": "PACE",
    "steps": [
      {
        "name": "Warm-up",
        "durationType": "DISTANCE",
        "value": 1.0,
        "target": { "low": 645, "high": 705 },
        "intensity": "EASY"
      },
      {
        "name": "Endurance",
        "durationType": "DISTANCE",
        "value": 8.0,
        "target": { "low": 615, "high": 630 },
        "intensity": "STEADY"
      },
      {
        "name": "Cool-down",
        "durationType": "DISTANCE",
        "value": 1.0,
        "target": { "low": 645, "high": 705 },
        "intensity": "EASY"
      }
    ],
    "notes": "Medium-long run; builds fatigue tolerance..."
  }
}
```

## Next Steps

1. Run migration: `alembic upgrade head`
2. Run smoke tests: `pytest tests/services/training_plan/test_launch_smoke.py -v`
3. Generate a test plan and verify row structure in database
4. If all checks pass → **Ready for launch!** 🎯
