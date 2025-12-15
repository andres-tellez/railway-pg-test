"""
QuestionContextBuilder for Coach system.

Builds intent-specific context for coaching questions by orchestrating
existing services based on classified intent.

This is an ORCHESTRATOR - it does NOT reimplement calculations.
It composes existing services based on intent.
"""

from typing import Dict, Optional, Any, List
from datetime import date, timedelta

from sqlalchemy.orm import Session

from coach.utils.intent_classifier import IntentClassifier, IntentClassificationResult
from coach.builders.runner_state_builder import RunnerStateBuilder
from coach.builders.activity_summarizer import ActivitySummarizer
from coach.builders.progress_review_context_builder import ProgressReviewContextBuilder
from coach.safety.safety_scanner import SafetyScanner
from coach.utils.schema_validator import SchemaValidator
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity

from src.services.smart_data_service import SmartDataService
from src.db.dao.plans_dao import get_active_plan


class QuestionContextBuilder:
    """
    Builds intent-specific context for coaching questions.

    Orchestrates:
    - IntentClassifier: Classifies user intent
    - RunnerStateBuilder: Provides runner state
    - ActivitySummarizer: Provides activity summaries
    - SafetyScanner: Provides safety flags
    - SmartDataService: Provides raw activity and plan data
    """

    def __init__(self, session: Session, user_id: str):
        """
        Initialize QuestionContextBuilder.

        Args:
            session: Database session
            user_id: User ID to build context for
        """
        self.session = session
        self.user_id = user_id
        self.intent_classifier = IntentClassifier()
        self.safety_scanner = SafetyScanner()
        self.activity_summarizer = ActivitySummarizer()

    def build(self, question: str) -> Dict[str, Any]:
        """
        Build intent-specific context for a user question.

        Args:
            question: User's question/message

        Returns:
            Dictionary matching QuestionContext schema
        """
        try:
            # 1. Classify intent
            classification = self.intent_classifier.classify(question)
            intent = classification.intent

            # 2. Scan for safety flags (always check)
            safety_flags = self.safety_scanner.scan_for_schema(question)

            # 3. Build base context
            base_context = {
                "intent": intent,
            }

            # 4. Build intent-specific context
            if intent == "workout_review":
                base_context["workout_review"] = self._build_workout_review_context(
                    question
                )
            elif intent == "this_week_plan":
                base_context["this_week_plan"] = self._build_this_week_plan_context()
            elif intent == "plan_adjustment_request":
                base_context["plan_adjustment_request"] = (
                    self._build_plan_adjustment_context()
                )
            elif intent == "progress_check":
                base_context["progress_check"] = self._build_progress_check_context()
            elif intent == "progress_review_last_week":
                # Get zones from RunnerState for weekly review
                runner_state_builder = RunnerStateBuilder(self.session, self.user_id)
                runner_state = runner_state_builder.build()
                zones = runner_state.get("runner_state", {}).get("zones", {})
                pace_zones = zones.get("pace", {})
                hr_zones = zones.get("hr", {})

                # Build weekly review context
                progress_builder = ProgressReviewContextBuilder(
                    self.session, self.user_id
                )
                weekly_context = progress_builder.build(
                    pace_zones=pace_zones,
                    hr_zones=hr_zones,
                )
                base_context["progress_review_last_week"] = weekly_context
            elif intent == "injury_or_symptom":
                base_context["injury_or_symptom"] = {
                    "safety_flags": safety_flags.get("safety_flags", {}).get(
                        "flags", []
                    )
                }
            elif intent == "general_education":
                # Minimal context for general education
                base_context["general_education"] = {}
            elif intent == "motivation_support":
                base_context["motivation_support"] = self._build_motivation_context()

            # 5. Build complete context
            result = {
                "version": "1.0.0",
                "question_context": base_context,
            }

            # 6. Validate against schema
            try:
                SchemaValidator.validate_question_context(result)
            except Exception as e:
                CoachErrorHandler.handle(
                    error=e,
                    severity=ErrorSeverity.MEDIUM,
                    component="QuestionContextBuilder.schema_validation",
                    user_id=self.user_id,
                )

            return result

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.HIGH,
                component="QuestionContextBuilder.build",
                user_id=self.user_id,
            )
            # Return minimal fallback context
            return {
                "version": "1.0.0",
                "question_context": {
                    "intent": "general_education",
                    "general_education": {},
                },
            }

    def _build_workout_review_context(self, question: str) -> Dict[str, Any]:
        """
        Build context for workout_review intent.

        Finds most recent activity and compares to plan targets.
        """
        try:
            # Get recent activities
            # NOTE: SmartDataService._get_recent_activities() doesn't accept weeks parameter
            # This is a temporary workaround until we fully migrate to ActivityFetcher
            data_service = SmartDataService(self.user_id)
            activities = data_service._get_recent_activities()

            if not activities:
                return {}

            # Get most recent activity
            most_recent = activities[0]

            # Get plan to find target workout
            plan = get_active_plan(self.session, self.user_id)
            plan_target = None

            if plan and most_recent.get("date"):
                plan_target = self._find_planned_workout_for_activity(
                    most_recent, plan.id
                )

            # Build activity context
            activity_context = {
                "date": most_recent.get("date"),
                "distance_miles": most_recent.get("distance_miles"),
            }

            if most_recent.get("pace_seconds_per_mile"):
                # Format pace
                pace_sec = most_recent["pace_seconds_per_mile"]
                minutes = int(pace_sec // 60)
                seconds = int(pace_sec % 60)
                activity_context["avg_pace"] = f"{minutes}:{seconds:02d}/mile"

            if most_recent.get("average_heartrate"):
                activity_context["avg_hr"] = int(most_recent["average_heartrate"])

            # Add zone distribution if available
            zone_dist = {}
            for zone in ["z1", "z2", "z3", "z4", "z5"]:
                zone_key = f"hr_zone{zone[1]}" if zone[1].isdigit() else zone
                if most_recent.get(zone_key):
                    zone_dist[zone] = f"{most_recent[zone_key]:.0f}%"

            if zone_dist:
                activity_context["zone_distribution"] = zone_dist

            # Add plan target and deviation if available
            if plan_target:
                activity_context["plan_target"] = plan_target
                activity_context["deviation"] = self._calculate_deviation(
                    most_recent, plan_target
                )

            # Determine workout type
            workout_type = "easy"
            if most_recent.get("distance_miles", 0) >= 8.0:
                workout_type = "long_run"
            elif most_recent.get("workout_type"):
                workout_type = most_recent["workout_type"].lower()

            return {
                "workout_type": workout_type,
                "activity": activity_context,
            }

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="QuestionContextBuilder._build_workout_review_context",
                user_id=self.user_id,
            )
            return {}

    def _build_this_week_plan_context(self) -> Dict[str, Any]:
        """
        Build context for this_week_plan intent.

        Gets current week's planned workouts.
        """
        try:
            plan = get_active_plan(self.session, self.user_id)
            if not plan or not plan.race_date:
                return {}

            # Calculate current week number
            today = date.today()
            days_until_race = (plan.race_date - today).days
            week_num = max(1, (days_until_race // 7) + 1)

            # Get workouts for this week
            from src.db.models.plan_workouts import PlanWorkout
            from src.utils.date_helpers import get_week_start_for_date

            week_start = plan.race_date - timedelta(weeks=week_num)
            week_start = get_week_start_for_date(week_start)
            week_end = week_start + timedelta(days=6)

            workouts = (
                self.session.query(PlanWorkout)
                .filter_by(plan_id=plan.id)
                .filter(PlanWorkout.date >= week_start)
                .filter(PlanWorkout.date <= week_end)
                .order_by(PlanWorkout.date)
                .all()
            )

            # Format workouts
            workout_list = []
            for workout in workouts:
                workout_dict = {
                    "day": workout.date.strftime("%A"),
                    "type": workout.workout_type,
                    "miles": float(workout.miles),
                }

                if workout.target_zone:
                    workout_dict["pace"] = workout.target_zone

                if workout.description:
                    workout_dict["details"] = workout.description[:200]  # Truncate

                workout_list.append(workout_dict)

            return {
                "current_week": {
                    "week_number": week_num,
                    "workouts": workout_list,
                }
            }

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="QuestionContextBuilder._build_this_week_plan_context",
                user_id=self.user_id,
            )
            return {}

    def _build_plan_adjustment_context(self) -> Dict[str, Any]:
        """Build context for plan_adjustment_request intent."""
        # For now, return empty - can be enhanced with current plan state
        return {}

    def _build_progress_check_context(self) -> Dict[str, Any]:
        """Build context for progress_check intent."""
        # Use ActivitySummarizer for recent performance summary
        try:
            # NOTE: SmartDataService._get_recent_activities() doesn't accept weeks parameter
            # This is a temporary workaround until we fully migrate to ActivityFetcher
            data_service = SmartDataService(self.user_id)
            activities = data_service._get_recent_activities()

            summary = self.activity_summarizer.summarize(activities)

            return {
                "recent_summary": {
                    "last_7_days": {
                        "total_miles": summary.last_7_days_summary.total_miles,
                        "activity_count": summary.last_7_days_summary.activity_count,
                    }
                }
            }

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="QuestionContextBuilder._build_progress_check_context",
                user_id=self.user_id,
            )
            return {}

    def _build_motivation_context(self) -> Dict[str, Any]:
        """Build context for motivation_support intent."""
        # Use recent performance data for motivation
        try:
            # NOTE: SmartDataService._get_recent_activities() doesn't accept weeks parameter
            # This is a temporary workaround until we fully migrate to ActivityFetcher
            data_service = SmartDataService(self.user_id)
            activities = data_service._get_recent_activities()

            if activities:
                total_miles = sum(a.get("distance_miles", 0) for a in activities)
                return {
                    "recent_mileage": total_miles,
                    "activity_count": len(activities),
                }

            return {}

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.LOW,
                component="QuestionContextBuilder._build_motivation_context",
                user_id=self.user_id,
            )
            return {}

    def _find_planned_workout_for_activity(
        self, activity: Dict, plan_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find planned workout that matches an activity.

        Returns target distance, pace, and HR zone if found.
        """
        try:
            activity_date_str = activity.get("date")
            if not activity_date_str:
                return None

            if isinstance(activity_date_str, str):
                activity_date = date.fromisoformat(activity_date_str)
            else:
                activity_date = activity_date_str

            from src.db.models.plan_workouts import PlanWorkout

            # Look for workout within ±1 day
            planned = (
                self.session.query(PlanWorkout)
                .filter_by(plan_id=plan_id)
                .filter(PlanWorkout.date >= activity_date - timedelta(days=1))
                .filter(PlanWorkout.date <= activity_date + timedelta(days=1))
                .first()
            )

            if not planned:
                return None

            target = {
                "distance_miles": float(planned.miles),
            }

            if planned.target_zone:
                target["pace_range"] = planned.target_zone

            if planned.target_hr:
                target["hr_zone"] = planned.target_hr

            return target

        except Exception:
            return None

    def _calculate_deviation(self, activity: Dict, plan_target: Dict) -> Dict[str, Any]:
        """Calculate deviation from plan target."""
        deviation = {}

        # Pace deviation
        if activity.get("pace_seconds_per_mile") and plan_target.get("pace_range"):
            # Simple: could parse pace_range and compare
            # For now, just indicate if faster/slower
            pass  # TODO: Implement pace comparison

        # HR zone deviation
        if plan_target.get("hr_zone"):
            # Extract zone number and check if activity HR matches
            deviation["hr_above_zone"] = False  # TODO: Implement HR zone check

        return deviation
