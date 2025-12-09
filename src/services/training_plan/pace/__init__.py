"""
Pace Zone Calculation Module

Performance-based pace zone calculation from recent run data.
Uses SQL-based median easy pace calculation for efficiency and reliability.
"""

from .models import PaceSeed
from .calculator import get_initial_pace_seed
from .adjustments import adjust_pace_seed, WeekLogRun
from .calibration import get_calibration_pace_seed
from .config import PaceConfig, DEFAULT_CONFIG
from .validation import validate_pace_seed, validate_input_parameters
from .strategies import (
    PaceCalculationStrategy,
    PerformanceBasedStrategy,
    CalibrationStrategy,
    DEFAULT_STRATEGIES,
)

__all__ = [
    "PaceSeed",
    "get_initial_pace_seed",
    "get_calibration_pace_seed",
    "adjust_pace_seed",
    "WeekLogRun",
    "PaceConfig",
    "DEFAULT_CONFIG",
    "validate_pace_seed",
    "validate_input_parameters",
    "PaceCalculationStrategy",
    "PerformanceBasedStrategy",
    "CalibrationStrategy",
    "DEFAULT_STRATEGIES",
]
