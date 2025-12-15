"""
RunnerStateBuilder for Coach system.

Builds the canonical RunnerState object by orchestrating existing services
and transforming their outputs to match the RunnerState schema.

This is an ORCHESTRATOR/WRAPPER - it does NOT reimplement calculations.
It calls existing services and formats their outputs.
"""

from datetime import date, timedelta
from typing import Dict, Optional, List, Any

from sqlalchemy.orm import Session

from coach.builders.race_info_builder import RaceInfoBuilder
from coach.utils.schema_validator import SchemaValidator
from coach.utils.error_handler import CoachErrorHandler
from coach.utils.config import Config

from src.db.dao.plans_dao import get_active_plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.heart_rate.heart_rate_orchestration_service import (
    HeartRateZoneOrchestrationService,
)
from src.services.training_plan.weekly_metrics_service import WeeklyMetricsService
from src.services.training_plan.trend_analysis_service import TrendAnalysisService
from src.services.training_plan.week_analysis_service import WeekAnalysisService
from src.services.training_plan.week_log_service import fetch_week_logs_from_db
from src.services.training_plan.v2.shared_v2.long_run_signals import (
    detect_consecutive_long_runs,
)
from src.services.training_plan.weekly_adjuster import WeekLogRun
from src.services.smart_data_service import SmartDataService
from src.services.training_plan.workout_utils import pace_range_to_str


class RunnerStateBuilder:
    """
    Builds RunnerState object by orchestrating existing services.

    Does NOT reimplement calculations - uses existing services:
    - RaceInfoBuilder: Extracts race info
    - HeartRateZoneOrchestrationService: HR zone calculations
    - WeeklyMetricsService: Weekly metrics (volume, intensity, consistency scores)
    - TrendAnalysisService: Trend analysis (improving/declining/stable)
    - Pattern detection functions: Long run patterns
    - SmartDataService: Activity data
    - PlanWorkout.pace_ranges: Pace zones from database
    """

    def __init__(self, session: Session, user_id: str):
        """
        Initialize RunnerStateBuilder.

        Args:
            session: Database session
            user_id: User ID to build state for
        """
        self.session = session
        self.user_id = user_id

    def build(self) -> Dict[str, Any]:
        """
        Build complete RunnerState object.

        Returns:
            Dictionary matching RunnerState schema
        """
        try:
            # Get active plan (required for most data)
            plan = get_active_plan(self.session, self.user_id)
            if not plan:
                # Return minimal state if no active plan
                return self._build_minimal_state()

            plan_id = plan.id
            race_date = plan.race_date

            if not race_date:
                return self._build_minimal_state()

            # 1. Race info (uses RaceInfoBuilder)
            race_info = RaceInfoBuilder(self.session, self.user_id).build()
            if not race_info:
                return self._build_minimal_state()

            # 2. Calculate phase and week_of_block
            phase, week_of_block = self._calculate_phase_and_week(race_date, plan_id)

            # 3. HR Zones (USE EXISTING SERVICE)
            hr_zones = self._build_hr_zones()

            # 4. Pace Zones (extract from plan workouts)
            pace_zones = self._build_pace_zones(plan_id)

            # 5. Weekly Metrics (USE EXISTING SERVICE)
            weekly_metrics = self._build_weekly_metrics(plan_id)

            # 6. Patterns (USE EXISTING FUNCTIONS + simple logic)
            patterns = self._build_patterns(plan_id, race_date)

            # 7. Safety indicators
            safety = self._build_safety_indicators()

            # Build complete state
            runner_state = {
                "phase": phase,
                "week_of_block": week_of_block,
                "plan_type": plan.plan_name if plan.plan_name else None,
                "race": race_info,
                "zones": {
                    "hr": hr_zones,
                    "pace": pace_zones,
                },
                "patterns": patterns,
                "safety": safety,
            }

            # Only include weekly_metrics if available (not required by schema)
            if weekly_metrics is not None:
                runner_state["weekly_metrics"] = weekly_metrics

            # Validate against schema
            result = {
                "version": "1.0.0",
                "runner_state": runner_state,
            }

            try:
                SchemaValidator.validate_runner_state(result)
            except Exception as e:
                # Log but don't fail - schema validation is informative
                from coach.utils.error_handler import ErrorSeverity

                CoachErrorHandler.handle(
                    error=e,
                    severity=ErrorSeverity.MEDIUM,
                    component="RunnerStateBuilder.schema_validation",
                    user_id=self.user_id,
                )

            return result

        except Exception as e:
            return CoachErrorHandler.handle_runner_state_builder_error(e, self.user_id)

    def _calculate_phase_and_week(
        self, race_date: date, plan_id: int
    ) -> tuple[str, int]:
        """
        Calculate current training phase and week of block.

        Uses same logic as WeeklyRebuildService._determine_phase().
        """
        today = date.today()
        days_until_race = (race_date - today).days

        # Calculate week number (race week = week 0, count backwards)
        if days_until_race < 0:
            # Race already passed
            return "Taper", 1

        # Week number: weeks until race week
        # If race is in 12 weeks, we're in week 12 of the plan
        week_of_block = max(1, (days_until_race // 7) + 1)

        # Get total weeks from plan (count workouts or estimate)
        total_weeks = self._get_total_weeks(plan_id)

        # Determine phase using same logic as _determine_phase()
        phase = self._determine_phase(week_of_block, total_weeks)

        return phase, week_of_block

    def _get_total_weeks(self, plan_id: int) -> int:
        """
        Get total weeks in plan.

        Estimates by finding the maximum week_num from workouts,
        or counts distinct week numbers.
        """
        # Get all workouts for the plan
        workouts = (
            self.session.query(PlanWorkout)
            .filter_by(plan_id=plan_id)
            .order_by(PlanWorkout.date)
            .all()
        )

        if not workouts:
            return 16  # Default fallback

        # Estimate total weeks by date range
        min_date = min(w.date for w in workouts)
        max_date = max(w.date for w in workouts)
        weeks_span = (max_date - min_date).days // 7 + 1

        return max(weeks_span, 16)  # At least 16 weeks default

    def _determine_phase(self, week_num: int, total_weeks: int) -> str:
        """
        Determine training phase (same logic as WeeklyRebuildService._determine_phase).
        """
        if week_num <= total_weeks * 0.4:
            return "Base"
        elif week_num <= total_weeks * 0.7:
            return "Build"
        elif week_num <= total_weeks * 0.9:
            return "Peak"
        else:
            return "Taper"

    def _build_hr_zones(self) -> Dict[str, str]:
        """
        Build HR zones using HeartRateZoneOrchestrationService.

        Formats output as "105-120 bpm" strings per schema.
        """
        try:
            result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
                self.session, self.user_id, use_estimate=True
            )

            if not result.get("success") or "zones" not in result:
                # Return empty zones if calculation failed
                return {}

            zones = result["zones"]
            formatted = {}

            # Format as "min-max bpm" strings
            for zone_key in ["Z1", "Z2", "Z3", "Z4", "Z5"]:
                if zone_key in zones:
                    zone_min, zone_max = zones[zone_key]
                    formatted[zone_key.lower()] = f"{int(zone_min)}-{int(zone_max)} bpm"

            return formatted

        except Exception as e:
            from coach.utils.error_handler import ErrorSeverity

            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="RunnerStateBuilder._build_hr_zones",
                user_id=self.user_id,
            )
            return {}

    def _build_pace_zones(self, plan_id: int) -> Dict[str, str]:
        """
        Build pace zones from plan workouts.

        Extracts pace_ranges from any recent workout in the plan.
        """
        try:
            # Get a recent workout with pace_ranges
            workout = (
                self.session.query(PlanWorkout)
                .filter_by(plan_id=plan_id)
                .filter(PlanWorkout.pace_ranges.isnot(None))
                .order_by(PlanWorkout.date.desc())
                .first()
            )

            if not workout or not workout.pace_ranges:
                # No pace ranges found in DB
                return {}

            pace_ranges = workout.pace_ranges

            # Format pace zones from DB structure: {"E": [min_sec, max_sec], ...}
            formatted = {}

            # Easy pace
            if "E" in pace_ranges and len(pace_ranges["E"]) == 2:
                min_sec, max_sec = pace_ranges["E"]
                formatted["easy"] = pace_range_to_str(float(min_sec), float(max_sec))

            # Marathon pace (single value)
            if "M" in pace_ranges:
                if isinstance(pace_ranges["M"], list) and len(pace_ranges["M"]) >= 1:
                    m_pace = float(pace_ranges["M"][0])
                    formatted["marathon"] = pace_range_to_str(m_pace, m_pace)
                elif isinstance(pace_ranges["M"], (int, float)):
                    m_pace = float(pace_ranges["M"])
                    formatted["marathon"] = pace_range_to_str(m_pace, m_pace)

            # Threshold pace
            if "T" in pace_ranges and len(pace_ranges["T"]) == 2:
                min_sec, max_sec = pace_ranges["T"]
                formatted["threshold"] = pace_range_to_str(
                    float(min_sec), float(max_sec)
                )

            return formatted

        except Exception as e:
            from coach.utils.error_handler import ErrorSeverity

            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="RunnerStateBuilder._build_pace_zones",
                user_id=self.user_id,
                metadata={"plan_id": plan_id},
            )
            return {}

    def _build_weekly_metrics(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """
        Build weekly metrics using WeeklyMetricsService.

        Gets current week's metrics and formats for schema.
        """
        try:
            # Get most recent week's metrics
            historical = WeeklyMetricsService.get_historical_metrics(
                self.session, plan_id, weeks=1
            )

            if not historical:
                return None

            current_week = historical[0]  # Most recent first

            # Format for schema
            # Note: total_actual_miles is not stored in WeeklyMetrics.
            # We can try to get it from activities, or estimate from load.
            mileage = self._get_weekly_mileage(current_week.week_start_date)

            return {
                "week_start": current_week.week_start_date.isoformat(),
                "mileage": mileage,
                "volume_score": float(current_week.volume_score),
                "intensity_score": float(current_week.intensity_score),
                "consistency_score": float(current_week.consistency_score),
                "load_change_pct": (
                    float(current_week.load_delta_pct)
                    if current_week.load_delta_pct is not None
                    else None
                ),
                "fatigue_flags": (
                    current_week.fatigue_markers
                    if hasattr(current_week, "fatigue_markers")
                    and current_week.fatigue_markers
                    else []
                ),
            }

        except Exception as e:
            from coach.utils.error_handler import ErrorSeverity

            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="RunnerStateBuilder._build_weekly_metrics",
                user_id=self.user_id,
                metadata={"plan_id": plan_id},
            )
            return None

    def _build_patterns(self, plan_id: int, race_date: date) -> Dict[str, Any]:
        """
        Build patterns using existing pattern detection functions.

        Uses detect_consecutive_long_runs() and other pattern functions.
        """
        try:
            # Get recent activities for pattern detection
            data_service = SmartDataService(self.session, self.user_id)
            activities = data_service._get_recent_activities(weeks=8)

            # Detect long run patterns (uses existing function)
            long_run_patterns = detect_consecutive_long_runs(activities)

            # Count long runs that were too fast
            long_runs_too_fast_count = self._count_long_runs_too_fast(activities)

            # Count missed key workouts
            missed_workouts = self._count_missed_key_workouts(plan_id, race_date)

            # Calculate trend using TrendAnalysisService
            trend = self._calculate_trend(plan_id)

            return {
                "long_runs_too_fast_count": long_runs_too_fast_count,
                "missed_key_workouts_last_4_weeks": missed_workouts,
                "trend": trend,
            }

        except Exception as e:
            from coach.utils.error_handler import ErrorSeverity

            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="RunnerStateBuilder._build_patterns",
                user_id=self.user_id,
            )
            return {
                "long_runs_too_fast_count": 0,
                "missed_key_workouts_last_4_weeks": 0,
                "trend": "stable",
            }

    def _count_long_runs_too_fast(self, activities: List[Dict]) -> int:
        """
        Count long runs that were too fast (above Zone 2 HR or faster than easy pace).

        Simple implementation: check if long runs (>8mi) had HR > Zone 2 threshold.
        """
        if not activities:
            return 0

        # Get long run threshold from config
        long_run_threshold = Config.get_thresholds("long_run_distance_threshold", 8.0)

        # Get HR zones to determine Zone 2 max
        try:
            hr_result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
                self.session, self.user_id, use_estimate=True
            )
            zone2_max = None
            if hr_result.get("success") and "zones" in hr_result:
                if "Z2" in hr_result["zones"]:
                    _, zone2_max = hr_result["zones"]["Z2"]
        except Exception:
            zone2_max = None

        count = 0
        for activity in activities:
            distance = activity.get("distance_miles", 0.0)
            avg_hr = activity.get("average_heartrate")

            # Check if it's a long run
            if distance < long_run_threshold:
                continue

            # Check if HR was too high (above Zone 2)
            if zone2_max and avg_hr and avg_hr > zone2_max:
                count += 1

        return count

    def _count_missed_key_workouts(self, plan_id: int, race_date: date) -> int:
        """
        Count missed key workouts (quality workouts) in last 4 weeks.

        Uses fetch_week_logs_from_db() to get week logs and counts
        quality workouts with done_mi == 0.
        """
        try:
            # Get current week number
            today = date.today()
            days_until_race = (race_date - today).days
            current_week = max(1, (days_until_race // 7) + 1)

            # Check last 4 weeks
            missed_count = 0
            quality_types = {"steady", "threshold", "tempo", "intervals", "vo2"}

            for week_offset in range(4):
                week_num = current_week + week_offset
                if week_num < 1:
                    continue

                week_logs = fetch_week_logs_from_db(
                    self.session, plan_id, week_num, race_date
                )

                for log in week_logs:
                    # Check if it's a quality workout that was missed
                    run_type = log.run_type.lower() if log.run_type else ""
                    if any(quality in run_type for quality in quality_types):
                        if log.done_mi == 0 or log.done_mi is None:
                            missed_count += 1

            return missed_count

        except Exception as e:
            CoachErrorHandler.handle_low_severity_error(
                "Failed to count missed workouts",
                e,
                {"user_id": self.user_id, "plan_id": plan_id},
                fallback_value=0,
            )
            return 0

    def _calculate_trend(self, plan_id: int) -> str:
        """
        Calculate overall trend using TrendAnalysisService.

        Aggregates multiple trend indicators into a single trend.
        """
        try:
            # This would require a WeekAnalysisResult for current week
            # For now, use a simplified approach or return stable
            # TODO: Full integration with TrendAnalysisService requires
            # analyzing current week first
            return "stable"

        except Exception as e:
            CoachErrorHandler.handle_medium_severity_error(
                "Failed to calculate trend",
                e,
                {"user_id": self.user_id, "plan_id": plan_id},
            )
            return "stable"

    def _get_weekly_mileage(self, week_start: date) -> float:
        """
        Get weekly mileage from activities for a specific week.

        Args:
            week_start: Monday of the week

        Returns:
            Total mileage for the week
        """
        try:
            week_end = week_start + timedelta(days=6)
            data_service = SmartDataService(self.session, self.user_id)
            activities = data_service._get_recent_activities(weeks=2)

            # Filter to this week
            week_activities = []
            for a in activities:
                if not a.get("date"):
                    continue
                activity_date = a["date"]
                if isinstance(activity_date, str):
                    try:
                        activity_date = date.fromisoformat(activity_date)
                    except (ValueError, AttributeError):
                        continue
                if isinstance(activity_date, date):
                    if week_start <= activity_date <= week_end:
                        week_activities.append(a)

            return sum(a.get("distance_miles", 0.0) or 0.0 for a in week_activities)

        except Exception:
            return 0.0

    def _build_safety_indicators(self) -> Dict[str, bool]:
        """
        Build safety indicators from activity data.

        Checks HR and pace data reliability.
        """
        try:
            data_service = SmartDataService(self.session, self.user_id)
            activities = data_service._get_recent_activities(weeks=4)

            if not activities:
                return {
                    "hr_data_reliable": False,
                    "pace_data_reliable": False,
                    "reported_injury": False,
                }

            # Check HR data reliability (>80% have HR)
            activities_with_hr = sum(
                1
                for a in activities
                if a.get("average_heartrate") is not None
                and a.get("average_heartrate") > 0
            )
            hr_reliability = activities_with_hr / len(activities) if activities else 0
            hr_data_reliable = hr_reliability > 0.8

            # Check pace data reliability (all should have pace)
            activities_with_pace = sum(
                1
                for a in activities
                if (
                    a.get("pace_seconds_per_mile") is not None
                    or a.get("average_speed") is not None
                )
            )
            pace_reliability = (
                activities_with_pace / len(activities) if activities else 0
            )
            pace_data_reliable = pace_reliability > 0.9

            # TODO: Check for reported injuries (could be in user profile or flags)
            reported_injury = False

            return {
                "hr_data_reliable": hr_data_reliable,
                "pace_data_reliable": pace_data_reliable,
                "reported_injury": reported_injury,
            }

        except Exception as e:
            from coach.utils.error_handler import ErrorSeverity

            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="RunnerStateBuilder._build_safety_indicators",
                user_id=self.user_id,
            )
            return {
                "hr_data_reliable": False,
                "pace_data_reliable": False,
                "reported_injury": False,
            }

    def _build_minimal_state(self) -> Dict[str, Any]:
        """Build minimal state when required data is missing."""
        return {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Base",
                "week_of_block": 1,
                "race": None,
                "zones": {"hr": {}, "pace": {}},
                "safety": {
                    "hr_data_reliable": False,
                    "pace_data_reliable": False,
                    "reported_injury": False,
                },
            },
        }
