"""
Workout Detail Rules Configuration

Pass4 phase/quality/segment rules. Placement-role focus tags and warmup/cool-down
distances live in ``runner_profile.plan_placement`` (SSOT).
"""

from src.smartcoach_mobile_coach.runner_profile.plan_placement import (
    FOCUS_TAGS,
    WU_CD_MI,
)

# ============================================================================
# PHASE DEFINITIONS
# ============================================================================
PHASE = {
    "BASE": "Base",
    "BUILD": "Build",
    "PEAK": "Peak",
    "TAPER": "Taper",
}

PHASES_LIST = [
    PHASE["BASE"],
    PHASE["BUILD"],
    PHASE["PEAK"],
    PHASE["TAPER"],
]

QUALITY_ENABLED_PHASES = {PHASE["BUILD"], PHASE["PEAK"]}


def is_peak_like_phase(phase: str) -> bool:
    """True when ``phase`` should use Peak workout / intensity rules."""
    return phase == PHASE["PEAK"]


# ============================================================================
# STRIDES CONFIGURATION
# ============================================================================
STRIDES = {
    "enabled_phases": {PHASE["BUILD"], PHASE["PEAK"]},
    "min_run_mi": 4.0,  # Minimum run distance to suggest strides
    "reps": 4,
    "on_sec": 20,
    "off_sec": 40,
}

# ============================================================================
# MARATHON FINISH CONFIGURATION
# ============================================================================
MARATHON_FINISH = {
    "enabled_phases": {PHASE["PEAK"]},
    "min_lr_mi": 16.0,  # Minimum long run distance to trigger M-finish
    "finish_fraction": 0.25,  # Fraction of total distance for M-finish
    "min_finish_mi": 2.0,  # Minimum miles for M-finish segment
}

# ============================================================================
# VALIDATION TOLERANCES
# ============================================================================
SEGMENT_SUM_TOLERANCE = (
    1.5  # Relaxed further - segment totals are guidance, not safety-critical
)

# ============================================================================
# INTERVAL WORKOUT CONFIGURATION
# ============================================================================
# Threshold intervals for STEADY workouts in Build/Peak phases
THRESHOLD_INTERVALS = {
    "enabled_phases": {PHASE["BUILD"], PHASE["PEAK"]},
    "min_run_mi": 5.0,  # Minimum total distance to use intervals
    "interval_types": {
        "short": {  # For 5-7 mi total runs
            "reps": 4,
            "interval_mi": 0.25,  # 400m intervals
            "rest_mi": 0.25,  # 400m rest
        },
        "medium": {  # For 7-9 mi total runs
            "reps": 5,
            "interval_mi": 0.5,  # 800m intervals
            "rest_mi": 0.25,  # 400m rest
        },
        "long": {  # For 9+ mi total runs
            "reps": 4,
            "interval_mi": 0.75,  # 1200m intervals
            "rest_mi": 0.25,  # 400m rest
        },
    },
}

# Tempo blocks for STEADY workouts (alternative to intervals)
TEMPO_BLOCKS = {
    "enabled_phases": {PHASE["BUILD"], PHASE["PEAK"]},
    "min_run_mi": 6.0,
    "block_mi": 2.0,  # 2-mile tempo blocks
    "recovery_mi": 0.5,  # 0.5-mile recovery between blocks
    "max_blocks": 3,  # Maximum 3 tempo blocks
}

# ============================================================================
# UNITS (future: support km/mi conversion)
# ============================================================================
DEFAULT_UNITS = "mi"
