"""
Weekly Decision Log DAO

Purpose:
    Database access object for weekly_decision_log table.
    Provides CRUD operations for decision log persistence.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from src.db.models.weekly_decision_log import WeeklyDecisionLog


def create_decision_log(
    session: Session,
    plan_id: int,
    week_num: int,
    week_start_date: date,
    decision_type: str,
    trigger_reason: str,
    metrics_json: dict,
    adjustments_json: dict,
    match_score: float,
    phase: str,
    weeks_remaining: int,
) -> WeeklyDecisionLog:
    """
    Create a new decision log record.

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        week_num: Week number
        week_start_date: Week start date (Monday)
        decision_type: Decision type (e.g., "fatigue_reduction")
        trigger_reason: Human-readable explanation
        metrics_json: All metrics used in decision (JSON)
        adjustments_json: Adjustments applied (JSON)
        match_score: Composite match score
        phase: Training phase
        weeks_remaining: Weeks until race

    Returns:
        Created WeeklyDecisionLog record
    """
    log = WeeklyDecisionLog(
        plan_id=plan_id,
        week_num=week_num,
        week_start_date=week_start_date,
        decision_type=decision_type,
        trigger_reason=trigger_reason,
        metrics_json=metrics_json,
        adjustments_json=adjustments_json,
        match_score=match_score,
        phase=phase,
        weeks_remaining=weeks_remaining,
    )
    session.add(log)
    session.flush()
    return log


def get_decision_logs_by_plan(
    session: Session,
    plan_id: int,
    week_num: Optional[int] = None,
) -> List[WeeklyDecisionLog]:
    """
    Get decision logs for a plan (optionally filtered by week).

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        week_num: Optional week number to filter by

    Returns:
        List of WeeklyDecisionLog records (most recent first)
    """
    query = session.query(WeeklyDecisionLog).filter_by(plan_id=plan_id)

    if week_num is not None:
        query = query.filter_by(week_num=week_num)

    return query.order_by(desc(WeeklyDecisionLog.week_num)).all()


def get_decision_log_by_plan_week(
    session: Session,
    plan_id: int,
    week_num: int,
) -> Optional[WeeklyDecisionLog]:
    """
    Get decision log for a specific plan and week.

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        week_num: Week number

    Returns:
        WeeklyDecisionLog record or None if not found
    """
    return (
        session.query(WeeklyDecisionLog)
        .filter_by(plan_id=plan_id, week_num=week_num)
        .first()
    )
