"""
Plan workout taxonomy — SSOT for workout type definitions used in plan generation.

Moved from ``services.training_plan.v2.workout_taxonomy.workout_definitions``.
"""

from typing import Any, Dict, List

_ALLOWED_INTENSITY_LABELS = frozenset(
    {"very_easy", "easy", "moderate", "hard", "very_hard"}
)

_TIER_PRIMARY = "primary"
_TIER_SECONDARY = "secondary"

# =============================================================================
# WORKOUT DEFINITIONS - The core taxonomy (defined once, consumed everywhere)
# =============================================================================

WORKOUT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # PRIMARY — Easy
    # -------------------------------------------------------------------------
    "easy": {
        "tier": _TIER_PRIMARY,
        "display_name": "Easy",
        "placement_role": "easy",
        "intensity": "easy",
        "purpose": "recovery",
        "recovery_days": 0,
        "is_quality": False,
        "default_distribution_pct": None,
        "description": "Easy aerobic run for recovery and base building",
        "pace_guidance": "Easy",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "EASY",
    },
    # -------------------------------------------------------------------------
    # PRIMARY — Tempo (Z3)
    # -------------------------------------------------------------------------
    "tempo": {
        "tier": _TIER_PRIMARY,
        "display_name": "Tempo",
        "placement_role": "endurance",
        "intensity": "hard",
        "purpose": "lactate_threshold",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.10,
        "description": "Sustained effort at lactate threshold pace",
        "pace_guidance": "Tempo (comfortably hard, can speak in short phrases)",
        "ideal_for_races": ["10k", "half", "marathon"],
        "detail_archetype": "TEMPO",
    },
    # -------------------------------------------------------------------------
    # PRIMARY — Threshold (Z4)
    # -------------------------------------------------------------------------
    "threshold": {
        "tier": _TIER_PRIMARY,
        "display_name": "Threshold",
        "placement_role": "endurance",
        "intensity": "hard",
        "purpose": "lactate_threshold",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.08,
        "description": "Cruise intervals at threshold pace with short recovery",
        "pace_guidance": "Threshold (slightly faster than tempo)",
        "ideal_for_races": ["10k", "half", "marathon"],
        "detail_archetype": "TEMPO",
    },
    # -------------------------------------------------------------------------
    # PRIMARY — Long Run
    # -------------------------------------------------------------------------
    "long_run": {
        "tier": _TIER_PRIMARY,
        "display_name": "Long Run",
        "placement_role": "long",
        "intensity": "easy",
        "purpose": "endurance",
        "recovery_days": 2,
        "is_quality": False,
        "default_distribution_pct": None,
        "description": "Steady easy long run for aerobic endurance",
        "pace_guidance": "Easy",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "LONG",
    },
    # -------------------------------------------------------------------------
    # SECONDARY — Intervals (Z4 quality; parent primary = threshold)
    # -------------------------------------------------------------------------
    "intervals": {
        "tier": _TIER_SECONDARY,
        "display_name": "Intervals",
        "placement_role": "endurance",
        "primary_run_type": "threshold",
        "intensity": "very_hard",
        "purpose": "vo2max",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.07,
        "description": "High-intensity repeats with recovery jogs between",
        "pace_guidance": "Interval (hard effort, 3-5 min repeats)",
        "ideal_for_races": ["5k", "10k", "half"],
        "detail_archetype": "INTERVALS",
    },
    # -------------------------------------------------------------------------
    # SECONDARY — Hills (Z4 quality; parent primary = threshold)
    # -------------------------------------------------------------------------
    "hills": {
        "tier": _TIER_SECONDARY,
        "display_name": "Hills",
        "placement_role": "endurance",
        "primary_run_type": "threshold",
        "intensity": "hard",
        "purpose": "strength",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.08,
        "description": "Hill repeats for running-specific strength and power",
        "pace_guidance": "Hard effort uphill, easy jog recovery down",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "HILLS",
    },
}

WORKOUT_TYPES = frozenset(WORKOUT_DEFINITIONS.keys())
PRIMARY_WORKOUT_TYPES = frozenset(
    key for key, defn in WORKOUT_DEFINITIONS.items() if defn["tier"] == _TIER_PRIMARY
)
SECONDARY_WORKOUT_TYPES = frozenset(
    key for key, defn in WORKOUT_DEFINITIONS.items() if defn["tier"] == _TIER_SECONDARY
)
_PLACEMENT_ROLE_KEYS = frozenset({"easy", "steady", "endurance", "long"})


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_workout_definition(workout_type: str) -> Dict[str, Any]:
    """
    Get the full definition for a workout type.

    Args:
        workout_type: The workout type key (e.g., "tempo", "easy")

    Returns:
        Dict with all workout properties, or empty dict if not found
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {})


def workout_display_label(workout_type: str, *, default: str = "Easy") -> str:
    """Athlete-facing label for a taxonomy key (SSOT — never capitalize raw keys)."""
    key = str(workout_type or "").strip().lower()
    if not key:
        return default
    defn = get_workout_definition(key)
    if defn:
        return str(defn["display_name"])
    from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
        resolve_run_type,
    )

    return resolve_run_type(key).display_name


def athlete_label_for_plan_workout(
    *,
    workout_type: str | None = None,
    canonical_run_type_key: str | None = None,
    taxonomy_key: str | None = None,
) -> str:
    """
    Athlete-facing workout label for plan rows and API payloads.

    Prefers persisted ``workout_type`` when already a display string; otherwise
    resolves via taxonomy ``display_name`` (SSOT).
    """
    wt = str(workout_type or "").strip()
    wt_lower = wt.lower()
    if wt and wt_lower not in WORKOUT_TYPES and wt_lower not in _PLACEMENT_ROLE_KEYS:
        return wt
    if taxonomy_key and get_workout_definition(taxonomy_key):
        return workout_display_label(taxonomy_key)
    if canonical_run_type_key:
        from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
            resolve_run_type,
        )

        return workout_display_label(
            resolve_run_type(canonical_run_type_key).taxonomy_key
        )
    if wt_lower in WORKOUT_TYPES:
        return workout_display_label(wt_lower)
    return workout_display_label("easy")


def resolve_taxonomy_and_placement(raw_type: str) -> tuple[str, str]:
    """
    Map a planner/storage ``type`` string to ``(taxonomy_key, placement_role)``.

    Taxonomy keys (``tempo``, ``threshold``, …) map via SSOT definitions.
    Placement roles (``easy``, ``endurance``, ``long``, …) reverse-map through
    :func:`role_to_taxonomy` for pace/label lookups.
    """
    from src.smartcoach_mobile_coach.runner_profile.plan_placement import (
        role_to_taxonomy,
        validate_persisted_run_type_key,
    )

    key = str(raw_type or "easy").strip().lower()
    if not key:
        key = "easy"
    if get_workout_definition(key):
        return key, placement_role_for_taxonomy(key)
    placement_role = validate_persisted_run_type_key(key)
    return role_to_taxonomy(placement_role), placement_role


def taxonomy_short_label(workout_type: str, *, default: str = "Easy") -> str:
    """Back-compat alias for :func:`workout_display_label`."""
    return workout_display_label(workout_type, default=default)


def placement_role_for_taxonomy(workout_type: str) -> str:
    """Map a taxonomy key to a DB placement role (easy|steady|endurance|long)."""
    key = str(workout_type or "").strip().lower()
    defn = get_workout_definition(key)
    if not defn:
        allowed = ", ".join(sorted(WORKOUT_TYPES))
        raise ValueError(
            f"Unknown workout type {workout_type!r} (must be one of: {allowed})"
        )
    return str(defn["placement_role"])


def canonical_run_type_for_taxonomy(workout_type: str) -> str:
    """Resolve taxonomy/legacy key to canonical run type for scoring/zones."""
    from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
        RUN_TYPE_EASY,
        normalize_run_type_key,
    )

    return normalize_run_type_key(workout_type) or RUN_TYPE_EASY


def pace_zone_key_for_taxonomy(
    workout_type: str, *, has_marathon_finish: bool = False
) -> str:
    """Resolve pace-band key (z2, z3, z4, m) for a taxonomy workout type."""
    from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
        pace_zone_key_for_run_type,
    )

    return pace_zone_key_for_run_type(
        workout_type, has_marathon_finish=has_marathon_finish
    )


def taxonomy_pace_guidance(workout_type: str, *, default: str = "Easy") -> str:
    """Pace guidance string from taxonomy (Pass4 / orchestrator draft fields)."""
    key = str(workout_type or "").strip().lower()
    if not key:
        return default
    defn = get_workout_definition(key)
    guidance = defn.get("pace_guidance")
    return str(guidance) if guidance else default


def is_quality_workout(workout_type: str) -> bool:
    """
    Check if a workout is a "quality" (hard) workout.

    Quality workouts:
    - Require spacing (no back-to-back)
    - Need recovery days after
    - Should be limited per week

    Args:
        workout_type: The workout type key

    Returns:
        True if this is a quality workout
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("is_quality", False)


def get_recovery_days(workout_type: str) -> int:
    """
    Get the number of easy days recommended after this workout.

    Args:
        workout_type: The workout type key

    Returns:
        Number of recovery days needed (0-2 typically)
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("recovery_days", 0)


def get_detail_archetype(workout_type: str) -> str:
    """
    Get the detail archetype for Step 7 segment generation.

    Archetypes tell Pass4 which segment generator to use:
    - EASY: Simple easy run
    - STEADY: Controlled aerobic run
    - ENDURANCE: Medium-long run
    - LONG: Long run with optional MP finish
    - TEMPO: Continuous tempo block
    - INTERVALS: Repeats with recovery
    - HILLS: Hill repeats

    Args:
        workout_type: The workout type key

    Returns:
        Archetype string, defaults to "EASY" if not found
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("detail_archetype", "EASY")


def get_intensity(workout_type: str) -> str:
    """
    Get the intensity level of a workout.

    Intensity levels:
    - very_easy: Recovery pace
    - easy: Conversational pace
    - moderate: Steady, controlled effort
    - hard: Challenging but sustainable
    - very_hard: Near maximal effort

    Args:
        workout_type: The workout type key

    Returns:
        Intensity string, defaults to "easy" if not found
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("intensity", "easy")


def get_quality_workouts() -> List[str]:
    """
    Get list of all quality workout types.

    Returns:
        List of workout type keys that are quality workouts
    """
    return [k for k, v in WORKOUT_DEFINITIONS.items() if v.get("is_quality", False)]


def get_workouts_for_race(race_type: str) -> List[str]:
    """
    Get workout types ideal for a specific race distance.

    Args:
        race_type: Race type (e.g., "marathon", "half", "10k", "5k")

    Returns:
        List of workout type keys ideal for this race
    """
    return [
        k
        for k, v in WORKOUT_DEFINITIONS.items()
        if race_type in v.get("ideal_for_races", [])
    ]


# =============================================================================
# VALIDATION (run at import time)
# =============================================================================


def _validate_definitions() -> None:
    """Validate all workout definitions have required fields."""
    required_fields = [
        "tier",
        "display_name",
        "placement_role",
        "intensity",
        "purpose",
        "recovery_days",
        "is_quality",
        "description",
        "pace_guidance",
        "ideal_for_races",
        "detail_archetype",
    ]

    valid_intensities = _ALLOWED_INTENSITY_LABELS
    valid_archetypes = {
        "EASY",
        "STEADY",
        "ENDURANCE",
        "LONG",
        "TEMPO",
        "INTERVALS",
        "HILLS",
    }
    valid_placement_roles = {"easy", "steady", "endurance", "long"}

    assert WORKOUT_TYPES == PRIMARY_WORKOUT_TYPES | SECONDARY_WORKOUT_TYPES
    assert len(WORKOUT_TYPES) == 6

    for workout_type, defn in WORKOUT_DEFINITIONS.items():
        for field in required_fields:
            assert (
                field in defn
            ), f"Workout '{workout_type}' missing required field '{field}'"

        assert defn["tier"] in {_TIER_PRIMARY, _TIER_SECONDARY}
        assert defn["placement_role"] in valid_placement_roles

        if defn["tier"] == _TIER_SECONDARY:
            assert (
                "primary_run_type" in defn
            ), f"Secondary workout '{workout_type}' missing primary_run_type"
            assert defn["primary_run_type"] in PRIMARY_WORKOUT_TYPES
        else:
            assert "primary_run_type" not in defn

        assert defn["intensity"] in valid_intensities
        assert defn["detail_archetype"] in valid_archetypes

        if defn["is_quality"]:
            assert (
                defn["recovery_days"] >= 2
            ), f"Quality workout '{workout_type}' must have recovery_days >= 2"

    assert placement_role_for_taxonomy("tempo") == "endurance"
    assert placement_role_for_taxonomy("threshold") == "endurance"
    assert workout_display_label("long_run") == "Long Run"
    assert workout_display_label("threshold") == "Threshold"
    assert canonical_run_type_for_taxonomy("threshold") == "threshold"
    assert canonical_run_type_for_taxonomy("steady") == "easy"
    taxonomy_key, placement = resolve_taxonomy_and_placement("tempo")
    assert taxonomy_key == "tempo"
    assert placement == "endurance"
    taxonomy_key, placement = resolve_taxonomy_and_placement("long")
    assert taxonomy_key == "long_run"
    assert placement == "long"


def iter_plan_workout_taxonomy_payload() -> list[dict[str, Any]]:
    """Read-only taxonomy slice for GET /api/runner-profile/zones."""
    out: list[dict[str, Any]] = []
    for key, defn in WORKOUT_DEFINITIONS.items():
        entry: dict[str, Any] = {
            "key": key,
            "tier": defn["tier"],
            "display_name": defn["display_name"],
            "placement_role": defn["placement_role"],
            "canonical_run_type_key": canonical_run_type_for_taxonomy(key),
            "intensity": defn["intensity"],
            "is_quality": defn["is_quality"],
            "recovery_days": defn["recovery_days"],
            "detail_archetype": defn["detail_archetype"],
            "pace_guidance": defn["pace_guidance"],
            "description": defn["description"],
        }
        if defn["tier"] == _TIER_SECONDARY:
            entry["primary_run_type"] = defn["primary_run_type"]
        out.append(entry)
    return out


def validate_weekly_template(
    template: List[str],
    *,
    frequency: int,
    context: str,
) -> None:
    """
    Validate a weekly workout template against plan workout taxonomy.

    Raises ``AssertionError`` when structure or workout keys are invalid.
    """
    assert (
        len(template) == frequency
    ), f"{context}: Template length {len(template)} != frequency {frequency}"
    assert template, f"{context}: Template must not be empty"
    assert (
        template[-1] == "long_run"
    ), f"{context}: Template must end with 'long_run', got '{template[-1]}'"
    for workout_type in template:
        assert workout_type in WORKOUT_TYPES, (
            f"{context}: Unknown workout type '{workout_type}' "
            f"(not in runner_profile.plan_workout_taxonomy)"
        )


# Run validation at import
_validate_definitions()
