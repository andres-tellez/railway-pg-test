from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import Base


class RunnerZoneProfile(Base):
    __tablename__ = "runner_zone_profiles"

    user_id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)

    # HR bands (bpm)
    hr_z1_low = Column(Integer, nullable=True)
    hr_z1_high = Column(Integer, nullable=True)
    hr_z2_low = Column(Integer, nullable=True)
    hr_z2_high = Column(Integer, nullable=True)
    hr_z3_low = Column(Integer, nullable=True)
    hr_z3_high = Column(Integer, nullable=True)
    hr_z4_low = Column(Integer, nullable=True)
    hr_z4_high = Column(Integer, nullable=True)
    hr_z5_low = Column(Integer, nullable=True)
    hr_z5_high = Column(Integer, nullable=True)

    hrmax_used = Column(Integer, nullable=True)
    resting_hr_used = Column(Integer, nullable=True)
    zone_method = Column(String(16), nullable=True)

    # Pace bands (seconds / mile)
    pace_z2_low = Column(Integer, nullable=True)
    pace_z2_high = Column(Integer, nullable=True)
    pace_z3_low = Column(Integer, nullable=True)
    pace_z3_high = Column(Integer, nullable=True)
    pace_z4_low = Column(Integer, nullable=True)
    pace_z4_high = Column(Integer, nullable=True)
    pace_source = Column(String(20), nullable=True)
    pace_computed_at = Column(DateTime(timezone=True), nullable=True)

    computed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
