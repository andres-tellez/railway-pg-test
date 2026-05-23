from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from src.db.db_session import Base
from src.db.models.user_profile import SqliteJSONB


class WeeklyTrainingInsight(Base):
    __tablename__ = "weekly_training_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)

    hr_drift_pct = Column(Float)
    z2_pace_min_per_mi = Column(Float)
    efficiency = Column(Float)

    hr_drift_band = Column(String(10))
    z2_pace_band = Column(String(10))
    efficiency_band = Column(String(10))
    overall_band = Column(String(10), nullable=False)

    hr_drift_delta = Column(Float)
    z2_pace_delta = Column(Float)
    efficiency_delta = Column(Float)

    easy_avg_hr = Column(Float)
    easy_avg_hr_band = Column(String(10))
    easy_avg_hr_delta = Column(Float)

    easy_run_count = Column(Integer, nullable=False, server_default="0")
    total_run_count = Column(Integer, nullable=False, server_default="0")

    summary_text = Column(Text)
    action_text = Column(Text)

    kpi_snapshot = Column(SqliteJSONB())
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
