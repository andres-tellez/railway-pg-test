"""
Centralized rounding utilities for training plan generation.

This module provides consistent rounding functions used throughout
the plan generation pipeline. All functions work with distances in miles
internally. All rounding happens in miles for consistency - frontend handles
unit conversion for display using toDisplayDistance().
"""

# Conversion constants
MI_TO_KM = 1.609344
KM_TO_MI = 1 / MI_TO_KM


def miles_to_km(miles: float) -> float:
    """
    Convert miles to kilometers.

    Args:
        miles: Distance in miles

    Returns:
        Distance in kilometers

    Example:
        >>> miles_to_km(5.0)
        8.04672
    """
    return miles * MI_TO_KM


def km_to_miles(km: float) -> float:
    """
    Convert kilometers to miles.

    Args:
        km: Distance in kilometers

    Returns:
        Distance in miles

    Example:
        >>> km_to_miles(8.0)
        4.970969537898671
    """
    return km * KM_TO_MI


def round_to_half_mile(value: float, unit_system: str = "imperial") -> float:
    """
    Round to nearest 0.5 miles.

    CRITICAL: unit_system parameter is deprecated and ignored.
    All rounding now happens in miles for internal consistency.
    Frontend handles unit conversion for display using toDisplayDistance().

    Args:
        value: Distance in miles (internal representation)
        unit_system: Deprecated - kept for backward compatibility, ignored

    Returns:
        Rounded distance in miles (always rounded to 0.5 mile increments)

    Examples:
        >>> round_to_half_mile(8.3)
        8.5
        >>> round_to_half_mile(8.7)
        9.0
    """
    # Always round to 0.5 miles (unit_system parameter ignored for consistency)
    return round(value * 2) / 2.0


def round_to_whole_mile(
    value: float, unit_system: str = "imperial"
) -> int:  # unit_system deprecated
    """
    Round to nearest whole mile.

    CRITICAL: unit_system parameter is deprecated and ignored.
    All rounding now happens in miles for internal consistency.
    Frontend handles unit conversion for display using toDisplayDistance().

    Args:
        value: Distance in miles (internal representation)
        unit_system: Deprecated - kept for backward compatibility, ignored

    Returns:
        Rounded distance in whole miles

    Examples:
        >>> round_to_whole_mile(8.3)
        8
        >>> round_to_whole_mile(8.7)
        9
    """
    # Always round to whole miles (unit_system parameter ignored for consistency)
    return int(round(value))


def round_workout_distance(value: float, unit_system: str = "imperial") -> float:
    """
    Round individual workout distance to practical increments (0.5 miles).

    CRITICAL: unit_system parameter is deprecated and ignored.
    All rounding now happens in miles for internal consistency.
    Frontend handles unit conversion for display using toDisplayDistance().

    Args:
        value: Distance in miles (internal representation)
        unit_system: Deprecated - kept for backward compatibility, ignored

    Returns:
        Rounded distance in miles (always rounded to 0.5 mile increments)

    Examples:
        >>> round_workout_distance(6.3)  # Rounds to 6.5 miles
        6.5
        >>> round_workout_distance(5.0)  # 5.0 mi, rounds to 5.0 mi
        5.0
    """
    # Always round to 0.5 miles (unit_system parameter ignored for consistency)
    return round(value * 2) / 2.0
