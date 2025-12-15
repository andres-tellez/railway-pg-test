"""
ProgressReviewContextBuilder for Coach system.

Orchestrates building context for "last week" training review questions.
"""

from datetime import date
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from coach.data.activity_fetcher import ActivityFetcher
from coach.builders.weekly_activities_builder import WeeklyActivitiesBuilder
from coach.utils.date_utils import get_last_week_range
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity
from src.db.dao.plans_dao import get_active_plan
from src.db.models.plan_workouts import PlanWorkout
from src.utils.date_helpers import get_week_start_for_date


class ProgressReviewContextBuilder:
    """
    Builds context for progress review of last week's training.

    Orchestrates:
    - ActivityFetcher (fetch activities)
    - WeeklyActivitiesBuilder (transform to structured data)
    - Plan data (get planned workouts)
    - RunnerState zones (received as input)
    """

    def __init__(self, session: Session, user_id: str):
        """
        Initialize ProgressReviewContextBuilder.

        Args:
            session: SQLAlchemy database session
            user_id: User UUID string
        """
        self.session = session
        self.user_id = user_id
        self.activity_fetcher = ActivityFetcher(user_id, session)
        self.weekly_builder = WeeklyActivitiesBuilder()

    def build(
        self,
        pace_zones: Optional[Dict[str, str]] = None,
        hr_zones: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Build full context for last week's training review.

        Args:
            pace_zones: Optional pace zones from RunnerState (e.g., {"easy": "9:45-10:15"})
            hr_zones: Optional HR zones from RunnerState (e.g., {"z2": "135-150 bpm"})

        Returns:
            Dictionary with structured weekly review context
        """
        try:
            # Determine last week range (Monday-Sunday)
            today = date.today()
            last_week_start, last_week_end = get_last_week_range(today)

            # Fetch activities for last week
            activities = self.activity_fetcher.fetch_week(
                last_week_start, last_week_end
            )

            # Get plan data for last week
            plan_data = self._get_plan_for_week(last_week_start, last_week_end)

            # Build weekly summary
            weekly_summary = self.weekly_builder.build(
                activities=activities,
                week_start=last_week_start,
                week_end=last_week_end,
                plan_for_week=plan_data,
                pace_zones=pace_zones,
                hr_zones=hr_zones,
            )

            # Format as context dictionary
            context = {
                "intent": "progress_review_last_week",
                "week": {
                    "start": last_week_start.isoformat(),
                    "end": last_week_end.isoformat(),
                },
                "plan_miles": weekly_summary.planned_miles,
                "actual_miles": weekly_summary.completed_miles,
                "completion_rate": weekly_summary.completion_rate,
                "run_count": weekly_summary.run_count,
                "runs": [
                    {
                        "date": run.date.isoformat(),
                        "day": run.day,
                        "type": run.type,
                        "distance": run.distance,
                        "pace": run.pace,
                        "hr": run.hr,
                        "evaluation": run.evaluation,
                    }
                    for run in weekly_summary.runs
                ],
                "long_run": (
                    {
                        "distance": weekly_summary.long_run.distance,
                        "pace": weekly_summary.long_run.pace,
                        "target_pace": weekly_summary.long_run.target_pace,
                        "evaluation": weekly_summary.long_run.evaluation,
                    }
                    if weekly_summary.long_run
                    else None
                ),
                "key_insights": weekly_summary.key_insights,
            }

            return context

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.HIGH,
                component="ProgressReviewContextBuilder.build",
                user_id=self.user_id,
            )
            # Return minimal fallback
            return {
                "intent": "progress_review_last_week",
                "week": {
                    "start": "",
                    "end": "",
                },
                "plan_miles": 0.0,
                "actual_miles": 0.0,
                "completion_rate": 0.0,
                "run_count": 0,
                "runs": [],
                "long_run": None,
                "key_insights": ["Unable to retrieve last week's training data"],
            }

    def _get_plan_for_week(
        self, week_start: date, week_end: date
    ) -> Optional[Dict[str, Any]]:
        """
        Get planned workouts for the specified week.

        Args:
            week_start: Monday of the week
            week_end: Sunday of the week

        Returns:
            Dictionary with plan data, or None if no active plan
        """
        try:
            plan = get_active_plan(self.session, self.user_id)
            if not plan:
                return None

            # Get workouts for this week
            workouts = (
                self.session.query(PlanWorkout)
                .filter_by(plan_id=plan.id)
                .filter(PlanWorkout.date >= week_start)
                .filter(PlanWorkout.date <= week_end)
                .order_by(PlanWorkout.date)
                .all()
            )

            if not workouts:
                return None

            # Format workouts
            workout_list = []
            total_planned_miles = 0.0

            for workout in workouts:
                miles = float(workout.miles) if workout.miles else 0.0
                total_planned_miles += miles

                workout_dict = {
                    "date": workout.date.isoformat(),
                    "day": workout.date.strftime("%A"),
                    "type": workout.workout_type or "easy",
                    "miles": miles,
                }

                if workout.target_zone:
                    workout_dict["pace"] = workout.target_zone

                if workout.description:
                    workout_dict["details"] = workout.description[:200]

                workout_list.append(workout_dict)

            return {
                "planned_miles": total_planned_miles,
                "workouts": workout_list,
            }

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="ProgressReviewContextBuilder._get_plan_for_week",
                user_id=self.user_id,
                metadata={
                    "week_start": str(week_start),
                    "week_end": str(week_end),
                },
            )
            return None
