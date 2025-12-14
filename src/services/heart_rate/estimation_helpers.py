"""
Estimation Helper Utilities for Heart Rate Zone Services

Pure utility functions for age parsing and resting HR estimation.
These functions are shared across heart rate services to avoid duplication.

Following guardrails:
- Pure functions (no DB access, no side effects)
- No imports from other heart_rate services
- Constants imported from hr_zone_constants only
"""

import logging
from typing import Optional

from src.utils.hr_zone_constants import RESTING_HR_ESTIMATION

logger = logging.getLogger(__name__)


def parse_age_from_group(age_group: Optional[str]) -> Optional[int]:
    """
    Parse numeric age from age_group string.

    Handles formats:
    - "30-39" → 35 (midpoint)
    - "50+" → 50
    - "18-25" → 22 (midpoint)

    This centralizes age parsing logic used across the codebase.

    Args:
        age_group: Age group string like "30-39" or "50+"

    Returns:
        Numeric age (int) or None if cannot parse
    """
    if not age_group:
        return None

    try:
        age_str = str(age_group).strip()

        # Handle range format: "30-39"
        if "-" in age_str:
            age_range = age_str.split("-")
            if len(age_range) == 2:
                age_low = int(age_range[0])
                age_high = int(age_range[1])
                # Return midpoint
                return (age_low + age_high) // 2

        # Handle plus format: "50+" or "65+"
        if "+" in age_str:
            age_str = age_str.replace("+", "")
            return int(age_str)

        # Try parsing as single number
        return int(age_str)

    except (ValueError, IndexError, AttributeError) as e:
        logger.debug(f"Could not parse age from group '{age_group}': {e}")
        return None


def estimate_resting_hr_from_age(age: Optional[int]) -> Optional[int]:
    """
    Estimate resting heart rate from age using population averages.

    Uses age-based estimates from RESTING_HR_ESTIMATION constants.
    Returns None if age is invalid or out of range.

    Note: These are coarse population averages intended only to unblock
    zone setup. For best accuracy, users should measure their resting HR
    manually (first thing in the morning after waking).

    Args:
        age: Numeric age (int)

    Returns:
        Estimated resting HR (int) or None if age is invalid
    """
    if age is None or age < 18 or age > 100:
        return None

    age_estimates = RESTING_HR_ESTIMATION["AGE_ESTIMATES"]

    # Map age to age group range
    if 18 <= age <= 25:
        return age_estimates["18-25"]
    elif 26 <= age <= 35:
        return age_estimates["26-35"]
    elif 36 <= age <= 45:
        return age_estimates["36-45"]
    elif 46 <= age <= 55:
        return age_estimates["46-55"]
    elif 56 <= age <= 65:
        return age_estimates["56-65"]
    elif 66 <= age <= 75:
        return age_estimates["66-75"]
    elif age >= 76:
        return age_estimates["76+"]
    else:
        # Should not reach here, but fallback
        return RESTING_HR_ESTIMATION["DEFAULT_RESTING_HR"]


def estimate_resting_hr_from_age_group(age_group: Optional[str]) -> Optional[int]:
    """
    Estimate resting HR from age_group string.

    Convenience function that combines parse_age_from_group and estimate_resting_hr_from_age.

    Args:
        age_group: Age group string like "30-39"

    Returns:
        Estimated resting HR (int) or None if cannot parse/estimate
    """
    age = parse_age_from_group(age_group)
    if age is None:
        return None
    return estimate_resting_hr_from_age(age)
