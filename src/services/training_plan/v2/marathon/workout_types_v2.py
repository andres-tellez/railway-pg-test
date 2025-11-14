"""
Workout Type Configuration V2

Single source of truth for workout type definitions, distributions, and mappings.

V2: Values come from RaceDistanceConfig instead of hardcoded constants.

This module centralizes:
- Internal type keys (canonical identifiers)
- Display labels (UI-facing names)
- Percentage distributions by frequency (from config)
- Slot counts (number of each role per frequency)
- Minimum mileage constraints (from config)

Invariants:
I1. Closest non-long day to LONG → EASY (smallest non-long mileage)
I2. Farthest non-long day → ENDURANCE (largest non-long mileage)
I3. Remaining day(s) → STEADY; within STEADY, farther gets more
I4. Never reduce the long run to satisfy minimums
I5. Works for any run_days order and any long_idx (3/4/5 runs)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Dict, List

from ..race_configs.base_config import RaceDistanceConfig
from ..race_configs.marathon_config import MarathonConfig

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
# SLOT COUNTS (number of each role per frequency)
# ============================================================================
# Maps: runs_per_week → {role: count}
# Must match NON_LONG_SHARES structure above.
SLOT_COUNTS = {
    3: {ENDURANCE: 1, STEADY: 0, EASY: 1},  # Total: 2 non-long slots
    4: {ENDURANCE: 1, STEADY: 1, EASY: 1},  # Total: 3 non-long slots
    5: {ENDURANCE: 1, STEADY: 2, EASY: 1},  # Total: 4 non-long slots
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
# INTENSITY ZONES (for future phase-aware adjustments)
# ============================================================================
# Base intensity zones that can be adjusted by phase (Base/Build/Peak/Taper)
# Example: ENDURANCE might become "E→steady" in Build, "E" in Base
INTENSITY_ZONE = {
    EASY: "E",
    STEADY: "E/steady",
    ENDURANCE: "E→steady",
    LONG: "E (optionally finish at M pace in peak phase)",
}


# ============================================================================
# HELPERS
# ============================================================================
def get_non_long_shares(runs_per_week: int, config: RaceDistanceConfig) -> List[float]:
    """Return non-long-run shares for a given frequency."""
    return config.non_long_shares[runs_per_week]


def get_slot_counts(runs_per_week: int) -> Dict[str, int]:
    """Return slot counts (ENDURANCE/STEADY/EASY) for given frequency."""
    return SLOT_COUNTS[runs_per_week]


def get_min_non_long_day(config: RaceDistanceConfig) -> float:
    """Minimum miles per non-long day."""
    return config.min_non_long_day


def get_long_run_share_range(runs_per_week: int, config: RaceDistanceConfig) -> tuple:
    """Allowable long-run share range for validation."""
    return config.long_run_percentage_ranges[runs_per_week]


# ============================================================================
# CONFIG VALIDATION
# ============================================================================
def _validate_config(config: RaceDistanceConfig) -> None:
    """Validate configuration at import time to catch errors early."""
    # Validate shares sum to 1.0 and match slot counts
    for rpw, shares in config.non_long_shares.items():
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
    assert set(INTENSITY_ZONE.keys()) == required_keys, (
        f"INTENSITY_ZONE missing keys: " f"{required_keys - set(INTENSITY_ZONE.keys())}"
    )

    # Validate ROLE_RANK_ORDER
    assert ROLE_RANK_ORDER == [ENDURANCE, STEADY, EASY], (
        f"ROLE_RANK_ORDER must be [ENDURANCE, STEADY, EASY], " f"got {ROLE_RANK_ORDER}"
    )

    # Validate long-run share ranges are defined for all frequencies
    assert set(config.long_run_percentage_ranges.keys()) == {3, 4, 5}, (
        f"LONG_RUN_SHARE_RANGES missing keys: "
        f"{set({3, 4, 5}) - set(config.long_run_percentage_ranges.keys())}"
    )


# Run validation at import time
_validate_config(MarathonConfig())

# Standalone execution for quick debugging
if __name__ == "__main__":
    _validate_config(MarathonConfig())
    print("Workout type configuration OK")
