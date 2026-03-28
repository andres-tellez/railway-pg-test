from sqlalchemy import Column, String, Float, DateTime, func
from src.db.db_session import Base


class UserHrZones(Base):
    __tablename__ = "user_hr_zones"

    user_id = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    z1_low = Column(Float)
    z1_high = Column(Float)
    z2_low = Column(Float)
    z2_high = Column(Float)
    z3_low = Column(Float)
    z3_high = Column(Float)
    z4_low = Column(Float)
    z4_high = Column(Float)
    z5_low = Column(Float)
    z5_high = Column(Float)

    method = Column(String, nullable=False)
    hrmax_used = Column(Float)
    resting_hr_used = Column(Float)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
