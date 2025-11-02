"""
Weekly Metrics Model

Purpose:
    Store weekly training performance metrics for trend analysis.
    Enables historical trend analysis and future ML features.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from sqlalchemy import (
    Column,
    Integer,
    Date,
    DECIMAL,
    JSON,
    TIMESTAMP,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from src.db.db_session import Base


class WeeklyMetrics(Base):
    """Weekly training performance metrics."""

    __tablename__ = "weekly_metrics"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, nullable=False, index=True)
    week_num = Column(Integer, nullable=False)
    week_start_date = Column(Date, nullable=False)

    # Core metrics (0-100 scores)
    volume_score = Column(DECIMAL(5, 2))
    intensity_score = Column(DECIMAL(5, 2))
    consistency_score = Column(DECIMAL(5, 2))

    # Pace analysis (seconds)
    pace_deviation = Column(DECIMAL(6, 2))
    avg_actual_pace = Column(DECIMAL(6, 2))
    avg_planned_pace = Column(DECIMAL(6, 2))

    # Recovery indicators
    consecutive_missed_days = Column(Integer, default=0)

    # Training load
    current_week_load = Column(DECIMAL(8, 2))
    previous_week_load = Column(DECIMAL(8, 2))
    load_delta_pct = Column(DECIMAL(6, 2))

    # Dynamic thresholds
    pace_threshold = Column(DECIMAL(6, 2))
    hr_threshold = Column(DECIMAL(6, 2))

    # Composite score
    match_score = Column(DECIMAL(4, 2))

    # Context (future enhancement)
    context_score = Column(JSON)

    # Metadata
    phase = Column(String(20))
    weeks_remaining = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (UniqueConstraint("plan_id", "week_num", name="uq_plan_week"),)
