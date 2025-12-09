"""
Pace Validation Module

Validates input parameters and calculated pace seeds to ensure
data integrity and prevent invalid pace zones.
"""

import logging
from typing import Optional

from .models import PaceSeed
from .config import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


def validate_pace_seed(seed: PaceSeed) -> tuple[bool, Optional[str]]:
    """
    Validate pace seed values are reasonable and ordered correctly.

    Args:
        seed: PaceSeed to validate

    Returns:
        (is_valid, error_message)
        - is_valid: True if seed is valid
        - error_message: None if valid, error description if invalid
    """
    config = DEFAULT_CONFIG

    # Check all values are positive
    pace_values = [
        ("E_min", seed.E_min),
        ("E_max", seed.E_max),
        ("S_min", seed.S_min),
        ("S_max", seed.S_max),
        ("M", seed.M),
        ("T_min", seed.T_min),
        ("T_max", seed.T_max),
    ]

    for name, value in pace_values:
        if value <= 0:
            return (
                False,
                f"Invalid {name}: {value:.1f} (must be positive)",
            )

    # Check ranges are valid (min <= max)
    if seed.E_min > seed.E_max:
        return (
            False,
            f"Invalid Easy range: min ({seed.E_min:.1f}) > max ({seed.E_max:.1f})",
        )

    if seed.S_min > seed.S_max:
        return (
            False,
            f"Invalid Steady range: min ({seed.S_min:.1f}) > max ({seed.S_max:.1f})",
        )

    if seed.T_min > seed.T_max:
        return (
            False,
            f"Invalid Threshold range: min ({seed.T_min:.1f}) > max ({seed.T_max:.1f})",
        )

    # Check ordering: Threshold < Marathon < Steady < Easy
    if seed.T_max >= seed.M:
        return (
            False,
            f"Invalid ordering: Threshold max ({seed.T_max:.1f}) >= Marathon ({seed.M:.1f})",
        )

    if seed.M >= seed.S_min:
        return (
            False,
            f"Invalid ordering: Marathon ({seed.M:.1f}) >= Steady min ({seed.S_min:.1f})",
        )

    # Steady should overlap with Easy range (Steady can extend slightly faster)
    # But Steady max should be <= Easy max, and there should be overlap
    if seed.S_max > seed.E_max:
        return (
            False,
            f"Invalid ordering: Steady max ({seed.S_max:.1f}) > Easy max ({seed.E_max:.1f})",
        )
    if seed.S_min >= seed.E_max:
        return (
            False,
            f"Invalid ordering: Steady ({seed.S_min:.1f}-{seed.S_max:.1f}) "
            f"does not overlap with Easy range ({seed.E_min:.1f}-{seed.E_max:.1f})",
        )

    # Check reasonable bounds (4:00/mile to 20:00/mile)
    if seed.T_min < config.MIN_PACE_SEC_PER_MILE:
        return (
            False,
            f"Threshold min ({seed.T_min:.1f}s/mi) too fast "
            f"(minimum: {config.MIN_PACE_SEC_PER_MILE:.1f}s/mi = 6:00/mile)",
        )

    if seed.E_max > config.MAX_PACE_SEC_PER_MILE:
        return (
            False,
            f"Easy max ({seed.E_max:.1f}s/mi) too slow "
            f"(maximum: {config.MAX_PACE_SEC_PER_MILE:.1f}s/mi = 20:00/mile)",
        )

    # Check week1_long_cap is reasonable
    if seed.week1_long_cap < config.MIN_WEEK1_LONG_CAP:
        return (
            False,
            f"Week1 long cap ({seed.week1_long_cap:.1f} miles) below minimum "
            f"({config.MIN_WEEK1_LONG_CAP:.1f} miles)",
        )

    return (True, None)


def validate_input_parameters(
    user_id: Optional[str] = None,
    lookback_weeks: Optional[int] = None,
    min_distance_miles: Optional[float] = None,
    week1_long: Optional[float] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate input parameters for pace calculations.

    Args:
        user_id: User UUID string
        lookback_weeks: Number of weeks to look back
        min_distance_miles: Minimum distance for runs
        week1_long: Week 1 long run distance

    Returns:
        (is_valid, error_message)
    """
    config = DEFAULT_CONFIG

    if user_id is not None:
        if not isinstance(user_id, str):
            return (False, f"user_id must be a string, got {type(user_id)}")
        if not user_id.strip():
            return (False, "user_id cannot be empty")

    if lookback_weeks is not None:
        if not isinstance(lookback_weeks, int):
            return (
                False,
                f"lookback_weeks must be an integer, got {type(lookback_weeks)}",
            )
        if lookback_weeks <= 0:
            return (False, f"lookback_weeks must be positive, got {lookback_weeks}")
        if lookback_weeks > 52:
            return (False, f"lookback_weeks too large: {lookback_weeks} (max: 52)")

    if min_distance_miles is not None:
        if not isinstance(min_distance_miles, (int, float)):
            return (
                False,
                f"min_distance_miles must be a number, got {type(min_distance_miles)}",
            )
        if min_distance_miles <= 0:
            return (
                False,
                f"min_distance_miles must be positive, got {min_distance_miles}",
            )
        if min_distance_miles > 50:
            return (
                False,
                f"min_distance_miles too large: {min_distance_miles} (max: 50 miles)",
            )

    if week1_long is not None:
        if not isinstance(week1_long, (int, float)):
            return (
                False,
                f"week1_long must be a number, got {type(week1_long)}",
            )
        if week1_long < 0:
            return (False, f"week1_long cannot be negative, got {week1_long}")
        if week1_long > 30:
            return (
                False,
                f"week1_long too large: {week1_long} (max: 30 miles)",
            )

    return (True, None)
