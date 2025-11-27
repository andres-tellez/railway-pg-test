"""
Placement Rules Engine - Configurable Rules for Workout Placement
=================================================================

PURPOSE
-------
This file defines the RULES that govern how workouts can be placed in a week.
These are safety and quality rules that every human coach applies automatically:
- No back-to-back hard days
- Easy day before long run
- Limit quality sessions per week
- Phase-specific restrictions

Rules are configurable and can be overridden per scenario.

STRUCTURE
---------
DEFAULT_RULES: Base rules applied to all plans
SCENARIO_RULES: Overrides for specific scenarios (injury_safe, aggressive, etc.)

RULE TYPES
----------
1. Spacing rules: How workouts relate to each other in time
2. Quantity rules: How many of each type per week
3. Phase rules: What's allowed in each training phase
4. Recovery rules: Minimum easy days between hard efforts

INVARIANTS (DO NOT VIOLATE)
---------------------------
1. Rules should be boolean or numeric (easy to evaluate)
2. Rule names should be self-documenting
3. Scenario rules MERGE with defaults (don't replace entirely)
4. validate_placement() must check ALL active rules

HOW TO ADD A NEW RULE
---------------------
1. Add rule to DEFAULT_RULES with appropriate default value
2. Add check in validate_placement() function
3. Optionally add scenario-specific overrides
4. Document the rule's purpose in comments

Author: SmartCoach Development Team
Last Updated: November 2025
"""

from typing import Dict, Any, List, Optional

from .workout_definitions import is_quality_workout, get_recovery_days

# =============================================================================
# DEFAULT RULES - Applied to all plans unless overridden
# =============================================================================

DEFAULT_RULES: Dict[str, Any] = {
    # -------------------------------------------------------------------------
    # SPACING RULES
    # -------------------------------------------------------------------------
    # No two quality workouts on consecutive days
    "no_back_to_back_hard": True,
    # Day before long run must be easy (not quality)
    "easy_before_long_run": True,
    # Quality workout should be at least 48 hours before long run
    # (This is softer than easy_before_long_run - allows 2 days gap)
    "quality_48hrs_before_long": True,
    # Minimum easy days between quality workouts
    "min_easy_between_hard": 1,
    # -------------------------------------------------------------------------
    # QUANTITY RULES
    # -------------------------------------------------------------------------
    # Maximum hard/quality days per week
    "max_hard_days_per_week": 2,
    # Maximum intervals sessions per week (subset of hard days)
    "max_intervals_per_week": 1,
    # -------------------------------------------------------------------------
    # PHASE RULES
    # -------------------------------------------------------------------------
    # No intervals during Base phase (aerobic focus only)
    "avoid_intervals_in_base": True,
    # No quality workouts during cutback/recovery weeks
    "avoid_quality_during_cutback": True,
    # No intensity in final 2 weeks before race (taper)
    "avoid_intensity_final_2_weeks": True,
    # -------------------------------------------------------------------------
    # RECOVERY RULES
    # -------------------------------------------------------------------------
    # After intervals, next day must be easy or rest
    "easy_after_intervals": True,
    # After tempo, next day should be easy
    "easy_after_tempo": True,
}


# =============================================================================
# SCENARIO-SPECIFIC RULE OVERRIDES
# =============================================================================

SCENARIO_RULES: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # INJURY-SAFE: More conservative, fewer hard days
    # -------------------------------------------------------------------------
    "injury_safe": {
        "max_hard_days_per_week": 1,
        "avoid_intervals_in_base": True,
        "avoid_intervals_in_build": True,  # Extra restriction
        "min_easy_between_hard": 2,  # More recovery
    },
    # -------------------------------------------------------------------------
    # RETURNING-TO-RUNNING: Very conservative
    # -------------------------------------------------------------------------
    "returning_to_running": {
        "max_hard_days_per_week": 1,
        "avoid_intervals_in_base": True,
        "avoid_intervals_in_build": True,
        "avoid_quality_during_cutback": True,
        "min_easy_between_hard": 2,
    },
    # -------------------------------------------------------------------------
    # AGGRESSIVE: For experienced runners with good recovery
    # -------------------------------------------------------------------------
    "aggressive": {
        "max_hard_days_per_week": 3,
        "max_intervals_per_week": 2,
        "avoid_quality_during_cutback": False,  # Can do light quality
        "min_easy_between_hard": 1,
    },
    # -------------------------------------------------------------------------
    # TIME-CONSTRAINED: More intensity to compensate for less volume
    # -------------------------------------------------------------------------
    "time_constrained": {
        "max_hard_days_per_week": 2,
        "avoid_intervals_in_base": False,  # Can introduce earlier
        "min_easy_between_hard": 1,
    },
    # -------------------------------------------------------------------------
    # EXTRA-TIME: Can be more conservative with intensity
    # -------------------------------------------------------------------------
    "extra_time": {
        "max_hard_days_per_week": 2,
        "avoid_intervals_in_base": True,
        "min_easy_between_hard": 2,  # More recovery since we have time
    },
}


# =============================================================================
# RULE RETRIEVAL
# =============================================================================


def get_rules(scenario: Optional[str] = None) -> Dict[str, Any]:
    """
    Get rules for a given scenario, merging with defaults.

    Scenario rules OVERRIDE defaults, they don't replace them entirely.
    This means you only need to specify rules that differ from default.

    Args:
        scenario: Optional scenario name (e.g., "injury_safe")

    Returns:
        Dict of all applicable rules
    """
    rules = DEFAULT_RULES.copy()

    if scenario and scenario in SCENARIO_RULES:
        rules.update(SCENARIO_RULES[scenario])

    return rules


# =============================================================================
# VALIDATION FUNCTION
# =============================================================================


def validate_placement(
    workouts: List[str],
    days: List[str],
    phase: str,
    is_cutback: bool,
    rules: Dict[str, Any],
    weeks_until_race: Optional[int] = None,
) -> Dict[str, List[str]]:
    """
    Validate workout placement against rules.

    Returns two categories of violations:
    - errors: Safety violations that should BLOCK plan creation
    - warnings: Quality violations that are logged but don't block

    Args:
        workouts: List of workout types in day order
        days: List of day names (for error messages)
        phase: Training phase ("Base", "Build", "Peak", "Taper")
        is_cutback: Whether this is a cutback/recovery week
        rules: Dict of rules to check (from get_rules())
        weeks_until_race: Optional weeks remaining (for taper rules)

    Returns:
        Dict with "errors" (blocking) and "warnings" (non-blocking) lists
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not workouts:
        return {"errors": errors, "warnings": warnings}

    # -------------------------------------------------------------------------
    # Count quality workouts
    # -------------------------------------------------------------------------
    quality_count = sum(1 for w in workouts if is_quality_workout(w))
    intervals_count = sum(1 for w in workouts if w == "intervals")

    # =========================================================================
    # SAFETY RULES (errors - block plan creation)
    # =========================================================================

    # SAFETY: No back-to-back hard days - high injury risk
    # Check CALENDAR day adjacency, not list index adjacency
    if rules.get("no_back_to_back_hard", True):
        DAY_TO_NUM = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }

        for i in range(len(workouts) - 1):
            if is_quality_workout(workouts[i]) and is_quality_workout(workouts[i + 1]):
                # Check actual calendar day distance
                day1_num = DAY_TO_NUM.get(days[i], 0)
                day2_num = DAY_TO_NUM.get(days[i + 1], 0)
                day_diff = (day2_num - day1_num) % 7

                # Only flag if truly adjacent (1 calendar day apart)
                if day_diff == 1:
                    errors.append(
                        f"Back-to-back hard days: {workouts[i]} ({days[i]}) "
                        f"and {workouts[i + 1]} ({days[i + 1]})"
                    )

    # SAFETY: Quality workout immediately before long run - high injury risk
    if rules.get("easy_before_long_run", True) and len(workouts) >= 2:
        long_run_idx = None
        for i, w in enumerate(workouts):
            if w == "long_run":
                long_run_idx = i
                break

        if long_run_idx is not None and long_run_idx > 0:
            prev_workout = workouts[long_run_idx - 1]
            if is_quality_workout(prev_workout):
                errors.append(
                    f"Quality workout ({prev_workout}) immediately before long run"
                )

    # SAFETY: Too many hard days per week - overtraining risk
    max_hard = rules.get("max_hard_days_per_week", 2)
    if quality_count > max_hard:
        errors.append(f"Too many hard days: {quality_count} > max {max_hard}")

    # =========================================================================
    # QUALITY RULES (warnings - log only, don't block)
    # =========================================================================

    # QUALITY: Too many interval sessions
    max_intervals = rules.get("max_intervals_per_week", 1)
    if intervals_count > max_intervals:
        warnings.append(
            f"Too many interval sessions: {intervals_count} > max {max_intervals}"
        )

    # QUALITY: Quality workout day after intervals
    if rules.get("easy_after_intervals", True):
        for i, w in enumerate(workouts[:-1]):  # Skip last day
            if w == "intervals":
                next_workout = workouts[i + 1]
                if is_quality_workout(next_workout):
                    warnings.append(
                        f"Quality workout ({next_workout}) day after intervals"
                    )

    # QUALITY: Intervals in Base phase
    if rules.get("avoid_intervals_in_base", True) and phase == "Base":
        if "intervals" in workouts:
            warnings.append("Intervals during Base phase (should focus on aerobic)")

    # QUALITY: Intervals in Build phase (injury_safe scenario)
    if rules.get("avoid_intervals_in_build", False) and phase == "Build":
        if "intervals" in workouts:
            warnings.append("Intervals during Build phase (injury_safe restriction)")

    # QUALITY: Quality during cutback
    if rules.get("avoid_quality_during_cutback", True) and is_cutback:
        if quality_count > 0:
            quality_types = [w for w in workouts if is_quality_workout(w)]
            warnings.append(
                f"Quality workout(s) ({', '.join(quality_types)}) during cutback week"
            )

    # QUALITY: Intensity in final 2 weeks (taper)
    if rules.get("avoid_intensity_final_2_weeks", True):
        if weeks_until_race is not None and weeks_until_race <= 2:
            if quality_count > 0:
                quality_types = [w for w in workouts if is_quality_workout(w)]
                warnings.append(
                    f"Quality workout(s) ({', '.join(quality_types)}) "
                    f"in final {weeks_until_race} week(s) before race"
                )

    return {"errors": errors, "warnings": warnings}


def check_rule(rule_name: str, rules: Dict[str, Any]) -> bool:
    """
    Check if a specific rule is enabled.

    Args:
        rule_name: Name of the rule to check
        rules: Dict of rules

    Returns:
        True if rule is enabled (truthy value)
    """
    return bool(rules.get(rule_name, False))


def get_max_hard_days(rules: Dict[str, Any]) -> int:
    """
    Get the maximum allowed hard days per week.

    Args:
        rules: Dict of rules

    Returns:
        Maximum hard days (default 2)
    """
    return rules.get("max_hard_days_per_week", 2)
