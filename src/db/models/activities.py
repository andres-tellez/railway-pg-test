# src/db/models/activities.py

from sqlalchemy import Column, Integer, String, Float, DateTime
from src.db.db_session import Base  # <-- Centralized Base import

class Activity(Base):
    __tablename__ = "activities"

    activity_id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)

    name = Column(String)
    type = Column(String)
    start_date = Column(DateTime)
    distance = Column(Float)
    elapsed_time = Column(Integer)
    moving_time = Column(Integer)
    total_elevation_gain = Column(Float)
    external_id = Column(String)
    timezone = Column(String)
