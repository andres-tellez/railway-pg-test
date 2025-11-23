"""
Simple fitness calculation functions for Layer 2.

These are pure functions that perform straightforward calculations
on activity data without complex business logic.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from .week_utils import get_complete_weeks, calculate_week_mileage


def calculate_weekly_mileage(activities: List[Dict[str, Any]], weeks: int = 4) -> float:
    """
    Get average weekly mileage from the last N complete weeks.

    Uses the average of last 3-4 weeks to provide a more stable baseline
    that represents the user's current fitness level, rather than just
    one week which may be higher or lower than normal.

    This aligns with plan generation logic which looks at recent activity
    patterns over multiple weeks.

    Args:
        activities: List of activity dictionaries
        weeks: Number of complete weeks to analyze (default: 4)

    Returns:
        Average weekly mileage in miles over the last N complete weeks
    """
    if not activities:
        return 0.0

    # Get the last N complete weeks
    weekly_data = get_complete_weeks(activities, max_weeks=weeks)

    if not weekly_data:
        return 0.0

    # Calculate mileage for each week
    weekly_mileages = []
    for week_activities in weekly_data.values():
        week_mileage = calculate_week_mileage(week_activities)
        if week_mileage > 0:
            weekly_mileages.append(week_mileage)

    if not weekly_mileages:
        return 0.0

    # Return average of last N weeks
    return sum(weekly_mileages) / len(weekly_mileages)


def find_longest_run(activities: List[Dict[str, Any]], weeks: int = 4) -> float:
    """
    Find the longest run in the last N complete weeks.

    Uses last 3-4 weeks (default: 4) to align with plan generation logic
    which looks at recent activity patterns. This provides a more relevant
    "recent longest run" metric for establishing baseline fitness.

    Args:
        activities: List of activity dictionaries
        weeks: Number of complete weeks to analyze (default: 4)

    Returns:
        Longest run distance in miles from the last N weeks
    """
    if not activities:
        return 0.0

    # Get complete weeks
    weekly_data = get_complete_weeks(activities, max_weeks=weeks)

    if not weekly_data:
        return 0.0

    longest_distance = 0.0
    for week_activities in weekly_data.values():
        for activity in week_activities:
            distance = activity.get("distance", 0.0)
            if distance and distance > longest_distance:
                longest_distance = distance

    return round(longest_distance, 1)


def calculate_average_pace(activities: List[Dict[str, Any]], weeks: int = 12) -> str:
    """
    Calculate average pace from last N complete weeks.

    Args:
        activities: List of activity dictionaries
        weeks: Number of complete weeks to analyze (default: 12)

    Returns:
        Average pace as "MM:SS/mile" string
    """
    if not activities:
        return "0:00/mile"

    # Get complete weeks
    weekly_data = get_complete_weeks(activities, max_weeks=weeks)

    if not weekly_data:
        return "0:00/mile"

    total_time = 0
    total_distance = 0.0

    for week_activities in weekly_data.values():
        for activity in week_activities:
            distance = activity.get("distance", 0.0)
            moving_time = activity.get("moving_time", 0)

            if distance and distance > 0 and moving_time and moving_time > 0:
                total_time += moving_time
                total_distance += distance

    if total_distance == 0:
        return "0:00/mile"

    # Calculate pace in seconds per mile
    pace_seconds_per_mile = total_time / total_distance

    # Convert to minutes:seconds
    minutes = int(pace_seconds_per_mile // 60)
    seconds = int(pace_seconds_per_mile % 60)

    return f"{minutes}:{seconds:02d}/mile"


def calculate_fitness_trend(activities: List[Dict[str, Any]], weeks: int = 12) -> str:
    """
    Calculate fitness trend over the last N complete weeks.

    Args:
        activities: List of activity dictionaries
        weeks: Number of complete weeks to analyze (default: 12)

    Returns:
        Trend description: "Improving", "Declining", "Stable", "Insufficient Data"
    """
    if not activities:
        return "Insufficient Data"

    # Get complete weeks
    weekly_data = get_complete_weeks(activities, max_weeks=weeks)

    if len(weekly_data) < 4:
        return "Insufficient Data"

    # Calculate mileage for each week (sorted by date, most recent first)
    weekly_mileages = []
    for week_id in sorted(weekly_data.keys(), reverse=True):
        week_mileage = calculate_week_mileage(weekly_data[week_id])
        weekly_mileages.append(week_mileage)

    # Reverse to get oldest first
    weekly_mileages = list(reversed(weekly_mileages))

    if len(weekly_mileages) < 4:
        return "Insufficient Data"

    # Simple trend calculation: compare first half to second half
    mid_point = len(weekly_mileages) // 2
    first_half_avg = sum(weekly_mileages[:mid_point]) / mid_point
    second_half_avg = sum(weekly_mileages[mid_point:]) / len(
        weekly_mileages[mid_point:]
    )

    if first_half_avg == 0:
        return "Insufficient Data"

    change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100

    if change_percent > 10:
        return "Improving"
    elif change_percent < -10:
        return "Declining"
    else:
        return "Stable"
