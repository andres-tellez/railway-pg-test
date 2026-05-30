"""
Mileage-slot math and persisted ``run_type_key`` validation.

``run_type_key`` on ``plan_workouts`` stores taxonomy keys (easy, tempo,
threshold, long_run, intervals, hills, race) — not legacy placement buckets.
Internal mileage-slot identifiers (``slot_large``, ``slot_medium``) are used
only for volume distribution math and are never persisted.
"""

from __future__ import annotations

# Taxonomy-aligned keys stored in plan_workouts.run_type_key (SSOT for persistence).
PERSISTED_RUN_TYPE_KEYS = frozenset(
    {"easy", "tempo", "threshold", "long_run", "intervals", "hills", "race"}
)
WORKOUT_TYPES = PERSISTED_RUN_TYPE_KEYS - {"race"}

# ============================================================================
# INTERNAL MILEAGE SLOTS (never persisted to run_type_key)
# ============================================================================
SLOT_LARGE = "slot_large"
SLOT_MEDIUM = "slot_medium"
SLOT_SMALL = "slot_small"

# Back-compat aliases for modules that imported the old names (internal only).
ENDURANCE = SLOT_LARGE
STEADY = SLOT_MEDIUM
EASY = SLOT_SMALL
LONG = "long"

ROLE_RANK_ORDER = [SLOT_LARGE, SLOT_MEDIUM, SLOT_SMALL]

NON_LONG_SHARES = {
    3: [0.55, 0.45],
    4: [0.40, 0.30, 0.30],
    5: [0.32, 0.25, 0.23, 0.20],
    6: [0.28, 0.22, 0.18, 0.16, 0.16],
}

SLOT_COUNTS = {
    3: {SLOT_LARGE: 1, SLOT_MEDIUM: 0, SLOT_SMALL: 1},
    4: {SLOT_LARGE: 1, SLOT_MEDIUM: 1, SLOT_SMALL: 1},
    5: {SLOT_LARGE: 1, SLOT_MEDIUM: 2, SLOT_SMALL: 1},
    6: {SLOT_LARGE: 1, SLOT_MEDIUM: 2, SLOT_SMALL: 2},
}

MIN_NON_LONG_DAY = 3

LONG_RUN_SHARE_RANGES = {
    3: (0.40, 0.50),
    4: (0.35, 0.45),
    5: (0.30, 0.40),
    6: (0.25, 0.30),
}

# Focus tags persisted on plan_workouts.focus (taxonomy keys).
FOCUS_TAGS: dict[str, str] = {
    "easy": "Recovery",
    "tempo": "Tempo",
    "threshold": "Threshold",
    "long_run": "Long – fueling practice",
    "long": "Long – fueling practice",
    "intervals": "Speed",
    "hills": "Strength",
    "race": "Race Day",
}

WU_CD_MI: dict[str, dict[str, float]] = {
    "easy": {"wu": 0.5, "cd": 0.5},
    "tempo": {"wu": 1.0, "cd": 1.0},
    "threshold": {"wu": 1.0, "cd": 1.0},
    "long_run": {"wu": 0.0, "cd": 0.0},
    "long": {"wu": 0.0, "cd": 0.0},
    "intervals": {"wu": 1.0, "cd": 1.0},
    "hills": {"wu": 1.0, "cd": 1.0},
    "race": {"wu": 0.0, "cd": 0.0},
}

_DEFAULT_WU_CD_MI = {"wu": 1.0, "cd": 1.0}

# Legacy placement-role strings accepted on read and normalized to taxonomy keys.
_LEGACY_PERSISTED_KEYS = frozenset({"steady", "endurance", "long"})

_PERSISTED_KEY_ALIASES: dict[str, str] = {
    "long": "long_run",
}


def normalize_persisted_run_type_key(
    raw: str | None,
    *,
    workout_type: str | None = None,
) -> str | None:
    """Normalize raw keys to a taxonomy persisted key for plan_workouts.run_type_key."""
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key:
        return None
    if key in _PERSISTED_KEY_ALIASES:
        return _PERSISTED_KEY_ALIASES[key]
    if key in PERSISTED_RUN_TYPE_KEYS:
        return key
    if key in _LEGACY_PERSISTED_KEYS:
        return _normalize_legacy_persisted_key(key, workout_type=workout_type)
    if key == "race day":
        return "race"
    return key


def _normalize_legacy_persisted_key(
    key: str,
    *,
    workout_type: str | None = None,
) -> str:
    if key == "steady":
        return "easy"
    if key == "long":
        return "long_run"
    if key == "endurance":
        inferred = recognize_run_type_key_from_workout_label(workout_type)
        if inferred:
            return inferred
        return "easy"
    return key


def validate_persisted_run_type_key(
    raw: str | None,
    *,
    workout_type: str | None = None,
) -> str:
    """
    Validate plan_workouts.run_type_key against taxonomy persisted keys.

    Matches DB constraint ``chk_run_type_key``.
    """
    key = normalize_persisted_run_type_key(raw, workout_type=workout_type)
    if key not in PERSISTED_RUN_TYPE_KEYS:
        allowed = ", ".join(sorted(PERSISTED_RUN_TYPE_KEYS))
        raise ValueError(
            f"Invalid run_type_key: {raw!r} (must be a workout type key: {allowed})"
        )
    return key


def recognize_run_type_key_from_workout_label(label: str | None) -> str | None:
    """Map a ``workout_type`` display label to a taxonomy run_type_key when recognized."""
    if not label or not str(label).strip():
        return None
    workout_type_lower = str(label).strip().lower()
    if "race" in workout_type_lower:
        return "race"
    if "threshold" in workout_type_lower:
        return "threshold"
    if "tempo" in workout_type_lower:
        return "tempo"
    if "interval" in workout_type_lower:
        return "intervals"
    if "hill" in workout_type_lower:
        return "hills"
    if "medium-long" in workout_type_lower or "medium long" in workout_type_lower:
        return "easy"
    if "long run" in workout_type_lower or workout_type_lower == "long":
        return "long_run"
    if "long" in workout_type_lower:
        return "long_run"
    if "easy" in workout_type_lower or "recovery" in workout_type_lower:
        return "easy"
    if workout_type_lower in WORKOUT_TYPES:
        return workout_type_lower
    return None


def infer_run_type_key_from_workout_label(
    label: str | None, *, default: str = "easy"
) -> str:
    """Infer ``run_type_key`` from a ``workout_type`` label."""
    return recognize_run_type_key_from_workout_label(label) or default


def infer_placement_role_from_label(label: str | None, *, default: str = "easy") -> str:
    """Back-compat alias for :func:`infer_run_type_key_from_workout_label`."""
    return infer_run_type_key_from_workout_label(label, default=default)


def role_to_taxonomy(role: str) -> str:
    """Map a persisted or legacy key to a taxonomy key for pace/label lookups."""
    from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
        get_workout_definition,
    )

    key = normalize_persisted_run_type_key(role) or str(role or "").strip().lower()
    if key in WORKOUT_TYPES or key == "race":
        return "long_run" if key == "long" else key
    if key in {SLOT_LARGE, SLOT_MEDIUM, SLOT_SMALL, ENDURANCE, STEADY, EASY}:
        return "easy"
    if get_workout_definition(key):
        return key
    return "easy"


def placement_display(taxonomy_key: str) -> str:
    from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
        workout_display_label,
    )

    return workout_display_label(taxonomy_key)


def placement_focus_tag(taxonomy_key: str, *, default: str = "Run") -> str:
    """Return plan_workouts.focus string for a taxonomy key or alias."""
    key = (
        normalize_persisted_run_type_key(taxonomy_key)
        or str(taxonomy_key or "").strip().lower()
    )
    return FOCUS_TAGS.get(key, default)


def placement_wu_cd_mi(taxonomy_key: str) -> dict[str, float]:
    """Return warmup/cool-down mile distances for Pass4 segment generation."""
    key = (
        normalize_persisted_run_type_key(taxonomy_key)
        or str(taxonomy_key or "").strip().lower()
    )
    return dict(WU_CD_MI.get(key, _DEFAULT_WU_CD_MI))


def _validate_config() -> None:
    for rpw, shares in NON_LONG_SHARES.items():
        assert (
            abs(sum(shares) - 1.0) < 1e-9
        ), f"Shares must sum to 1.0 for {rpw}-day plan, got {sum(shares)}"
        expected_slots = (
            SLOT_COUNTS[rpw][SLOT_LARGE]
            + SLOT_COUNTS[rpw][SLOT_MEDIUM]
            + SLOT_COUNTS[rpw][SLOT_SMALL]
        )
        assert expected_slots == len(shares), (
            f"Share count {len(shares)} != slot count {expected_slots} "
            f"for {rpw}-day plan"
        )

    assert ROLE_RANK_ORDER == [SLOT_LARGE, SLOT_MEDIUM, SLOT_SMALL]
    assert set(LONG_RUN_SHARE_RANGES.keys()) == {3, 4, 5, 6}


_validate_config()
