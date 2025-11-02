"""
Weekly Metrics Service - Metrics Persistence

Purpose:
    Persist weekly analysis metrics and decision logs to database.
    Enables historical trend analysis and future ML features.

Responsibilities:
    - Save weekly metrics to weekly_metrics table
    - Save decision logs to weekly_decision_log table
    - Query historical metrics for trend analysis

Dependencies:
    - WeeklyMetricsDAO (database operations)
    - WeeklyDecisionLogDAO (database operations)
    - WeekAnalysisResult (from Stage 2)
    - AdjustmentDecision (from Stage 4)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
import logging

from .week_analysis_service import WeekAnalysisResult
from .adaptive_adjustment_service import AdjustmentDecision
from src.db.dao.weekly_metrics_dao import (
    upsert_weekly_metrics,
    get_historical_metrics as get_historical_metrics_dao,
)
from src.db.dao.weekly_decision_log_dao import (
    create_decision_log,
    get_decision_logs_by_plan,
)

logger = logging.getLogger(__name__)


class WeeklyMetricsService:
    """Service for persisting and querying weekly metrics."""

    @staticmethod
    def save_week_metrics(
        session: Session,
        plan_id: int,
        analysis: WeekAnalysisResult,
        decision: AdjustmentDecision,
    ) -> int:
        """
        Save weekly metrics and decision log to database.

        Creates records in:
        - weekly_metrics table
        - weekly_decision_log table

        Returns:
            ID of saved weekly_metrics record
        """
        try:
            # Save metrics
            metrics_record = upsert_weekly_metrics(
                session=session,
                plan_id=plan_id,
                week_num=analysis.week_num,
                week_start_date=analysis.week_start_date,
                volume_score=analysis.volume_score,
                intensity_score=analysis.intensity_score,
                consistency_score=analysis.consistency_score,
                pace_deviation=analysis.pace_deviation,
                avg_actual_pace=analysis.avg_actual_pace,
                avg_planned_pace=analysis.avg_planned_pace,
                consecutive_missed_days=analysis.consecutive_missed_days,
                current_week_load=analysis.current_week_load,
                previous_week_load=analysis.previous_week_load,
                load_delta_pct=analysis.load_delta_pct,
                pace_threshold=analysis.pace_threshold,
                hr_threshold=analysis.hr_threshold,
                match_score=decision.match_score,
                phase=decision.phase,
                weeks_remaining=decision.weeks_remaining,
            )

            # Save decision log
            create_decision_log(
                session=session,
                plan_id=plan_id,
                week_num=analysis.week_num,
                week_start_date=analysis.week_start_date,
                decision_type=decision.decision_type,
                trigger_reason=decision.trigger_reason,
                metrics_json={
                    "volume_score": analysis.volume_score,
                    "intensity_score": analysis.intensity_score,
                    "consistency_score": analysis.consistency_score,
                    "pace_deviation": analysis.pace_deviation,
                    "current_week_load": analysis.current_week_load,
                    "load_delta_pct": analysis.load_delta_pct,
                },
                adjustments_json={
                    "volume_change_pct": decision.volume_change_pct,
                    "pace_adjustment_sec": decision.pace_adjustment_sec,
                    "disable_quality_workouts": decision.disable_quality_workouts,
                },
                match_score=decision.match_score,
                phase=decision.phase,
                weeks_remaining=decision.weeks_remaining,
            )

            logger.info(
                f"Saved weekly metrics for plan {plan_id}, week {analysis.week_num}"
            )

            return metrics_record.id

        except Exception as e:
            logger.error(f"Error saving weekly metrics: {e}")
            raise

    @staticmethod
    def get_historical_metrics(
        session: Session,
        plan_id: int,
        weeks: int = 3,
    ) -> List[WeekAnalysisResult]:
        """
        Get historical metrics for trend analysis.

        Args:
            session: SQLAlchemy session
            plan_id: Plan ID
            weeks: Number of weeks to fetch (default: 3)

        Returns:
            List of WeekAnalysisResult (most recent first)
        """
        try:
            metrics_records = get_historical_metrics_dao(session, plan_id, weeks)

            results = []
            for metrics in metrics_records:
                result = WeekAnalysisResult(
                    volume_score=float(metrics.volume_score or 0),
                    intensity_score=float(metrics.intensity_score or 0),
                    consistency_score=float(metrics.consistency_score or 0),
                    pace_deviation=float(metrics.pace_deviation or 0),
                    avg_actual_pace=(
                        float(metrics.avg_actual_pace)
                        if metrics.avg_actual_pace
                        else None
                    ),
                    avg_planned_pace=(
                        float(metrics.avg_planned_pace)
                        if metrics.avg_planned_pace
                        else None
                    ),
                    consecutive_missed_days=metrics.consecutive_missed_days or 0,
                    fatigue_markers=[],  # Not stored in metrics
                    current_week_load=float(metrics.current_week_load or 0),
                    previous_week_load=(
                        float(metrics.previous_week_load)
                        if metrics.previous_week_load
                        else None
                    ),
                    load_delta_pct=(
                        float(metrics.load_delta_pct)
                        if metrics.load_delta_pct
                        else None
                    ),
                    pace_threshold=float(metrics.pace_threshold or 10.0),
                    hr_threshold=float(metrics.hr_threshold or 5.0),
                    week_num=metrics.week_num,
                    week_start_date=metrics.week_start_date,
                    total_planned_miles=0.0,  # Not stored
                    total_actual_miles=0.0,  # Not stored
                    planned_workouts=0,  # Not stored
                    completed_workouts=0,  # Not stored
                )
                results.append(result)

            return results

        except Exception as e:
            logger.warning(f"Error fetching historical metrics: {e}")
            return []

    @staticmethod
    def get_decision_logs(
        session: Session,
        plan_id: int,
        week_num: Optional[int] = None,
    ) -> List[dict]:
        """
        Get decision logs for a plan (or specific week).

        Returns:
            List of decision log dictionaries
        """
        try:
            logs = get_decision_logs_by_plan(session, plan_id, week_num)
            return [
                {
                    "week_num": log.week_num,
                    "week_start_date": log.week_start_date.isoformat(),
                    "decision_type": log.decision_type,
                    "trigger_reason": log.trigger_reason,
                    "metrics_json": log.metrics_json,
                    "adjustments_json": log.adjustments_json,
                    "match_score": float(log.match_score) if log.match_score else 0.0,
                    "phase": log.phase,
                    "weeks_remaining": log.weeks_remaining,
                    "created_at": (
                        log.created_at.isoformat() if log.created_at else None
                    ),
                }
                for log in logs
            ]
        except Exception as e:
            logger.warning(f"Error fetching decision logs: {e}")
            return []
