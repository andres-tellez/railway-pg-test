"""
Weekly Decision Log Model

Purpose:
    Log of adjustment decisions with explanations.
    Enables debugging, explainability, and UI feedback.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from sqlalchemy import Column, Integer, Date, String, Text, JSON, TIMESTAMP, DECIMAL
from sqlalchemy.sql import func
from src.db.db_session import Base


class WeeklyDecisionLog(Base):
    """Log of adjustment decisions with explanations."""

    __tablename__ = "weekly_decision_log"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, nullable=False, index=True)
    week_num = Column(Integer, nullable=False)
    week_start_date = Column(Date, nullable=False)

    # Decision details
    decision_type = Column(String(50))  # "fatigue_reduction", etc.
    trigger_reason = Column(Text)  # Human-readable explanation

    # Metrics used (JSON)
    metrics_json = Column(JSON)  # All 6 metrics + trends

    # Adjustments applied (JSON)
    adjustments_json = Column(JSON)  # Volume, pace, quality changes

    # Composite score
    match_score = Column(DECIMAL(4, 2))

    # Context
    phase = Column(String(20))
    weeks_remaining = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
