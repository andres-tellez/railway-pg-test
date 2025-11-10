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


# ============================================================================
# DAY NAME CONSTANTS AND CONVERSION
# ============================================================================

# Standard day names (full format) - PRIMARY FORMAT for consistency
DAY_NAMES_FULL = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

# Abbreviated day names (for backward compatibility with API/database)
DAY_NAMES_ABBREV = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Mapping from any day name format to weekday number (0=Monday, 6=Sunday)
# Supports both full and abbreviated formats for backward compatibility
DAY_TO_WEEKDAY = {
    # Full names (primary)
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
    # Abbreviated names (for compatibility)
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}

# Default training days (abbreviated format for API compatibility)
DEFAULT_TRAINING_DAYS = ["Mon", "Wed", "Thu", "Sat"]


def date_to_day_name(d: Union[date, datetime]) -> str:
    """
    Convert date to standard day name (Monday, Tuesday, etc.).

    This is the PRIMARY conversion function - always returns full day names
    for consistency across the project.

    Args:
        d: Date or datetime object

    Returns:
        Full day name string (e.g., "Monday")
    """
    if isinstance(d, datetime):
        d = d.date()
    weekday = d.weekday()  # 0=Monday, 6=Sunday
    return DAY_NAMES_FULL[weekday]


def date_to_day_name_abbrev(d: Union[date, datetime]) -> str:
    """
    Convert date to abbreviated day name (Mon, Tue, etc.).

    Use this only when abbreviated format is required for API/database compatibility.

    Args:
        d: Date or datetime object

    Returns:
        Abbreviated day name string (e.g., "Mon")
    """
    if isinstance(d, datetime):
        d = d.date()
    weekday = d.weekday()
    return DAY_NAMES_ABBREV[weekday]


def day_name_to_weekday(day_name: str) -> int:
    """
    Convert day name (any format) to weekday number (0=Monday, 6=Sunday).

    Args:
        day_name: Day name in any format (Monday, Mon, etc.)

    Returns:
        Weekday number (0-6), defaults to 0 (Monday) if invalid
    """
    return DAY_TO_WEEKDAY.get(day_name, 0)


def normalize_day_name(day_name: str) -> str:
    """
    Normalize any day name format to standard full format.

    Args:
        day_name: Day name in any format (Mon, Monday, etc.)

    Returns:
        Standard full day name (e.g., "Monday"), or original if not recognized
    """
    weekday = day_name_to_weekday(day_name)
    if 0 <= weekday < len(DAY_NAMES_FULL):
        return DAY_NAMES_FULL[weekday]
    return day_name  # Return original if not recognized


def get_days_until_next_monday(
    target_date: Union[date, datetime] = None, include_today: bool = False
) -> int:
    """
    Calculate days until the next Monday from the target date.

    If target_date is Monday, returns 7 (next Monday is 7 days away).
    If target_date is Tuesday-Sunday, returns days until next Monday (1-6).

    Args:
        target_date: Date or datetime object (defaults to today if None)

    Returns:
        Number of days until next Monday (1-7)
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    days_until_monday = (7 - target_date.weekday()) % 7
    if days_until_monday == 0 and not include_today:
        days_until_monday = 7  # Today is Monday, next Monday is 7 days away
    elif days_until_monday == 0 and include_today:
        days_until_monday = 0
    return days_until_monday


def get_next_monday(
    target_date: Union[date, datetime] = None, include_today: bool = False
) -> date:
    """
    Get the date of the next Monday from the target date.

    If target_date is Monday, returns next Monday (7 days away).
    If target_date is Tuesday-Sunday, returns next Monday (1-6 days away).

    Args:
        target_date: Date or datetime object (defaults to today if None)

    Returns:
        Date object for next Monday
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    days = get_days_until_next_monday(target_date, include_today=include_today)
    return target_date + timedelta(days=days)


def get_previous_completed_week_range(
    target_date: Union[date, datetime] = None
) -> tuple[date, date]:
    """
    Get the date range (Monday to Sunday) for the current week that just completed.

    When scheduler runs on Sunday, the current week includes that Sunday and ends on that day.
    This function returns the week that just ended (Monday to Sunday, where Sunday is today).

    Example:
        If scheduler runs on Sunday Nov 3:
        - Current week that just completed: Monday Oct 27 to Sunday Nov 2
        - Returns: (Monday Oct 27, Sunday Nov 2)
        - Note: Nov 3 is the next week (starts Monday Nov 3)

    Args:
        target_date: Date or datetime object (defaults to today if None)
                     When scheduler runs, this is Sunday (the last day of the week)

    Returns:
        Tuple of (week_start, week_end) where both are date objects.
        week_start is Monday, week_end is Sunday of the current week that just completed.
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    # When scheduler runs on Sunday, the current week ends on the previous day (Saturday)
    # The week we want is Monday to Sunday, where Sunday is yesterday
    # Get yesterday (which is Saturday when scheduler runs on Sunday)
    yesterday = target_date - timedelta(days=1)

    # Get the week start (Monday) for the week containing yesterday
    # This gives us the Monday of the week that just completed
    week_start = get_week_start_for_date(yesterday)

    # Week end is Sunday (6 days after Monday)
    week_end = week_start + timedelta(days=6)

    return (week_start, week_end)
