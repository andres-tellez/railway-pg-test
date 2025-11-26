# Architectural Guardrails for Plan Generation

## Purpose
This document defines architectural principles and guardrails to prevent code drift and ensure maintainable, predictable plan generation.

## Core Principles

### 1. Single Source of Truth
**Rule:** Long run progression is calculated **once** in the spine generator. No other component modifies it.

**Enforcement:**
- Spine generator (`generate_long_run_spine`) is the ONLY place that calculates long run progression
- No post-processing of spine data
- If adjustments are needed, regenerate with different parameters

**Validation:**
- `_validate_spine_immutability()` validates spine structure and peak reached
- Fails fast if spine is invalid

### 2. Immutability After Generation
**Rule:** Spine data structures are immutable after generation.

**Implementation:**
- Spine is validated immediately after generation
- No component should modify `long_run_miles` after spine generation
- If modifications are detected, raise `AssertionError`

### 3. Configuration-Driven Development
**Rule:** No hardcoded values. All training parameters come from `RaceDistanceConfig`.

**Enforcement:**
- All numeric values must reference `config.*`
- Validation at import time (like `workout_types_v2.py`)
- Linter rules detect hardcoded numbers in plan generation code

**Example:**
```python
# ❌ BAD - Hardcoded
if weeks_needed >= 4:
    weeks_needed += 1

# ✅ GOOD - Config-driven
if weeks_needed >= config.cutback_every:
    weeks_needed += 1
```

### 4. Clear Layer Boundaries
**Rule:** Each layer has a single responsibility and cannot modify previous layers' outputs.

**Layer Contracts:**

```
Layer 1: Spine Generator
  Input: starting_long_run, total_weeks, peak_target, config
  Output: List[Dict[week_number, long_run_miles, phase]]
  Contract: NEVER modified after generation
  Side Effects: NONE

Layer 2: Weekly Totals Calculator
  Input: Spine (immutable)
  Output: Spine + weekly_mileage
  Contract: Only adds weekly_mileage, never modifies long_run_miles
  Side Effects: NONE

Layer 3: Workout Distribution
  Input: Weeks with totals
  Output: Weeks with workouts
  Contract: Only adds workouts, never modifies long_run_miles or weekly_mileage
  Side Effects: NONE

Layer 4: Workout Details
  Input: Weeks with workouts
  Output: Weeks with detailed workouts
  Contract: Only adds details, never modifies structure
  Side Effects: NONE

Layer 5: Validation
  Input: Complete plan
  Output: Validation result
  Contract: Read-only, never modifies plan
  Side Effects: NONE
```

### 5. No Post-Processing Rule
**Rule:** No component can modify the spine after generation. If changes are needed, regenerate.

**Enforcement:**
- Recovery week insertion removed (was post-processing)
- Spine generator handles extra weeks naturally
- If plan needs adjustment, regenerate with different parameters

### 6. Contract Documentation
**Rule:** Every public function must document:
- Input contracts (types, constraints)
- Output contracts (guarantees)
- Side effects (none allowed for spine generation)
- Dependencies

**Template:**
```python
def function_name(...) -> ReturnType:
    """
    CONTRACT:
        - Input: [describe inputs and constraints]
        - Output: [describe output guarantees]
        - Side Effects: NONE (or describe if any)
        - Dependencies: [list dependencies]

    GUARDRAILS:
        - [list any guardrails]

    ARCHITECTURAL PRINCIPLE:
        [describe how this fits into the architecture]
    """
```

## Extended Plan Logic Guardrails

### Fitness-Based Branching (CRITICAL)
**Rule:** Extended plan logic branches on **fitness-based recommendation**, NOT date constraint.

**Problem:**
- Extended plans are for users with MORE time (fitness-based), not less time (date-constrained)
- Branching on `available_weeks` (date-constrained) causes wrong plan structure
- Start date calculation uses wrong plan length

**Solution:**
```python
# ✅ CORRECT: Branch on fitness-based recommendation
use_extended_logic = constraints.recommended_weeks >= 16

if use_extended_logic:
    # Generate using fitness-based length
    weeks_long = generate_long_run_spine_extended(
        total_weeks_in_plan=constraints.recommended_weeks,  # Fitness-based!
        ...
    )
else:
    # Standard plan (may be constrained by race date)
    weeks_long = pass1.build(recommended_weeks=constraints.target_weeks)
```

**Enforcement:**
- Branching condition: `constraints.recommended_weeks >= threshold`
- Extended generator receives: `constraints.recommended_weeks` (fitness-based)
- Standard generator receives: `constraints.target_weeks` (may be date-constrained)
- Date calculation uses: `len(weeks_out)` (actual generated length)
- Trimming happens AFTER generation (preserves taper)

**Why This Matters:**
- Extended plans need proper structure (6-8 week base phase, gradual progression)
- Race date constraint only affects trimming, not structure
- Start date must align with actual generated plan length, not target length

### Plan Length Semantics
**Rule:** Distinguish between fitness-based recommendation and date-constrained target.

**Definitions:**
- `recommended_weeks`: Fitness-based recommendation (e.g., 16 weeks for 20-30 mpw)
- `available_weeks`: Weeks available until race date (e.g., 12 weeks)
- `target_weeks`: Minimum of recommendation and available (e.g., min(16, 12) = 12)

**Usage:**
- **Extended plan branching:** Use `recommended_weeks` (fitness-based)
- **Extended plan generation:** Use `recommended_weeks` (fitness-based)
- **Standard plan generation:** Use `target_weeks` (may be date-constrained)
- **Start date calculation:** Use `len(weeks_out)` (actual generated length)
- **Trimming:** Use `available_weeks` (date constraint)

## Removed Components

### Recovery Week Insertion Service
**Status:** DELETED

**Reason:**
- Created architectural conflict (two systems managing recovery)
- Post-processing violated single source of truth principle
- Caused code drift and unpredictable behavior

**Replacement:**
- Spine generator now handles extra weeks naturally
- Pass `recommended_weeks` (fitness-based) to extended spine generator
- Spine extends build phase with gradual progression

## Validation Points

### 1. Spine Generation Boundary
- Validates spine structure (all weeks have required fields)
- Validates peak is reached (within tolerance)
- Fails fast if invalid

### 2. Configuration Validation
- All config values validated at import time
- No hardcoded values in plan generation code
- Linter rules enforce config-driven development

### 3. Layer Boundaries
- Each layer validates its inputs
- Each layer validates its outputs
- No layer modifies previous layer's outputs

## Code Review Checklist

When reviewing plan generation code:

- [ ] Does this modify spine after generation? (REJECT if yes)
- [ ] Are all values from config? (REJECT if hardcoded)
- [ ] Does this have side effects? (REJECT if yes)
- [ ] Is the contract documented? (REJECT if no)
- [ ] Are there tests? (REJECT if no)
- [ ] Does this violate layer boundaries? (REJECT if yes)

## Testing Requirements

### Unit Tests
- Test that spine is never modified after generation
- Test that all values come from config
- Test that validation catches invalid spines
- Test that error messages are actionable

### Integration Tests
- Test full plan generation pipeline
- Test with various input parameters
- Test edge cases (short plans, long plans, etc.)
- Test that spine immutability is maintained

## Future Improvements

### 1. Immutable Dataclasses
Consider using `@frozen` dataclasses for spine weeks:
```python
@frozen
class SpineWeek:
    week_number: int
    long_run_miles: float
    phase: str
```

### 2. Type Safety
Add type hints and use mypy for static type checking.

### 3. Automated Checks
- Pre-commit hook to detect hardcoded numbers
- CI check that validates spine immutability
- Linter rule for missing contract documentation

## Examples

### ✅ Good: Config-Driven
```python
if weeks_needed >= config.cutback_every:
    weeks_needed += 1
```

### ❌ Bad: Hardcoded
```python
if weeks_needed >= 4:
    weeks_needed += 1
```

### ✅ Good: Immutable Spine
```python
spine = generate_long_run_spine(...)
validate_spine(spine)
# Pass spine to next layer - never modify
weeks_with_totals = calculate_weekly_totals_from_long_runs(spine, ...)
```

### ❌ Bad: Post-Processing
```python
spine = generate_long_run_spine(...)
# DON'T DO THIS - violates single source of truth
insert_recovery_weeks(spine, ...)
recalculate_long_runs(spine, ...)
```

## Summary

These guardrails ensure:
1. **Predictability:** Single source of truth for progression
2. **Maintainability:** Clear layer boundaries and contracts
3. **Testability:** Pure functions with no side effects
4. **Extensibility:** Configuration-driven, easy to modify
5. **Reliability:** Validation at every boundary

By following these principles, we prevent code drift and ensure the plan generation system remains maintainable and predictable.
