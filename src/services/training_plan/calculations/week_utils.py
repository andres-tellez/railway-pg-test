"""
Week calculation utilities for Layer 2.

Handles complete week calculations (Mon-Sun) for consistent analysis.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict


def get_last_complete_week_dates() -> Tuple[datetime, datetime]:
    """
    Get the start and end dates of the last complete Mon-Sun week.

    Returns:
        Tuple of (start_date, end_date) for last complete week

    Example:
        If today is Wednesday Oct 30, 2025:
        - Last complete week: Mon Oct 21 - Sun Oct 27
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Find the most recent Monday
    days_since_monday = today.weekday()  # 0 = Monday, 6 = Sunday

    # If today is Monday, we want last week's Monday
    # Otherwise, we want this week's Monday
    if days_since_monday == 0:
        # Today is Monday, go back to last Monday
        last_monday = today - timedelta(days=7)
    else:
        # Go back to this week's Monday, then back one more week
        last_monday = today - timedelta(days=days_since_monday + 7)

    # Last complete week is Monday to Sunday
    last_sunday = last_monday + timedelta(days=6)

    return last_monday, last_sunday


def get_complete_weeks(
    activities: List[Dict[str, Any]], max_weeks: int = 12
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group activities into complete Mon-Sun weeks.

    Args:
        activities: List of activity dictionaries
        max_weeks: Maximum number of weeks to analyze (default: 12)

    Returns:
        Dictionary mapping week_id (YYYY-Wxx) to list of activities
        Only includes COMPLETE weeks (Mon-Sun)

    Example:
        {
            "2025-W43": [activity1, activity2, ...],  # Oct 21-27
            "2025-W42": [activity3, activity4, ...],  # Oct 14-20
            ...
        }
    """
    if not activities:
        return {}

    # Get the last complete week boundary
    last_complete_monday, last_complete_sunday = get_last_complete_week_dates()

    # Group activities by ISO week
    weekly_data = defaultdict(list)

    for activity in activities:
        if not activity.get("date"):
            continue

        try:
            activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")

            # Only include activities up to the last complete week
            if activity_date > last_complete_sunday:
                continue

            # Get ISO week info
            iso_year, iso_week, iso_weekday = activity_date.isocalendar()
            week_id = f"{iso_year}-W{iso_week:02d}"

            weekly_data[week_id].append(activity)

        except (ValueError, TypeError):
            continue

    # Sort weeks by date (most recent first) and limit to max_weeks
    sorted_weeks = sorted(weekly_data.items(), reverse=True)[:max_weeks]

    return dict(sorted_weeks)


def calculate_week_mileage(week_activities: List[Dict[str, Any]]) -> float:
    """
    Calculate total mileage for a week's activities.

    Args:
        week_activities: List of activities for a single week

    Returns:
        Total mileage in miles
    """
    total = 0.0
    for activity in week_activities:
        distance = activity.get("distance", 0.0)
        if distance and distance > 0:
            total += distance
    return round(total, 1)


def get_week_date_range(week_id: str) -> Tuple[datetime, datetime]:
    """
    Get the date range for a week_id.

    Args:
        week_id: Week identifier in format "YYYY-Wxx"

    Returns:
        Tuple of (monday, sunday) for that week

    Example:
        "2025-W43" -> (Oct 21, Oct 27)
    """
    # Parse week_id
    year, week = week_id.split("-W")
    year = int(year)
    week = int(week)

    # Get the Monday of that week
    # ISO week 1 is the week with the first Thursday of the year
    jan_4 = datetime(year, 1, 4)
    week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
    target_monday = week_1_monday + timedelta(weeks=week - 1)
    target_sunday = target_monday + timedelta(days=6)

    return target_monday, target_sunday


def format_week_range(week_id: str) -> str:
    """
    Format a week_id into a human-readable date range.

    Args:
        week_id: Week identifier in format "YYYY-Wxx"

    Returns:
        Formatted string like "Oct 21-27, 2025"

    Example:
        "2025-W43" -> "Oct 21-27, 2025"
    """
    monday, sunday = get_week_date_range(week_id)

    # If same month
    if monday.month == sunday.month:
        return f"{monday.strftime('%b')} {monday.day}-{sunday.day}, {monday.year}"
    else:
        return f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d')}, {monday.year}"


def has_sufficient_data(
    weekly_data: Dict[str, List[Dict[str, Any]]], min_weeks: int = 4
) -> Tuple[bool, str]:
    """
    Check if there's sufficient data for analysis.

    Args:
        weekly_data: Dictionary of weekly activity data
        min_weeks: Minimum number of weeks required (default: 4)

    Returns:
        Tuple of (is_sufficient, message)

    Example:
        (True, "12 complete weeks available")
        (False, "Only 2 complete weeks - need at least 4 for reliable analysis")
    """
    num_weeks = len(weekly_data)

    if num_weeks >= min_weeks:
        return True, f"{num_weeks} complete weeks available"
    elif num_weeks > 0:
        return (
            False,
            f"Only {num_weeks} complete week(s) - need at least {min_weeks} for reliable analysis",
        )
    else:
        return False, "No complete weeks of training data available"
