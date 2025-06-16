from sqlalchemy import (
    Column,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    TIMESTAMP,
    BigInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from src.db.db_session import Base

class Split(Base):
    __tablename__ = "splits"

    id = Column(Integer, primary_key=True)
    activity_id = Column(BigInteger, ForeignKey("activities.activity_id", ondelete="CASCADE"), nullable=False)
    lap_index = Column(Integer, nullable=False)
    distance = Column(Float)
    elapsed_time = Column(Integer)
    moving_time = Column(Integer)
    average_speed = Column(Float)
    max_speed = Column(Float)
    start_index = Column(Integer)
    end_index = Column(Integer)
    split = Column(Boolean)  # ✅ Corrected from Integer to Boolean
    average_heartrate = Column(Float)
    pace_zone = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    conv_distance = Column(Float)
    conv_avg_speed = Column(Float)
    conv_moving_time = Column(String)
    conv_elapsed_time = Column(String)

    __table_args__ = (
        UniqueConstraint("activity_id", "lap_index", name="uq_activity_lap"),
    )
