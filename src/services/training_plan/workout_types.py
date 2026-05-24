"""
Workout Type Configuration

Single source of truth for workout type definitions, distributions, and mappings.

This module centralizes:
- Internal type keys (canonical identifiers)
- Display labels (UI-facing names)
- Percentage distributions by frequency
- Slot counts (number of each role per frequency)
- Minimum mileage constraints

Invariants:
I1. Closest non-long day to LONG → EASY (smallest non-long mileage)
I2. Farthest non-long day → ENDURANCE (largest non-long mileage)
I3. Remaining day(s) → STEADY; within STEADY, farther gets more
I4. Never reduce the long run to satisfy minimums
I5. Works for any run_days order and any long_idx (3/4/5 runs)

Author: SmartCoach Development Team
Last Updated: January 2026
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
