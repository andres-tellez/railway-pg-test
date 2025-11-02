"""
Adaptive Training Constants - Centralized Configuration

Purpose:
    Centralize all thresholds, weights, and configuration values
    for adaptive training plan adjustments.

    Single source of truth prevents drift and makes tuning easy.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import Dict


# ============================================================================
# MATCHING CONFIGURATION
# ============================================================================

# Day window for flexible matching (±days)
MATCH_DAY_WINDOW = 3  # Match within ±3 days

# Distance tolerance for matching
MATCH_DISTANCE_TOLERANCE_EASY = 0.40  # ±40% for easy runs
MATCH_DISTANCE_TOLERANCE_QUALITY = 0.20  # ±20% for quality workouts

# Match score thresholds
MATCH_SCORE_PERFECT = 1.0  # Same day, same distance, same type
MATCH_SCORE_GOOD = 0.8  # Same type, within 2 days, ±30% distance
MATCH_SCORE_PARTIAL = 0.6  # Same type, within 3 days, ±40% distance
MATCH_SCORE_TYPE_ONLY = 0.4  # Correct type, wrong day/distance
MATCH_SCORE_NONE = 0.0  # No match


# ============================================================================
# METRIC THRESHOLDS
# ============================================================================

# Volume score thresholds
VOLUME_SCORE_LOW = 0.70  # <70% = low completion
VOLUME_SCORE_GOOD = 0.90  # ≥90% = good completion

# Intensity score thresholds
INTENSITY_SCORE_LOW = 0.60  # <60% = low quality completion
INTENSITY_SCORE_GOOD = 0.80  # ≥80% = good quality completion

# Consistency score thresholds
CONSISTENCY_SCORE_LOW = 0.60  # <60% = low consistency


# ============================================================================
# PHASE-SPECIFIC ADJUSTMENT RULES
# ============================================================================


@dataclass
class PhaseRules:
    """Adjustment rules for a specific training phase."""

    volume_low_threshold: float
    volume_good_threshold: float
    intensity_low_threshold: float
    pace_adjustment_max: float  # seconds per mile
    volume_adjustment_max: float  # percentage
    allow_volume_increase: bool
    allow_pace_increase: bool
    match_score_weights: Dict[str, float]  # Weighting for match_score


# Phase-specific rules
BASE_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.70,
    volume_good_threshold=0.90,
    intensity_low_threshold=0.60,
    pace_adjustment_max=15.0,  # More lenient
    volume_adjustment_max=15.0,
    allow_volume_increase=True,
    allow_pace_increase=True,
    match_score_weights={
        "volume": 0.5,
        "intensity": 0.2,
        "consistency": 0.2,
        "recovery": 0.1,
    },
)

BUILD_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.75,
    volume_good_threshold=0.90,
    intensity_low_threshold=0.60,
    pace_adjustment_max=10.0,
    volume_adjustment_max=15.0,
    allow_volume_increase=True,
    allow_pace_increase=True,
    match_score_weights={
        "volume": 0.4,
        "intensity": 0.3,
        "consistency": 0.2,
        "recovery": 0.1,
    },
)

PEAK_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.75,
    volume_good_threshold=0.90,
    intensity_low_threshold=0.70,  # Stricter on quality
    pace_adjustment_max=10.0,
    volume_adjustment_max=15.0,
    allow_volume_increase=False,  # Don't increase in peak
    allow_pace_increase=False,
    match_score_weights={
        "volume": 0.3,
        "intensity": 0.4,  # Prioritize quality
        "consistency": 0.2,
        "recovery": 0.1,
    },
)

TAPER_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.50,  # Very lenient
    volume_good_threshold=0.90,
    intensity_low_threshold=0.70,
    pace_adjustment_max=5.0,  # Very strict
    volume_adjustment_max=10.0,  # Very strict
    allow_volume_increase=False,  # Never increase in taper
    allow_pace_increase=False,
    match_score_weights={
        "volume": 0.2,
        "intensity": 0.4,
        "consistency": 0.3,
        "recovery": 0.1,
    },
)


# ============================================================================
# FATIGUE DETECTION CONFIGURATION
# ============================================================================

# Dynamic threshold percentages
FATIGUE_PACE_THRESHOLD_PCT = 0.02  # 2% of baseline pace
FATIGUE_HR_THRESHOLD_PCT = 0.03  # 3% of baseline HR
FATIGUE_PACE_THRESHOLD_MIN = 10.0  # Minimum 10 seconds
FATIGUE_LOAD_DELTA_THRESHOLD = 0.15  # 15% load increase

# Lookback period for baseline calculation
FATIGUE_BASELINE_WEEKS = 2  # Use last 2 weeks for baseline


# ============================================================================
# SAFETY CONSTRAINTS
# ============================================================================

# Hard limits (absolute maximums)
MAX_VOLUME_CHANGE_PCT = 15.0  # Never exceed ±15% volume change
MAX_PACE_CHANGE_SEC = 10.0  # Never exceed ±10 seconds/mile

# Progressive limits based on weeks remaining
SAFETY_LIMITS_BY_WEEKS_REMAINING = {
    "high": {  # >8 weeks
        "max_volume_pct": 15.0,
        "max_pace_sec": 10.0,
    },
    "medium": {  # 4-8 weeks
        "max_volume_pct": 10.0,
        "max_pace_sec": 5.0,
    },
    "low": {  # <4 weeks
        "max_volume_pct": 5.0,
        "max_pace_sec": 3.0,
    },
}


# ============================================================================
# TREND ANALYSIS CONFIGURATION
# ============================================================================

# Lookback period for trends
TREND_LOOKBACK_WEEKS = 2  # Analyze 2 weeks back
TREND_ROLLING_AVG_WEEKS = 3  # 3-week rolling average

# Anomaly detection threshold (standard deviations)
ANOMALY_THRESHOLD_SIGMA = 2.0


# ============================================================================
# GRACE PERIODS
# ============================================================================

# First N weeks of plan (lenient matching)
GRACE_PERIOD_WEEKS = 2

# Rebuild ramp after missed week
REBUILD_RAMP_PCT = 0.80  # Resume at 80% of previous load


class AdaptiveConfig:
    """Centralized configuration accessor."""

    @staticmethod
    def get_phase_rules(phase: str) -> PhaseRules:
        """Get phase-specific rules."""
        rules_map = {
            "Base": BASE_PHASE_RULES,
            "Build": BUILD_PHASE_RULES,
            "Peak": PEAK_PHASE_RULES,
            "Taper": TAPER_PHASE_RULES,
        }
        return rules_map.get(phase, BUILD_PHASE_RULES)

    @staticmethod
    def get_safety_limits(weeks_remaining: int) -> Dict[str, float]:
        """Get safety limits based on weeks remaining."""
        if weeks_remaining > 8:
            return SAFETY_LIMITS_BY_WEEKS_REMAINING["high"]
        elif weeks_remaining >= 4:
            return SAFETY_LIMITS_BY_WEEKS_REMAINING["medium"]
        else:
            return SAFETY_LIMITS_BY_WEEKS_REMAINING["low"]
