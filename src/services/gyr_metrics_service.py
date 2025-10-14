"""
GYR (Green/Yellow/Red) Metrics Service
======================================

This service calculates Green/Yellow/Red status scores for training metrics.
Leverages existing metrics infrastructure (materialized views, caching) for performance.

GYR Logic:
---------
1. Total Runs: Compare actual runs vs planned runs from training plan
   - Green: 90-110% of plan OR 4-6 runs if no plan
   - Yellow: 70-90% or 110-130% of plan
   - Red: <70% or >130% of plan

2. Weekly Pace: Compare current pace to 3-week rolling average
   - Green: Same or faster than avg
   - Yellow: Up to 10s/mi slower
   - Red: >10s/mi slower

3. Weekly HR Zones: Check 80/20 training adherence (Z1-Z2 time)
   - Green: 75-85% of time in Z1-Z2
   - Yellow: 65-75% or 85-90%
   - Red: <65% or >90%

Author: SmartCoach Development Team
Last Updated: October 14, 2025
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from src.utils.logger import get_logger
from src.utils.date_helpers import normalize_week_date, get_current_week_start

logger = get_logger(__name__)


class GYRMetricsService:
    """Service for calculating GYR (Green/Yellow/Red) metric scores"""

    @staticmethod
    def calculate_gyr_scores(
        session: Session, athlete_id: int, user_id: str, weeks: int = 8
    ) -> Dict:
        """
        Calculate GYR scores for all metrics using existing metrics infrastructure.

        Args:
            session: SQLAlchemy session
            athlete_id: Strava athlete ID
            user_id: Internal user ID (for training plan lookup)
            weeks: Number of weeks to calculate scores for (default: 8)

        Returns:
            Dictionary with GYR scores for each metric type
        """
        # Import here to avoid circular import
        from src.routes.metrics_routes import get_all_metrics_ultra_optimized

        metrics_data = get_all_metrics_ultra_optimized(
            session, athlete_id, user_id=user_id, weeks=weeks
        )

        # Calculate GYR scores for each metric type
        total_runs_scores = GYRMetricsService._calculate_total_runs_gyr(
            metrics_data, weeks
        )

        weekly_pace_scores = GYRMetricsService._calculate_weekly_pace_gyr(
            metrics_data, weeks
        )

        weekly_hr_zones_scores = GYRMetricsService._calculate_hr_zones_gyr(
            metrics_data, weeks
        )

        return {
            "totalRuns": {
                "historicalScores": total_runs_scores,
                "criteria": {
                    "green": "90–110% of planned miles",
                    "yellow": "70–90% or 110–130% of plan",
                    "red": "<70% or >130% of plan",
                },
            },
            "weeklyPace": {
                "historicalScores": weekly_pace_scores,
                "criteria": {
                    "green": "Same or faster",
                    "yellow": "Up to 10s/mi slower",
                    "red": ">10s/mi slower",
                },
            },
            "weeklyHRZones": {
                "historicalScores": weekly_hr_zones_scores,
                "criteria": {
                    "green": "75–85% easy runs (perfect 80/20)",
                    "yellow": "65–75% or 85–90% easy runs",
                    "red": "<65% or >90% easy runs",
                },
            },
        }

    @staticmethod
    def _calculate_total_runs_gyr(metrics_data: Dict, weeks: int) -> List[Dict]:
        """
        Calculate GYR status for total runs (actual vs planned).

        Logic:
        - Green: 90-110% of planned runs
        - Yellow: 70-90% or 110-130% of planned runs
        - Red: <70% or >130% of planned runs
        - Gray: No data for that week
        """
        weekly_trends = metrics_data.get("weekly_trends", [])
        weekly_goals = metrics_data.get("weekly_goals", [])

        # Create goal lookup by week (normalize all date formats)
        goals_by_week = {}
        for goal in weekly_goals:
            week_key = normalize_week_date(goal.get("week", ""))
            goals_by_week[week_key] = goal.get("goal_miles", 0)

        scores = []
        for i, trend in enumerate(weekly_trends[:weeks]):  # Limit to requested weeks
            week = trend.get("week", "")
            week_normalized = normalize_week_date(week)

            actual_runs = trend.get("runs", 0)
            actual_miles = trend.get("distance", 0)  # Get actual miles run

            # Only the first (most recent) week should have GYR status
            if i == 0:  # First week (previous week - leftmost bar)
                # Get planned miles from training plan for this week
                planned_miles = goals_by_week.get(week_normalized, 0)

                # Calculate percentage of plan completion (miles vs miles)
                if planned_miles > 0:
                    completion_pct = (actual_miles / planned_miles) * 100
                else:
                    completion_pct = 0

                # Determine status based on plan completion
                if actual_miles == 0:
                    status = "gray"
                elif 90 <= completion_pct <= 110:
                    status = "green"
                elif (70 <= completion_pct < 90) or (110 < completion_pct <= 130):
                    status = "yellow"
                else:
                    status = "red"
            else:
                # All other weeks (historical) should be gray
                status = "gray"
                completion_pct = 0
                planned_miles = 0

            scores.append(
                {
                    "value": round(completion_pct, 1),
                    "date": week_normalized,  # Use normalized date for consistency
                    "status": status,
                    "actual_runs": actual_runs,
                    "actual_miles": round(actual_miles, 1),
                    "planned_miles": round(planned_miles, 1) if i == 0 else 0,
                }
            )

        return scores

    @staticmethod
    def _calculate_weekly_pace_gyr(metrics_data: Dict, weeks: int) -> List[Dict]:
        """
        Calculate GYR status for weekly pace (vs 3-week rolling average).

        Logic:
        - Green: Same or faster than 3-week avg
        - Yellow: Up to 10s/mi slower
        - Red: >10s/mi slower
        - Gray: No data for that week
        """
        from src.routes.metrics_routes import format_pace

        weekly_trends = metrics_data.get("weekly_trends", [])

        scores = []

        # Calculate rolling 3-week average for each week
        for i, trend in enumerate(weekly_trends[:weeks]):
            week = trend.get("week", "")
            week_normalized = normalize_week_date(week)
            current_pace_str = trend.get("avgPace", "0:00")
            distance = trend.get("distance", 0)

            # Skip if no data
            if distance == 0 or current_pace_str == "0:00":
                scores.append({"value": 0, "date": week_normalized, "status": "gray"})
                continue

            # Convert pace string to seconds per mile
            current_pace_seconds = GYRMetricsService._pace_to_seconds(current_pace_str)

            # Calculate 3-week rolling average (weeks i+1, i+2, i+3 - previous weeks)
            rolling_avg_seconds = None
            if i < len(weekly_trends) - 3:
                prev_paces = []
                for j in range(i + 1, min(i + 4, len(weekly_trends))):
                    prev_pace_str = weekly_trends[j].get("avgPace", "0:00")
                    prev_distance = weekly_trends[j].get("distance", 0)
                    if prev_distance > 0 and prev_pace_str != "0:00":
                        prev_paces.append(
                            GYRMetricsService._pace_to_seconds(prev_pace_str)
                        )

                if prev_paces:
                    rolling_avg_seconds = sum(prev_paces) / len(prev_paces)

            # Determine status
            if rolling_avg_seconds is None:
                # Not enough history, default to green if running
                status = "green"
                value = 100
            else:
                # Calculate difference in seconds
                pace_diff = current_pace_seconds - rolling_avg_seconds

                if pace_diff <= 0:
                    # Same or faster
                    status = "green"
                    value = 100
                elif pace_diff <= 10:
                    # Up to 10s/mi slower
                    status = "yellow"
                    value = 75
                else:
                    # >10s/mi slower
                    status = "red"
                    value = 50

            scores.append(
                {
                    "value": value,
                    "date": week_normalized,
                    "status": status,
                    "current_pace": current_pace_str,
                    "avg_pace": (
                        format_pace(1609.34 / rolling_avg_seconds)
                        if rolling_avg_seconds
                        else None
                    ),
                }
            )

        return scores

    @staticmethod
    def _calculate_hr_zones_gyr(metrics_data: Dict, weeks: int) -> List[Dict]:
        """
        Calculate GYR status for HR zones (80/20 training adherence).

        Logic:
        - Green: 75-85% of time in Z1-Z2 (80/20 adherence)
        - Yellow: 65-75% or 85-90%
        - Red: <65% or >90%
        - Gray: No HR data for that week
        """
        weekly_hr_zones = metrics_data.get("weekly_hr_zones", [])

        scores = []

        for hr_week in weekly_hr_zones[:weeks]:
            week = hr_week.get("week", "")
            week_normalized = normalize_week_date(week)
            zone_1 = hr_week.get("zone_1", 0)
            zone_2 = hr_week.get("zone_2", 0)

            # Calculate Z1-Z2 percentage (easy aerobic)
            z1_z2_pct = zone_1 + zone_2

            # Determine status
            if z1_z2_pct == 0:
                status = "gray"
                value = 0
            elif 75 <= z1_z2_pct <= 85:
                status = "green"
                value = 90
            elif (65 <= z1_z2_pct < 75) or (85 < z1_z2_pct <= 90):
                status = "yellow"
                value = 70
            else:
                status = "red"
                value = 50

            scores.append(
                {
                    "value": round(z1_z2_pct, 1),
                    "date": week_normalized,
                    "status": status,
                    "z1_z2_pct": round(z1_z2_pct, 1),
                }
            )

        return scores

    @staticmethod
    def _pace_to_seconds(pace_str: str) -> float:
        """
        Convert pace string (MM:SS) to seconds per mile.

        Args:
            pace_str: Pace string like "8:45"

        Returns:
            Total seconds per mile
        """
        try:
            parts = pace_str.split(":")
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0
