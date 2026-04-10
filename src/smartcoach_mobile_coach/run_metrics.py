"""
Shared run distance and pace derivations for coach payloads.

Formatting strings live in display_format.py; this module holds numeric helpers only.
"""

from __future__ import annotations

from typing import Any, Optional

# Strava / activities store distance in meters; coach surfaces use statute miles.
METERS_TO_MILES = 0.000621371


def distance_miles_from_meters(meters: Any) -> float:
    """Convert activity/split distance in meters to miles; invalid → 0.0."""
    if meters is None:
        return 0.0
    try:
        return float(meters) * METERS_TO_MILES
    except (TypeError, ValueError):
        return 0.0


def pace_sec_per_mi(
    moving_time: Optional[int], distance_miles: float
) -> Optional[float]:
    """Average pace in seconds per mile; None if inputs are unusable."""
    if not moving_time or moving_time <= 0 or distance_miles <= 0:
        return None
    return float(moving_time) / distance_miles
