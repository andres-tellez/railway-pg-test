"""
WeeklyActivitiesBuilder for Coach system.

Transforms raw activity records into structured weekly coaching data.
Pure transformation component - no database queries or side effects.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Any

from coach.data.activity_fetcher import ActivityRecord
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity


@dataclass
class WeeklyRunSummary:
    """Summary of a single run for weekly review."""

    date: date
    day: str  # "Monday", "Tuesday", etc.
    type: str  # "easy", "tempo", "long_run", "interval", "other"
    distance: float
    pace: Optional[str]  # "9:45/mile" format
    hr: Optional[int]
    evaluation: str  # "On target", "Too fast", "Too slow", "Missing HR", "Missing pace", "Missing data"
    plan_target: Optional[Dict[str, Any]] = None  # If available from plan


@dataclass
class LongRunSummary:
    """Summary of the week's long run."""

    distance: float
    pace: Optional[str]
    target_pace: Optional[str]  # Range like "9:45-10:15"
    evaluation: (
        str  # "On target", "Slightly fast", "Too fast", "Too slow", "Missing data"
    )


@dataclass
class WeeklyActivitiesSummary:
    """Structured weekly activities summary."""

    week_start: date
    week_end: date
    planned_miles: float
    completed_miles: float
    completion_rate: float  # 0.0 to 1.0
    run_count: int
    runs: List[WeeklyRunSummary]
    long_run: Optional[LongRunSummary]
    key_insights: List[str]


class WeeklyActivitiesBuilder:
    """
    Builds structured weekly activity summaries from raw activity records.

    Pure transformation - receives all inputs, no side effects.
    """

    DAY_NAMES = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    def build(
        self,
        activities: List[ActivityRecord],
        week_start: date,
        week_end: date,
        plan_for_week: Optional[Dict[str, Any]] = None,
        pace_zones: Optional[Dict[str, str]] = None,  # {"easy": "9:45-10:15", ...}
        hr_zones: Optional[Dict[str, str]] = None,  # {"z2": "135-150 bpm", ...}
    ) -> WeeklyActivitiesSummary:
        """
        Build structured weekly summary from activities.

        Args:
            activities: List of ActivityRecord for the week
            week_start: Monday of the week
            week_end: Sunday of the week
            plan_for_week: Optional plan data with planned workouts
            pace_zones: Optional pace zone ranges
            hr_zones: Optional HR zone ranges

        Returns:
            WeeklyActivitiesSummary with structured data
        """
        try:
            # Calculate totals
            completed_miles = sum(a.distance_miles or 0.0 for a in activities)
            run_count = len(activities)

            # Get planned miles if available
            planned_miles = 0.0
            if plan_for_week and "planned_miles" in plan_for_week:
                planned_miles = float(plan_for_week["planned_miles"])
            elif plan_for_week and "workouts" in plan_for_week:
                planned_miles = sum(
                    w.get("miles", 0.0) for w in plan_for_week["workouts"]
                )

            # Calculate completion rate
            completion_rate = (
                (completed_miles / planned_miles) if planned_miles > 0 else 0.0
            )

            # Build individual run summaries
            runs = []
            for activity in activities:
                run_summary = self._build_run_summary(
                    activity, pace_zones, hr_zones, plan_for_week
                )
                runs.append(run_summary)

            # Identify and summarize long run
            long_run = self._identify_long_run(activities, pace_zones)

            # Generate key insights
            insights = self._generate_insights(
                runs, long_run, completion_rate, planned_miles
            )

            return WeeklyActivitiesSummary(
                week_start=week_start,
                week_end=week_end,
                planned_miles=planned_miles,
                completed_miles=completed_miles,
                completion_rate=completion_rate,
                run_count=run_count,
                runs=runs,
                long_run=long_run,
                key_insights=insights,
            )

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="WeeklyActivitiesBuilder.build",
                metadata={
                    "week_start": str(week_start),
                    "week_end": str(week_end),
                    "activity_count": len(activities),
                },
            )
            # Return minimal fallback
            return WeeklyActivitiesSummary(
                week_start=week_start,
                week_end=week_end,
                planned_miles=0.0,
                completed_miles=0.0,
                completion_rate=0.0,
                run_count=0,
                runs=[],
                long_run=None,
                key_insights=["Unable to process weekly activities"],
            )

    def _build_run_summary(
        self,
        activity: ActivityRecord,
        pace_zones: Optional[Dict[str, str]],
        hr_zones: Optional[Dict[str, str]],
        plan_for_week: Optional[Dict[str, Any]],
    ) -> WeeklyRunSummary:
        """Build summary for a single run."""
        # Determine day of week
        day = self.DAY_NAMES[activity.date.weekday()]

        # Determine workout type
        workout_type = self._determine_workout_type(activity)

        # Format pace
        pace_str = activity.avg_pace_str

        # Build evaluation
        evaluation = self._evaluate_run(activity, pace_zones, hr_zones)

        # Find plan target if available
        plan_target = None
        if plan_for_week and "workouts" in plan_for_week:
            # Try to match by date
            for workout in plan_for_week["workouts"]:
                if workout.get("date") == activity.date.isoformat():
                    plan_target = workout
                    break

        return WeeklyRunSummary(
            date=activity.date,
            day=day,
            type=workout_type,
            distance=activity.distance_miles or 0.0,
            pace=pace_str,
            hr=activity.avg_hr,
            evaluation=evaluation,
            plan_target=plan_target,
        )

    def _determine_workout_type(self, activity: ActivityRecord) -> str:
        """Determine workout type from activity data."""
        if activity.workout_type:
            return activity.workout_type.lower()

        # Heuristic: long run if distance >= 8 miles
        if activity.distance_miles and activity.distance_miles >= 8.0:
            return "long_run"

        # Default to easy
        return "easy"

    def _evaluate_run(
        self,
        activity: ActivityRecord,
        pace_zones: Optional[Dict[str, str]],
        hr_zones: Optional[Dict[str, str]],
    ) -> str:
        """
        Evaluate run against target zones.

        Returns: "On target", "Too fast", "Too slow", "Missing HR", "Missing pace", "Missing data"
        """
        has_pace = activity.avg_pace_seconds_per_mile is not None
        has_hr = activity.avg_hr is not None

        if not has_pace and not has_hr:
            return "Missing data"

        if not has_pace:
            return "Missing pace"

        if not has_hr:
            return "Missing HR"

        # If we have zones, check against them
        if pace_zones and "easy" in pace_zones:
            pace_str = activity.avg_pace_str
            if pace_str:
                # Parse zone range (e.g., "9:45-10:15")
                zone_range = pace_zones["easy"]
                if self._is_pace_in_range(pace_str, zone_range):
                    return "On target"
                elif self._is_pace_faster_than_range(pace_str, zone_range):
                    return "Too fast"
                else:
                    return "Too slow"

        # If we have HR zones, check against them
        if hr_zones and "z2" in hr_zones and activity.avg_hr:
            hr_range = hr_zones["z2"]
            if self._is_hr_in_range(activity.avg_hr, hr_range):
                return "On target"
            elif activity.avg_hr > self._parse_hr_range_max(hr_range):
                return "Too fast"
            else:
                return "Too slow"

        # Default: assume on target if we have data
        return "On target"

    def _is_pace_in_range(self, pace_str: str, range_str: str) -> bool:
        """Check if pace is within range (e.g., "9:45" in "9:45-10:15")."""
        try:
            pace_sec = self._pace_str_to_seconds(pace_str)
            min_pace, max_pace = self._parse_pace_range(range_str)
            return min_pace <= pace_sec <= max_pace
        except (ValueError, AttributeError):
            return False

    def _is_pace_faster_than_range(self, pace_str: str, range_str: str) -> bool:
        """Check if pace is faster (lower seconds) than range minimum."""
        try:
            pace_sec = self._pace_str_to_seconds(pace_str)
            min_pace, _ = self._parse_pace_range(range_str)
            return pace_sec < min_pace
        except (ValueError, AttributeError):
            return False

    def _pace_str_to_seconds(self, pace_str: str) -> float:
        """Convert pace string "9:45" to seconds per mile."""
        parts = pace_str.replace("/mile", "").split(":")
        minutes = int(parts[0])
        seconds = int(parts[1]) if len(parts) > 1 else 0
        return minutes * 60 + seconds

    def _parse_pace_range(self, range_str: str) -> tuple:
        """Parse pace range "9:45-10:15" to (min_seconds, max_seconds)."""
        parts = range_str.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid pace range format: {range_str}")
        min_pace = self._pace_str_to_seconds(parts[0].strip())
        max_pace = self._pace_str_to_seconds(parts[1].strip())
        return (min_pace, max_pace)

    def _is_hr_in_range(self, hr: int, range_str: str) -> bool:
        """Check if HR is within range (e.g., 140 in "135-150 bpm")."""
        try:
            min_hr, max_hr = self._parse_hr_range(range_str)
            return min_hr <= hr <= max_hr
        except (ValueError, AttributeError):
            return False

    def _parse_hr_range(self, range_str: str) -> tuple:
        """Parse HR range "135-150 bpm" to (min_hr, max_hr)."""
        parts = range_str.replace("bpm", "").strip().split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid HR range format: {range_str}")
        return (int(parts[0].strip()), int(parts[1].strip()))

    def _parse_hr_range_max(self, range_str: str) -> int:
        """Get max HR from range."""
        _, max_hr = self._parse_hr_range(range_str)
        return max_hr

    def _identify_long_run(
        self,
        activities: List[ActivityRecord],
        pace_zones: Optional[Dict[str, str]],
    ) -> Optional[LongRunSummary]:
        """Identify and summarize the week's long run."""
        if not activities:
            return None

        # Find longest run
        long_run_activity = max(
            activities,
            key=lambda a: a.distance_miles or 0.0,
        )

        if (
            not long_run_activity.distance_miles
            or long_run_activity.distance_miles < 6.0
        ):
            # Not a significant long run
            return None

        pace_str = long_run_activity.avg_pace_str

        # Get target pace if available
        target_pace = None
        if pace_zones and "easy" in pace_zones:
            target_pace = pace_zones["easy"]

        # Evaluate
        evaluation = "On target"
        if pace_str and target_pace:
            if self._is_pace_faster_than_range(pace_str, target_pace):
                # Check how much faster
                pace_sec = self._pace_str_to_seconds(pace_str)
                min_pace, max_pace = self._parse_pace_range(target_pace)
                diff_pct = ((min_pace - pace_sec) / min_pace) * 100
                if diff_pct > 5:
                    evaluation = "Too fast"
                else:
                    evaluation = "Slightly fast"
            elif not self._is_pace_in_range(pace_str, target_pace):
                evaluation = "Too slow"
        elif not pace_str:
            evaluation = "Missing data"

        return LongRunSummary(
            distance=long_run_activity.distance_miles,
            pace=pace_str,
            target_pace=target_pace,
            evaluation=evaluation,
        )

    def _generate_insights(
        self,
        runs: List[WeeklyRunSummary],
        long_run: Optional[LongRunSummary],
        completion_rate: float,
        planned_miles: float,
    ) -> List[str]:
        """Generate key coaching insights."""
        insights = []

        # Completion rate insight
        if completion_rate >= 0.95:
            insights.append(
                f"Great consistency: {len(runs)} of {len(runs)} workouts completed"
            )
        elif completion_rate >= 0.8:
            insights.append(
                f"Good consistency: {len(runs)} workouts completed ({completion_rate:.0%} of plan)"
            )
        elif completion_rate < 0.8 and planned_miles > 0:
            insights.append(
                f"Missed workouts: only {completion_rate:.0%} of planned volume completed"
            )

        # Long run insight
        if long_run:
            if long_run.evaluation == "Too fast":
                insights.append(
                    f"Long run too fast ({long_run.pace} vs target {long_run.target_pace}) — keep it Zone 2 next week"
                )
            elif long_run.evaluation == "Slightly fast":
                insights.append(
                    f"Long run slightly fast — aim for {long_run.target_pace} next week"
                )

        # Evaluation insights
        fast_runs = [r for r in runs if r.evaluation == "Too fast"]
        if fast_runs:
            insights.append(
                f"{len(fast_runs)} run(s) were too fast — focus on easy pace for recovery"
            )

        return insights
