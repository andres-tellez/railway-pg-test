"""
Plan placement roles — mileage distribution roles (easy/steady/endurance/long).

Moved from ``services.training_plan.workout_types``.
"""

# ============================================================================
# CANONICAL TYPE KEYS
# ============================================================================
EASY = "easy"
STEADY = "steady"
ENDURANCE = "endurance"
LONG = "long"

# ============================================================================
# DISPLAY LABELS (UI-facing names)
# ============================================================================
TYPE_DISPLAY = {
    EASY: "Easy / Recovery",
    STEADY: "Aerobic / Steady",
    ENDURANCE: "Endurance (Medium-Long)",
    LONG: "Long Run",
}

# ============================================================================
# WORKOUT DESCRIPTIONS
# ============================================================================
TYPE_DESCRIPTIONS = {
    EASY: "Easy aerobic run for recovery and base building",
    STEADY: "Controlled aerobic run; steady, not hard",
    ENDURANCE: "Mid-week medium-long run at easy–steady effort; builds fatigue",
    LONG: "Steady easy long run",
}

# ============================================================================
# ROLE RANK ORDER
# ============================================================================
# Distances derived from NON_LONG_SHARES are applied in this rank:
# largest -> ENDURANCE, middle(s) -> STEADY, smallest -> EASY
ROLE_RANK_ORDER = [ENDURANCE, STEADY, EASY]

# ============================================================================
# NON-LONG SHARES (ranked longest → ... → shortest)
# ============================================================================
# These percentages define how non-long-run mileage is distributed.
# Order matters: first = largest distance (ENDURANCE), last = smallest (EASY)
# Shares must sum to 1.0 for each frequency.
NON_LONG_SHARES = {
    3: [0.55, 0.45],  # [ENDURANCE, EASY]
    4: [0.40, 0.30, 0.30],  # [ENDURANCE, STEADY, EASY]
    5: [0.32, 0.25, 0.23, 0.20],  # [ENDURANCE, STEADY, STEADY, EASY]
    6: [0.28, 0.22, 0.18, 0.16, 0.16],  # [ENDURANCE, STEADY, STEADY, EASY, EASY]
}

# ============================================================================
# SLOT COUNTS (number of each role per frequency)
# ============================================================================
# Maps: runs_per_week → {role: count}
# Must match NON_LONG_SHARES structure above.
SLOT_COUNTS = {
    3: {ENDURANCE: 1, STEADY: 0, EASY: 1},  # Total: 2 non-long slots
    4: {ENDURANCE: 1, STEADY: 1, EASY: 1},  # Total: 3 non-long slots
    5: {ENDURANCE: 1, STEADY: 2, EASY: 1},  # Total: 4 non-long slots
    6: {ENDURANCE: 1, STEADY: 2, EASY: 2},  # Total: 5 non-long slots
}

# ============================================================================
# CONSTRAINTS
# ============================================================================
MIN_NON_LONG_DAY = 3  # Minimum miles per non-long run day

# ============================================================================
# VALIDATION RANGES
# ============================================================================
# Expected long-run share of weekly total by frequency
LONG_RUN_SHARE_RANGES = {
    3: (0.40, 0.50),  # 40-50% for 3-day plans
    4: (0.35, 0.45),  # 35-45% for 4-day plans
    5: (0.30, 0.40),  # 30-40% for 5-day plans
    6: (0.25, 0.30),  # 25-30% for 6-day plans
}

# ============================================================================
# PACE GUIDANCE (for workout descriptions)
# ============================================================================
PACE_GUIDANCE = {
    EASY: "Easy",
    STEADY: "Steady",
    ENDURANCE: "Easy–Steady",
    LONG: "Easy",
}

# Focus tags persisted on plan_workouts.focus (placement roles).
FOCUS_TAGS: dict[str, str] = {
    EASY: "Recovery",
    STEADY: "Aerobic",
    ENDURANCE: "Medium-Long",
    LONG: "Long – fueling practice",
}

# Warmup/cool-down distances (miles) for Pass4 segment generation.
WU_CD_MI: dict[str, dict[str, float]] = {
    EASY: {"wu": 0.5, "cd": 0.5},
    STEADY: {"wu": 1.0, "cd": 1.0},
    ENDURANCE: {"wu": 1.0, "cd": 1.0},
    LONG: {"wu": 0.0, "cd": 0.0},
}

_DEFAULT_WU_CD_MI = {"wu": 1.0, "cd": 1.0}

PLACEMENT_ROLE_TYPES = frozenset({EASY, STEADY, ENDURANCE, LONG})

# Aliases accepted at plan_workouts.run_type_key write time (DB chk_run_type_key).
_PERSISTED_RUN_TYPE_ALIASES: dict[str, str] = {
    "long_run": LONG,
}

ROLE_TO_TAXONOMY_MAP: dict[str, str] = {
    LONG: "long_run",
    ENDURANCE: "easy",
    STEADY: "steady",
    EASY: "easy",
}


def role_to_taxonomy(role: str) -> str:
    return ROLE_TO_TAXONOMY_MAP.get(str(role or "").strip().lower(), "easy")


def normalize_persisted_run_type_key(raw: str | None) -> str | None:
    """Normalize raw keys to a placement role for plan_workouts.run_type_key."""
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key:
        return None
    return _PERSISTED_RUN_TYPE_ALIASES.get(key, key)


def validate_persisted_run_type_key(raw: str | None) -> str:
    """
    Validate plan_workouts.run_type_key against placement roles.

    Matches DB constraint ``chk_run_type_key`` (easy|steady|endurance|long).
    """
    key = normalize_persisted_run_type_key(raw)
    if key not in PLACEMENT_ROLE_TYPES:
        allowed = ", ".join(sorted(PLACEMENT_ROLE_TYPES))
        raise ValueError(
            f"Invalid run_type_key: {raw!r} (must be a placement role: {allowed})"
        )
    return key


def recognize_run_type_key_from_workout_label(label: str | None) -> str | None:
    """
    Map a ``workout_type`` display label to run_type_key when recognized.

    Returns ``None`` when the label does not match any known pattern.
    """
    if not label or not str(label).strip():
        return None
    workout_type_lower = str(label).strip().lower()
    if "threshold" in workout_type_lower or "tempo" in workout_type_lower:
        return "tempo"
    if "easy" in workout_type_lower or "recovery" in workout_type_lower:
        return EASY
    if "steady" in workout_type_lower or "aerobic" in workout_type_lower:
        return STEADY
    if "endurance" in workout_type_lower or "medium-long" in workout_type_lower:
        return ENDURANCE
    if "long" in workout_type_lower:
        return LONG
    return None


def infer_placement_role_from_label(label: str | None, *, default: str = EASY) -> str:
    """
    Infer placement role from a persisted ``workout_type`` display label.

    Used when ``run_type_key`` is missing (legacy rows, rebuild/week-log paths).
    """
    return recognize_run_type_key_from_workout_label(label) or default


def infer_run_type_key_from_workout_label(
    label: str | None, *, default: str = EASY
) -> str:
    """
    Infer ``run_type_key`` for HR/pace lookups from a ``workout_type`` label.

    Same recognition rules as :func:`infer_placement_role_from_label`, including
    tempo/threshold quality labels.
    """
    return recognize_run_type_key_from_workout_label(label) or default


def placement_display(role: str) -> str:
    return TYPE_DISPLAY.get(str(role or "").strip().lower(), str(role or "Easy Run"))


def placement_focus_tag(role: str, *, default: str = "Run") -> str:
    """Return plan_workouts.focus string for a placement role or alias."""
    key = normalize_persisted_run_type_key(role) or str(role or "").strip().lower()
    return FOCUS_TAGS.get(key, default)


def placement_wu_cd_mi(role: str) -> dict[str, float]:
    """Return warmup/cool-down mile distances for Pass4 segment generation."""
    key = normalize_persisted_run_type_key(role) or str(role or "").strip().lower()
    return dict(WU_CD_MI.get(key, _DEFAULT_WU_CD_MI))


# ============================================================================
# CONFIG VALIDATION
# ============================================================================
def _validate_config() -> None:
    """Validate configuration at import time to catch errors early."""
    # Validate shares sum to 1.0 and match slot counts
    for rpw, shares in NON_LONG_SHARES.items():
        assert (
            abs(sum(shares) - 1.0) < 1e-9
        ), f"Shares must sum to 1.0 for {rpw}-day plan, got {sum(shares)}"
        expected_slots = (
            SLOT_COUNTS[rpw][ENDURANCE]
            + SLOT_COUNTS[rpw][STEADY]
            + SLOT_COUNTS[rpw][EASY]
        )
        assert expected_slots == len(shares), (
            f"Share count {len(shares)} != slot count {expected_slots} "
            f"for {rpw}-day plan"
        )

    # Validate all dicts have complete keys
    required_keys = {EASY, STEADY, ENDURANCE, LONG}
    assert (
        set(TYPE_DISPLAY.keys()) == required_keys
    ), f"TYPE_DISPLAY missing keys: {required_keys - set(TYPE_DISPLAY.keys())}"
    assert set(TYPE_DESCRIPTIONS.keys()) == required_keys, (
        f"TYPE_DESCRIPTIONS missing keys: "
        f"{required_keys - set(TYPE_DESCRIPTIONS.keys())}"
    )
    assert set(PACE_GUIDANCE.keys()) == required_keys, (
        f"PACE_GUIDANCE missing keys: " f"{required_keys - set(PACE_GUIDANCE.keys())}"
    )
    assert set(FOCUS_TAGS.keys()) == required_keys
    assert set(WU_CD_MI.keys()) == required_keys
    # Validate ROLE_RANK_ORDER
    assert ROLE_RANK_ORDER == [ENDURANCE, STEADY, EASY], (
        f"ROLE_RANK_ORDER must be [ENDURANCE, STEADY, EASY], " f"got {ROLE_RANK_ORDER}"
    )

    # Validate long-run share ranges are defined for all frequencies
    assert set(LONG_RUN_SHARE_RANGES.keys()) == {3, 4, 5, 6}, (
        f"LONG_RUN_SHARE_RANGES missing keys: "
        f"{set({3, 4, 5, 6}) - set(LONG_RUN_SHARE_RANGES.keys())}"
    )


# Run validation at import time
_validate_config()

# Standalone execution for quick debugging
if __name__ == "__main__":
    _validate_config()
    print("Workout type configuration OK")
