"""
Weekly Metrics DAO

Purpose:
    Database access object for weekly_metrics table.
    Provides CRUD operations for weekly metrics persistence.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from src.db.models.weekly_metrics import WeeklyMetrics


def create_weekly_metrics(
    session: Session, plan_id: int, week_num: int, week_start_date: date, **kwargs
) -> WeeklyMetrics:
    """
    Create a new weekly metrics record.

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        week_num: Week number
        week_start_date: Week start date (Monday)
        **kwargs: Additional metrics fields

    Returns:
        Created WeeklyMetrics record
    """
    metrics = WeeklyMetrics(
        plan_id=plan_id, week_num=week_num, week_start_date=week_start_date, **kwargs
    )
    session.add(metrics)
    session.flush()
    return metrics


def get_weekly_metrics_by_plan_week(
    session: Session,
    plan_id: int,
    week_num: int,
) -> Optional[WeeklyMetrics]:
    """
    Get weekly metrics for a specific plan and week.

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        week_num: Week number

    Returns:
        WeeklyMetrics record or None if not found
    """
    return (
        session.query(WeeklyMetrics)
        .filter_by(plan_id=plan_id, week_num=week_num)
        .first()
    )


def get_historical_metrics(
    session: Session,
    plan_id: int,
    weeks: int = 3,
) -> List[WeeklyMetrics]:
    """
    Get historical metrics for a plan (most recent first).

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        weeks: Number of weeks to fetch (default: 3)

    Returns:
        List of WeeklyMetrics records (most recent first)
    """
    return (
        session.query(WeeklyMetrics)
        .filter_by(plan_id=plan_id)
        .order_by(desc(WeeklyMetrics.week_num))
        .limit(weeks)
        .all()
    )


def upsert_weekly_metrics(
    session: Session, plan_id: int, week_num: int, week_start_date: date, **kwargs
) -> WeeklyMetrics:
    """
    Upsert (insert or update) weekly metrics.

    Args:
        session: SQLAlchemy session
        plan_id: Plan ID
        week_num: Week number
        week_start_date: Week start date (Monday)
        **kwargs: Metrics fields to update

    Returns:
        WeeklyMetrics record (created or updated)
    """
    existing = get_weekly_metrics_by_plan_week(session, plan_id, week_num)

    if existing:
        # Update existing record
        for key, value in kwargs.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        session.flush()
        return existing
    else:
        # Create new record
        return create_weekly_metrics(
            session, plan_id, week_num, week_start_date, **kwargs
        )
