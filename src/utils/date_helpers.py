"""
Date Helper Utilities
====================

Utilities for consistent date handling across the application,
especially for week-based metrics and comparisons.

Author: SmartCoach Development Team
Last Updated: October 14, 2025
"""

from datetime import datetime, date, timedelta
from typing import Union


def normalize_week_date(week_value: Union[str, datetime, date]) -> str:
    """
    Normalize week date to ISO format string (YYYY-MM-DD).

    Handles multiple input formats:
    - ISO string with time: "2025-10-13T00:00:00" -> "2025-10-13"
    - ISO string date only: "2025-10-13" -> "2025-10-13"
    - datetime object -> "2025-10-13"
    - date object -> "2025-10-13"

    Args:
        week_value: Week date in various formats

    Returns:
        Normalized ISO date string (YYYY-MM-DD)
    """
    if isinstance(week_value, str):
        # Handle ISO string with time component
        if "T" in week_value:
            return week_value.split("T")[0]
        # Handle ISO string date only (already normalized)
        return week_value

    if isinstance(week_value, datetime):
        return week_value.date().isoformat()

    if isinstance(week_value, date):
        return week_value.isoformat()

    # Fallback: convert to string
    return str(week_value)


def get_current_week_start() -> date:
    """
    Get the start date (Monday) of the current week.

    Returns:
        Date object for Monday of current week
    """
    today = datetime.now().date()
    days_since_monday = today.weekday()  # 0 = Monday, 6 = Sunday
    return today - timedelta(days=days_since_monday)


def get_week_start_for_date(target_date: Union[str, datetime, date]) -> date:
    """
    Get the start date (Monday) of the week containing the given date.

    Args:
        target_date: Date to find week start for

    Returns:
        Date object for Monday of that week
    """
    if isinstance(target_date, str):
        target_date = datetime.fromisoformat(target_date.split("T")[0]).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    days_since_monday = target_date.weekday()
    return target_date - timedelta(days=days_since_monday)


def compare_week_dates(
    week1: Union[str, datetime, date], week2: Union[str, datetime, date]
) -> bool:
    """
    Compare two week dates for equality, handling various formats.

    Args:
        week1: First week date
        week2: Second week date

    Returns:
        True if weeks are the same, False otherwise
    """
    norm1 = normalize_week_date(week1)
    norm2 = normalize_week_date(week2)
    return norm1 == norm2
