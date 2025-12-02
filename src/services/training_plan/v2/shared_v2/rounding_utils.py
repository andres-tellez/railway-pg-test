"""
Centralized rounding utilities for training plan generation.

This module provides consistent rounding functions used throughout
the plan generation pipeline.
"""


def round_to_half_mile(value: float) -> float:
    """
    Round to nearest 0.5 miles.

    Args:
        value: Distance in miles

    Returns:
        Rounded distance to nearest 0.5 miles

    Examples:
        >>> round_to_half_mile(8.3)
        8.5
        >>> round_to_half_mile(8.7)
        9.0
        >>> round_to_half_mile(8.0)
        8.0
    """
    return round(value * 2) / 2.0


def round_to_whole_mile(value: float) -> int:
    """
    Round to nearest whole mile.

    Args:
        value: Distance in miles

    Returns:
        Rounded distance to nearest whole mile

    Examples:
        >>> round_to_whole_mile(8.3)
        8
        >>> round_to_whole_mile(8.7)
        9
        >>> round_to_whole_mile(8.5)
        9
    """
    return int(round(value))
