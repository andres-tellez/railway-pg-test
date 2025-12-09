"""
Pace Calculation Configuration

Centralized configuration for pace zone calculations.
All magic numbers and thresholds are defined here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PaceConfig:
    """Configuration for pace zone calculations."""

    # Data requirements
    MIN_DISTANCE_MILES: float = 2.0
    LOOKBACK_WEEKS: int = 6
    MIN_RUNS_REQUIRED: int = 6

    # Pace bounds (seconds per mile)
    MIN_PACE_SEC_PER_MILE: float = 360.0  # 6:00/mile (very fast)
    MAX_PACE_SEC_PER_MILE: float = 1200.0  # 20:00/mile (very slow)

    # Pace zone offsets from median easy pace (seconds)
    EASY_MIN_OFFSET: float = -15.0
    EASY_MAX_OFFSET: float = 45.0
    STEADY_MIN_OFFSET: float = -15.0
    STEADY_MAX_OFFSET: float = 15.0
    MARATHON_OFFSET: float = -60.0
    THRESHOLD_MIN_OFFSET: float = -30.0  # Relative to marathon pace
    THRESHOLD_MAX_OFFSET: float = -20.0  # Relative to marathon pace

    # Week 1 long run cap calculation
    MIN_WEEK1_LONG_CAP: float = 8.0
    WEEK1_LONG_CAP_BUFFER: float = 2.0  # Add 2 miles to longest recent run
    MIN_RUN_FOR_LONG_CAP: float = 10.0  # Only consider runs >= 10 miles

    # Calibration defaults (for users without sufficient data)
    CALIBRATION_MARATHON_PACE: float = 600.0  # 10:00/mile
    CALIBRATION_EASY_MIN: float = 630.0  # 10:30/mile (adjusted to overlap with Steady)
    CALIBRATION_EASY_MAX: float = 690.0  # 11:30/mile
    CALIBRATION_STEADY_MIN: float = 630.0  # 10:30/mile
    CALIBRATION_STEADY_MAX: float = 660.0  # 11:00/mile
    CALIBRATION_THRESHOLD_MIN: float = 570.0  # 9:30/mile
    CALIBRATION_THRESHOLD_MAX: float = 580.0  # 9:40/mile


# Global default configuration instance
DEFAULT_CONFIG = PaceConfig()
