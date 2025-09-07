from sqlalchemy import Column, Integer, BigInteger, DateTime, func
from src.db.db_session import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True)
    strava_athlete_id = Column(BigInteger, unique=True, nullable=False)
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
