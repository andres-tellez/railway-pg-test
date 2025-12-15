"""
Activity Summarizer for Coach system.

Summarizes activity data into compact, GPT-friendly formats.
Extracts key metrics, patterns, and recent performance indicators.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from coach.utils.config import Config
from coach.utils.constants import (
    DEFAULT_LAST_7_DAYS,
    DEFAULT_LONG_RUNS_LIMIT,
    DEFAULT_WEEKS_FOR_AGGREGATES,
)


@dataclass
class Last7DaysSummary:
    """Summary of last 7 days of activities."""

    total_miles: float
    activity_count: int
    average_pace_seconds_per_mile: Optional[float] = None
    average_heartrate: Optional[float] = None


@dataclass
class WeeklyAggregate:
    """Weekly aggregate metrics."""

    week_start_date: str  # ISO format date
    total_miles: float
    activity_count: int
    average_pace_seconds_per_mile: Optional[float] = None


@dataclass
class ActivitySummary:
    """Complete activity summary."""

    last_7_days_summary: Last7DaysSummary
    last_3_long_runs: List[Dict] = field(default_factory=list)
    weekly_aggregates: List[WeeklyAggregate] = field(default_factory=list)


class ActivitySummarizer:
    """
    Summarizes activities into compact formats for GPT context.

    Focuses on:
    - Recent activity (last 7 days)
    - Key workouts (long runs, tempo runs)
    - Weekly aggregates for pattern analysis

    Configuration loaded from config/thresholds.yaml for thresholds.
    """

    def __init__(self):
        """Initialize with configuration from config file."""
        self.long_run_distance_threshold = Config.get_thresholds(
            "long_run_distance_threshold", 8.0  # Default fallback
        )

    def summarize(self, activities: List[Dict]) -> ActivitySummary:
        """
        Summarize activities into compact format.

        Args:
            activities: List of activity dictionaries with at minimum:
                - date (ISO format string or date object)
                - distance_miles (float)
                Optional fields:
                - pace_seconds_per_mile (float)
                - average_heartrate (float)
                - workout_type (str)
                - other fields as available

        Returns:
            ActivitySummary with last 7 days, long runs, and weekly aggregates
        """
        if not activities:
            return self._empty_summary()

        # Filter to valid activities (have date and distance)
        valid_activities = [act for act in activities if self._is_valid_activity(act)]

        if not valid_activities:
            return self._empty_summary()

        # Parse dates and sort by date (most recent first)
        for act in valid_activities:
            if isinstance(act["date"], str):
                act["_parsed_date"] = date.fromisoformat(act["date"])
            else:
                act["_parsed_date"] = act["date"]

        valid_activities.sort(key=lambda x: x["_parsed_date"], reverse=True)

        # Calculate last 7 days summary
        last_7_days_summary = self._calculate_last_7_days(valid_activities)

        # Extract last N long runs
        last_3_long_runs = self._extract_long_runs(
            valid_activities, limit=DEFAULT_LONG_RUNS_LIMIT
        )

        # Calculate weekly aggregates
        weekly_aggregates = self._calculate_weekly_aggregates(
            valid_activities, weeks=DEFAULT_WEEKS_FOR_AGGREGATES
        )

        return ActivitySummary(
            last_7_days_summary=last_7_days_summary,
            last_3_long_runs=last_3_long_runs,
            weekly_aggregates=weekly_aggregates,
        )

    def _is_valid_activity(self, activity: Dict) -> bool:
        """Check if activity has minimum required fields."""
        return (
            "date" in activity
            and "distance_miles" in activity
            and activity.get("distance_miles") is not None
        )

    def _empty_summary(self) -> ActivitySummary:
        """Return empty summary for no activities."""
        return ActivitySummary(
            last_7_days_summary=Last7DaysSummary(
                total_miles=0.0,
                activity_count=0,
            ),
            last_3_long_runs=[],
            weekly_aggregates=[],
        )

    def _calculate_last_7_days(self, activities: List[Dict]) -> Last7DaysSummary:
        """Calculate summary for last N days (default 7)."""
        today = date.today()
        seven_days_ago = today - timedelta(days=DEFAULT_LAST_7_DAYS)

        last_7_days = [
            act
            for act in activities
            if act["_parsed_date"] >= seven_days_ago and act["_parsed_date"] <= today
        ]

        if not last_7_days:
            return Last7DaysSummary(
                total_miles=0.0,
                activity_count=0,
            )

        total_miles = sum(act.get("distance_miles", 0.0) for act in last_7_days)
        activity_count = len(last_7_days)

        # Calculate average pace if available
        paces = [
            act.get("pace_seconds_per_mile")
            for act in last_7_days
            if act.get("pace_seconds_per_mile") is not None
        ]
        average_pace = self._calculate_average(paces)

        # Calculate average HR if available
        heartrates = [
            act.get("average_heartrate")
            for act in last_7_days
            if act.get("average_heartrate") is not None
        ]
        average_hr = self._calculate_average(heartrates)

        return Last7DaysSummary(
            total_miles=total_miles,
            activity_count=activity_count,
            average_pace_seconds_per_mile=average_pace,
            average_heartrate=average_hr,
        )

    def _extract_long_runs(self, activities: List[Dict], limit: int = 3) -> List[Dict]:
        """Extract last N long runs."""
        long_runs = []

        for act in activities:
            # Check if it's a long run
            distance = act.get("distance_miles", 0.0)
            workout_type = (
                act.get("workout_type", "").lower() if act.get("workout_type") else ""
            )

            is_long_run = distance > self.long_run_distance_threshold or (
                distance >= self.long_run_distance_threshold and "long" in workout_type
            )

            if is_long_run:
                # Create summary dict (don't include internal fields)
                summary = {
                    "date": (
                        act["date"]
                        if isinstance(act["date"], str)
                        else act["date"].isoformat()
                    ),
                    "distance_miles": distance,
                }

                if act.get("pace_seconds_per_mile") is not None:
                    summary["pace_seconds_per_mile"] = act["pace_seconds_per_mile"]

                if act.get("average_heartrate") is not None:
                    summary["average_heartrate"] = act["average_heartrate"]

                if act.get("workout_type"):
                    summary["workout_type"] = act["workout_type"]

                long_runs.append(summary)

                if len(long_runs) >= limit:
                    break

        return long_runs

    def _calculate_weekly_aggregates(
        self, activities: List[Dict], weeks: int = 4
    ) -> List[WeeklyAggregate]:
        """Calculate weekly aggregates for last N weeks."""
        if not activities:
            return []

        # Group activities by week (Monday to Sunday)
        weekly_groups: Dict[date, List[Dict]] = {}

        for act in activities:
            act_date = act["_parsed_date"]
            # Get Monday of the week
            days_since_monday = act_date.weekday()
            week_start = act_date - timedelta(days=days_since_monday)

            if week_start not in weekly_groups:
                weekly_groups[week_start] = []
            weekly_groups[week_start].append(act)

        # Sort weeks (most recent first) and limit to N weeks
        sorted_weeks = sorted(weekly_groups.keys(), reverse=True)[:weeks]

        aggregates = []
        for week_start in sorted_weeks:
            week_activities = weekly_groups[week_start]

            total_miles = sum(act.get("distance_miles", 0.0) for act in week_activities)
            activity_count = len(week_activities)

            # Calculate average pace if available
            paces = [
                act.get("pace_seconds_per_mile")
                for act in week_activities
                if act.get("pace_seconds_per_mile") is not None
            ]
            average_pace = self._calculate_average(paces)

            aggregates.append(
                WeeklyAggregate(
                    week_start_date=week_start.isoformat(),
                    total_miles=total_miles,
                    activity_count=activity_count,
                    average_pace_seconds_per_mile=average_pace,
                )
            )

        return aggregates

    def _calculate_average(self, values: List[float]) -> Optional[float]:
        """
        Calculate average of values.

        Args:
            values: List of numeric values (may contain None, which are filtered out)

        Returns:
            Average value, or None if no valid values
        """
        valid_values = [v for v in values if v is not None]
        return sum(valid_values) / len(valid_values) if valid_values else None
