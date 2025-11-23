# Training Plan Validation

This document describes the validation system that ensures training plans meet quality and safety standards.

## Validation Checks

### 1. Cutback Spacing Validation

**Rule**: Cutbacks must occur every `cutback_every` build weeks (default: 4 weeks).

**Checks**:
- First cutback must occur at build week `cutback_every` (e.g., build week 4)
- Subsequent cutbacks must be spaced exactly `cutback_every` build weeks apart
- No consecutive cutbacks allowed

**Example**:
- ✅ Correct: Cutbacks at build weeks 4, 8, 12
- ❌ Wrong: Cutbacks at build weeks 4, 7, 12 (spacing violation)
- ❌ Wrong: Cutbacks at build weeks 4, 5 (consecutive cutbacks)

### 2. Progression Safety

**Rule**: Long run increases must be gradual and safe.

**Checks**:
- Normal build weeks: Maximum 1 mile increase per week
- After cutback: Maximum 3 miles increase (resume week)
- No jumps >3 miles except immediately after cutback

**Example**:
- ✅ Correct: 14 → 17 → 18 → 19 → 20 (3-mile resume, then gradual)
- ❌ Wrong: 14 → 20 (6-mile jump, too aggressive)

### 3. Peak Achievement

**Rule**: Plan must reach the target peak long run before taper.

**Checks**:
- Peak long run (20 miles for marathon) must be achieved
- Peak must occur before taper phase begins

### 4. Taper Quality

**Rule**: Taper must follow correct ratios and be strictly decreasing.

**Checks**:
- Taper length: Minimum 2 weeks
- Taper ratios: 70%, 50%, 25% of peak (for 3-week taper)
- Strictly decreasing: Each week must be less than previous

## Running Validation

### Automatic Validation

Validation runs automatically after spine generation in `PlanGenerationOrchestratorV2`:

```python
# After spine generation
is_valid, quality_issues = validate_phase_quality(
    weeks_long,
    peak=self.config.target_peak_miles,
    cutback_every=self.config.cutback_every,
    taper_weeks=self.config.taper_weeks,
)
```

If validation fails, errors are logged with detailed messages.

### Manual Testing

Run the test script to validate a plan:

```bash
python test_plan_validation.py
```

This will:
1. Generate a training plan
2. Display the plan with cutback annotations
3. Validate cutback spacing
4. Run all quality checks
5. Report any violations

## Validation Output

### Success
```
✅ ALL VALIDATIONS PASSED
   - Cutback spacing is correct
   - No consecutive cutbacks
   - Safe progression
   - Peak reached
```

### Failure
```
❌ VALIDATION FAILURES:
   - Cutback spacing violations
   - Quality issues found:
     • Phase 1 (Build): First cutback at build week 3, expected at build week 4
     • Phase 1 (Build): Cutback spacing violation - Cutback at build week 4 followed by cutback at build week 7 (spacing: 3 weeks, expected: 4 weeks)
```

## Fixing Validation Issues

If validation fails, the issue is in the spine generation logic (`long_run_spine_v2.py`). Common fixes:

1. **Cutback spacing wrong**: Check `build_counter` logic in cutback condition
2. **Consecutive cutbacks**: Ensure `last_was_cutback` flag is properly managed
3. **Aggressive jumps**: Check `calculate_dynamic_resume` maximum increment cap
4. **Peak not reached**: Verify plan length is sufficient and progression logic is correct
