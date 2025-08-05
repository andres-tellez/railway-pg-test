from sqlalchemy import Column, Integer, BigInteger, String, DateTime, func
from src.db.db_session import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True)
    strava_athlete_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
