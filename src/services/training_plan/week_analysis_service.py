"""
Week Analysis Service - Multi-Dimensional Metrics

Purpose:
    Calculate 6 core metrics from week logs to assess training performance:
    1. Volume Score (% of planned miles completed)
    2. Intensity Score (% of quality workouts completed)
    3. Consistency Score (% of planned days completed)
    4. Pace Trend (deviation from planned pace)
    5. Recovery Indicators (fatigue markers)
    6. Training Load Delta (week-over-week load change)

Responsibilities:
    - Calculate all 6 metrics
    - Generate comprehensive analysis result
    - Calculate dynamic thresholds for fatigue detection

Dependencies:
    - WeekLogService (for week logs)
    - AdaptiveConfig (for thresholds)
    - WorkoutUtils (for pace calculations)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import logging
import statistics

from .weekly_adjuster import WeekLogRun
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.activities import Activity
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    normalize_run_type_key,
)
from src.utils.adaptive_constants import (
    AdaptiveConfig,
    FATIGUE_PACE_THRESHOLD_PCT,
    FATIGUE_HR_THRESHOLD_PCT,
    FATIGUE_PACE_THRESHOLD_MIN,
)

logger = logging.getLogger(__name__)


@dataclass
class WeekAnalysisResult:
    """Complete analysis of a week's training performance."""

    # Core metrics (0-100 scores)
    volume_score: float  # % of planned miles completed
    intensity_score: float  # % of quality workouts completed
    consistency_score: float  # % of planned days completed

    # Pace analysis
    pace_deviation: float  # seconds (negative = faster, positive = slower)
    avg_actual_pace: Optional[float]  # seconds per mile
    avg_planned_pace: Optional[float]  # seconds per mile

    # Recovery indicators
    consecutive_missed_days: int
    fatigue_markers: List[str]  # ["pace_declining", "hr_increasing", etc.]

    # Training load
    current_week_load: float  # Proxy TSS (distance × RPE)
    previous_week_load: Optional[float]
    load_delta_pct: Optional[float]  # % change from previous week

    # Dynamic thresholds (calculated from baseline)
    pace_threshold: float  # Dynamic threshold for fatigue detection
    hr_threshold: float  # Dynamic threshold for fatigue detection

    # Metadata
    week_num: int
    week_start_date: date
    total_planned_miles: float
    total_actual_miles: float
    planned_workouts: int
    completed_workouts: int
    avg_zone_compliance_by_type: Dict[str, float] = field(default_factory=dict)


class WeekAnalysisService:
    """Service for analyzing week performance across multiple dimensions."""

    @staticmethod
    def analyze_week(
        session: Session,
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
        week_num: int,
        week_start_date: date,
        previous_week_metrics: Optional[WeekAnalysisResult] = None,
    ) -> WeekAnalysisResult:
        """
        Analyze week performance across 6 dimensions.

        Calculates:
        - Volume score: actual_miles / planned_miles
        - Intensity score: quality_completed / quality_planned
        - Consistency score: days_completed / days_planned
        - Pace trend: avg_actual_pace - avg_planned_pace
        - Recovery indicators: fatigue markers
        - Load delta: (current_load - prev_load) / prev_load

        Also calculates dynamic thresholds for fatigue detection.

        Args:
            session: SQLAlchemy session (for fetching previous week data)
            week_logs: List of WeekLogRun entries
            planned_workouts: List of planned workouts for the week
            week_num: Week number
            week_start_date: Week start date (Monday)
            previous_week_metrics: Optional previous week metrics for load delta

        Returns:
            WeekAnalysisResult with all metrics calculated
        """
        # Rollback any failed transaction first to prevent lazy-load errors
        if session.in_transaction():
            try:
                session.rollback()
            except Exception:
                pass  # Ignore rollback errors

        # Extract all needed data from planned_workouts BEFORE any queries
        # This prevents lazy-load failures if transaction was aborted
        planned_workouts_data = []
        if planned_workouts:
            for w in planned_workouts:
                # Access all attributes we'll need to prevent lazy-loading later
                try:
                    planned_workouts_data.append(
                        {
                            "miles": float(w.miles) if w.miles else 0.0,
                            "workout_type": w.workout_type or "",
                            "date": w.date if hasattr(w, "date") else None,
                        }
                    )
                except Exception as e:
                    # If we can't access the data, log and skip
                    logger.debug(f"Could not extract data from planned workout: {e}")
                    continue

        # Calculate core metrics (using extracted data to avoid lazy-load issues)
        volume_score = WeekAnalysisService._calculate_volume_score(
            week_logs, planned_workouts_data
        )
        intensity_score = WeekAnalysisService._calculate_intensity_score(
            week_logs, planned_workouts_data
        )
        consistency_score = WeekAnalysisService._calculate_consistency_score(
            week_logs, planned_workouts_data
        )

        # Calculate pace trend
        pace_data = WeekAnalysisService._calculate_pace_trend(
            week_logs, planned_workouts_data
        )

        # Calculate recovery indicators
        recovery_data = WeekAnalysisService._calculate_recovery_indicators(
            week_logs, planned_workouts_data
        )

        # Calculate training load
        previous_load = (
            previous_week_metrics.current_week_load if previous_week_metrics else None
        )
        load_data = WeekAnalysisService._calculate_training_load(
            week_logs, previous_load
        )

        # Calculate dynamic thresholds
        # Get user_id from plan (need to query plan if relationship not loaded)
        user_id = None
        if planned_workouts:  # Use original list for relationship access
            try:
                # Try to access via relationship first
                if hasattr(planned_workouts[0], "plan") and planned_workouts[0].plan:
                    user_id = str(planned_workouts[0].plan.user_id)
                else:
                    # Query plan directly if relationship not loaded
                    from src.db.models.plans import Plan

                    plan_id = (
                        planned_workouts[0].plan_id
                        if hasattr(planned_workouts[0], "plan_id")
                        else None
                    )
                    if plan_id:
                        plan = session.query(Plan).filter_by(id=plan_id).first()
                        if plan:
                            user_id = str(plan.user_id)
            except Exception as e:
                logger.debug(f"Could not get user_id for thresholds: {e}")

        thresholds = (
            WeekAnalysisService._calculate_dynamic_thresholds(
                session, user_id, week_start_date
            )
            if user_id
            else {"pace_threshold": FATIGUE_PACE_THRESHOLD_MIN, "hr_threshold": 5.0}
        )

        # Calculate totals (using extracted data)
        total_planned_miles = (
            sum(w["miles"] for w in planned_workouts_data)
            if planned_workouts_data
            else 0.0
        )
        total_actual_miles = sum(w.done_mi for w in week_logs)
        planned_workouts_count = (
            len(planned_workouts_data) if planned_workouts_data else 0
        )
        completed_workouts_count = len([w for w in week_logs if w.done_mi > 0])
        avg_zone_compliance_by_type = (
            WeekAnalysisService._calculate_avg_zone_compliance_by_type(
                session, planned_workouts
            )
        )

        return WeekAnalysisResult(
            volume_score=volume_score,
            intensity_score=intensity_score,
            consistency_score=consistency_score,
            pace_deviation=pace_data.get("pace_deviation", 0.0),
            avg_actual_pace=pace_data.get("avg_actual_pace"),
            avg_planned_pace=pace_data.get("avg_planned_pace"),
            consecutive_missed_days=recovery_data.get("consecutive_missed_days", 0),
            fatigue_markers=recovery_data.get("fatigue_markers", []),
            current_week_load=load_data.get("current_week_load", 0.0),
            previous_week_load=load_data.get("previous_week_load"),
            load_delta_pct=load_data.get("load_delta_pct"),
            pace_threshold=thresholds.get("pace_threshold", FATIGUE_PACE_THRESHOLD_MIN),
            hr_threshold=thresholds.get("hr_threshold", 5.0),
            week_num=week_num,
            week_start_date=week_start_date,
            total_planned_miles=total_planned_miles,
            total_actual_miles=total_actual_miles,
            planned_workouts=planned_workouts_count,
            completed_workouts=completed_workouts_count,
            avg_zone_compliance_by_type=avg_zone_compliance_by_type,
        )

    @staticmethod
    def _calculate_volume_score(
        week_logs: List[WeekLogRun],
        planned_workouts: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate volume score (0-100%).

        Volume score = (total actual miles / total planned miles) * 100
        """
        if not planned_workouts:
            return 0.0

        total_planned = sum(w.get("miles", 0.0) for w in planned_workouts)
        total_actual = sum(w.done_mi for w in week_logs)

        if total_planned == 0:
            return 0.0

        score = (total_actual / total_planned) * 100.0
        return min(100.0, max(0.0, score))

    @staticmethod
    def _calculate_intensity_score(
        week_logs: List[WeekLogRun],
        planned_workouts: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate intensity score (0-100%).

        Intensity score = (quality workouts completed / quality workouts planned) * 100
        Quality workouts are tempo, intervals, fartlek, etc. (not easy/recovery)
        """
        if not planned_workouts:
            return 0.0

        # Identify quality workouts (non-easy/recovery)
        quality_planned = [
            w
            for w in planned_workouts
            if w.get("workout_type")
            and w.get("workout_type", "").lower() not in ("easy", "recovery", "rest")
        ]

        # Count quality workouts completed
        # Match by matching planned workouts with completed week logs
        quality_completed = 0
        for workout in quality_planned:
            # Find matching week log entry
            matching_log = None
            for log in week_logs:
                # Simple matching: same workout type (normalized) and done_mi > 0
                if log.done_mi > 0 and log.run_type in (
                    "tempo",
                    "threshold",
                    "interval",
                    "fartlek",
                    "speed",
                ):
                    # Check if this could match the planned workout
                    if workout.get("workout_type") and any(
                        term in workout.get("workout_type", "").lower()
                        for term in [
                            "tempo",
                            "threshold",
                            "interval",
                            "fartlek",
                            "speed",
                        ]
                    ):
                        matching_log = log
                        break

            if matching_log:
                quality_completed += 1

        if not quality_planned:
            return 100.0  # No quality planned = perfect score

        score = (quality_completed / len(quality_planned)) * 100.0
        return min(100.0, max(0.0, score))

    @staticmethod
    def _calculate_consistency_score(
        week_logs: List[WeekLogRun],
        planned_workouts: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate consistency score (0-100%).

        Consistency score = (days with completed workouts / planned workout days) * 100
        """
        if not planned_workouts:
            return 0.0

        planned_days = len(planned_workouts)
        completed_days = len([w for w in week_logs if w.done_mi > 0])

        score = (completed_days / planned_days) * 100.0
        return min(100.0, max(0.0, score))

    @staticmethod
    def _calculate_pace_trend(
        week_logs: List[WeekLogRun],
        planned_workouts: List[Dict[str, Any]],
    ) -> Dict[str, Optional[float]]:
        """
        Calculate pace trend analysis.

        Returns:
            {
                "pace_deviation": float,  # seconds
                "avg_actual_pace": Optional[float],
                "avg_planned_pace": Optional[float],
            }
        """
        # For now, we don't have actual pace data in WeekLogRun
        # This would need to be enhanced with actual pace from activities
        # For now, return placeholder values
        return {
            "pace_deviation": 0.0,
            "avg_actual_pace": None,
            "avg_planned_pace": None,
        }

    @staticmethod
    def _calculate_recovery_indicators(
        week_logs: List[WeekLogRun],
        planned_workouts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate recovery indicators (fatigue markers).

        Returns:
            {
                "consecutive_missed_days": int,
                "fatigue_markers": List[str],
            }
        """
        # Count consecutive missed days (days with planned but not completed)
        consecutive_missed = 0
        fatigue_markers = []

        # Simple check: if multiple missed workouts in a row
        missed_count = 0
        for log in week_logs:
            if log.done_mi == 0:
                missed_count += 1
            else:
                consecutive_missed = max(consecutive_missed, missed_count)
                missed_count = 0

        consecutive_missed = max(consecutive_missed, missed_count)

        # Add fatigue markers
        if consecutive_missed >= 2:
            fatigue_markers.append("consecutive_missed_workouts")

        # Check for high RPE in completed workouts (indicates stress)
        high_rpe_count = len([w for w in week_logs if w.rpe >= 7])
        if high_rpe_count >= 2:
            fatigue_markers.append("high_rpe_workouts")

        return {
            "consecutive_missed_days": consecutive_missed,
            "fatigue_markers": fatigue_markers,
        }

    @staticmethod
    def _calculate_training_load(
        week_logs: List[WeekLogRun],
        previous_week_load: Optional[float] = None,
    ) -> Dict[str, Optional[float]]:
        """
        Calculate training load (proxy TSS) and delta.

        Proxy TSS = Σ(distance_mi × estimated_rpe)

        Returns:
            {
                "current_week_load": float,
                "previous_week_load": Optional[float],
                "load_delta_pct": Optional[float],
            }
        """
        # Calculate current week load
        current_load = sum(log.done_mi * max(log.rpe, 1) for log in week_logs)

        # Calculate delta if we have previous load
        load_delta_pct = None
        if previous_week_load and previous_week_load > 0:
            load_delta_pct = (
                (current_load - previous_week_load) / previous_week_load
            ) * 100.0

        return {
            "current_week_load": current_load,
            "previous_week_load": previous_week_load,
            "load_delta_pct": load_delta_pct,
        }

    @staticmethod
    def _calculate_avg_zone_compliance_by_type(
        session: Session,
        planned_workouts: List[PlanWorkout],
    ) -> Dict[str, float]:
        """
        Calculate average zone compliance by canonical run type for this week.

        Uses activities matched to the provided plan workouts and aggregates
        `zone_compliance_pct` by executed (or planned fallback) run type.
        """
        if not planned_workouts:
            return {}

        workout_ids = [w.id for w in planned_workouts if getattr(w, "id", None)]
        if not workout_ids:
            return {}

        try:
            rows = (
                session.query(
                    Activity.executed_type,
                    Activity.planned_type,
                    Activity.zone_compliance_pct,
                )
                .filter(
                    and_(
                        Activity.matched_plan_workout_id.in_(workout_ids),
                        Activity.zone_compliance_pct.isnot(None),
                    )
                )
                .all()
            )
        except Exception as e:
            logger.warning(f"Error calculating zone compliance aggregates: {e}")
            return {}

        grouped: Dict[str, List[float]] = {}
        for executed_type, planned_type, zone_compliance in rows:
            if zone_compliance is None:
                continue

            run_type_key = normalize_run_type_key(
                executed_type
            ) or normalize_run_type_key(planned_type)
            if not run_type_key:
                continue

            grouped.setdefault(run_type_key, []).append(float(zone_compliance))

        return {
            run_type: round(statistics.mean(values), 2)
            for run_type, values in grouped.items()
            if values
        }

    @staticmethod
    def _calculate_dynamic_thresholds(
        session: Session,
        user_id: str,
        week_start_date: date,
    ) -> Dict[str, float]:
        """
        Calculate dynamic thresholds for fatigue detection.

        Uses last 2-3 weeks of easy runs to establish baseline:
        - Pace threshold: max(10s, 2% of baseline pace)
        - HR threshold: 3% of baseline HR

        Returns:
            {
                "pace_threshold": float,
                "hr_threshold": float,
            }
        """
        # Calculate lookback period
        lookback_start = week_start_date - timedelta(weeks=2)

        try:
            # Rollback any failed transaction first
            if session.in_transaction():
                try:
                    session.rollback()
                except Exception:
                    pass  # Ignore rollback errors

            # Fetch easy runs from last 2 weeks
            from sqlalchemy import and_
            from datetime import datetime

            activities = (
                session.query(Activity)
                .filter(
                    and_(
                        Activity.user_id == user_id,
                        Activity.type == "Run",
                        Activity.start_date
                        >= datetime.combine(lookback_start, datetime.min.time()),
                        Activity.start_date
                        < datetime.combine(week_start_date, datetime.min.time()),
                    )
                )
                .order_by(Activity.start_date.desc())
                .limit(20)  # Limit to most recent 20 runs
                .all()
            )

            if not activities:
                return {
                    "pace_threshold": FATIGUE_PACE_THRESHOLD_MIN,
                    "hr_threshold": 5.0,  # Default 5 bpm
                }

            # Calculate baseline pace from easy runs
            easy_paces = []
            easy_hrs = []

            for activity in activities:
                if (
                    activity.conv_distance and activity.conv_distance >= 2.0
                ):  # At least 2 miles
                    # Calculate pace (seconds per mile)
                    if activity.moving_time and activity.moving_time > 0:
                        pace_sec_per_mi = activity.moving_time / activity.conv_distance
                        if 360 <= pace_sec_per_mi <= 1200:  # Reasonable range
                            easy_paces.append(pace_sec_per_mi)

                    # Collect HR data
                    if activity.average_heartrate and activity.average_heartrate > 0:
                        easy_hrs.append(float(activity.average_heartrate))

            # Calculate thresholds
            if easy_paces:
                baseline_pace = statistics.median(easy_paces)
                pace_threshold = max(
                    FATIGUE_PACE_THRESHOLD_MIN,
                    baseline_pace * FATIGUE_PACE_THRESHOLD_PCT,
                )
            else:
                pace_threshold = FATIGUE_PACE_THRESHOLD_MIN

            if easy_hrs:
                baseline_hr = statistics.median(easy_hrs)
                hr_threshold = baseline_hr * FATIGUE_HR_THRESHOLD_PCT
            else:
                hr_threshold = 5.0  # Default 5 bpm

            return {
                "pace_threshold": pace_threshold,
                "hr_threshold": hr_threshold,
            }

        except Exception as e:
            logger.warning(f"Error calculating dynamic thresholds: {e}")
            return {
                "pace_threshold": FATIGUE_PACE_THRESHOLD_MIN,
                "hr_threshold": 5.0,
            }
