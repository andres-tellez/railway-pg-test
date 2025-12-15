"""
Date utilities for Coach system.

Provides week boundary helpers following ISO-8601 standard (Monday-Sunday).
"""

from datetime import date, timedelta
from typing import Tuple


def get_week_start(week_date: date) -> date:
    """
    Get the Monday of the week containing the given date.

    Following ISO-8601 standard: Monday is the first day of the week.

    Args:
        week_date: Any date in the week

    Returns:
        The Monday of that week
    """
    # weekday() returns 0=Monday, 6=Sunday
    # So we subtract the weekday to get Monday
    days_since_monday = week_date.weekday()
    return week_date - timedelta(days=days_since_monday)


def get_week_end(week_start: date) -> date:
    """
    Get the Sunday of the week starting with the given Monday.

    Args:
        week_start: Monday of the week

    Returns:
        The Sunday of that week (week_start + 6 days)
    """
    return week_start + timedelta(days=6)


def get_last_week_range(today: date) -> Tuple[date, date]:
    """
    Get the date range for the previous completed week (Monday-Sunday).

    If today is Monday, returns the week that ended yesterday (Sunday).
    If today is any other day, returns the most recent Monday-Sunday week.

    Args:
        today: Current date

    Returns:
        Tuple of (last_week_start, last_week_end) where:
        - last_week_start: Monday of last week
        - last_week_end: Sunday of last week
    """
    current_week_start = get_week_start(today)

    # If today is Monday, last week ended yesterday (Sunday)
    # Otherwise, last week is the week before current week
    if today.weekday() == 0:  # Monday
        last_week_end = today - timedelta(days=1)  # Yesterday (Sunday)
        last_week_start = get_week_start(last_week_end)
    else:
        # Last week is the week before current week
        last_week_start = current_week_start - timedelta(days=7)
        last_week_end = get_week_end(last_week_start)

    return last_week_start, last_week_end
