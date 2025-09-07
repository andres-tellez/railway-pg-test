from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime
from src.db.db_session import Base


class Activity(Base):
    __tablename__ = "activities"

    activity_id = Column(BigInteger, primary_key=True, index=True)
    athlete_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String)
    type = Column(String)
    start_date = Column(DateTime)
    distance = Column(Float)
    elapsed_time = Column(Integer)
    moving_time = Column(Integer)
    total_elevation_gain = Column(Float)
    external_id = Column(String)
    timezone = Column(String)

    average_speed = Column(Float)
    max_speed = Column(Float)
    suffer_score = Column(Float)
    average_heartrate = Column(Float)
    max_heartrate = Column(Float)
    calories = Column(Float)

    conv_distance = Column(Float)
    conv_elevation_feet = Column(Float)
    conv_avg_speed = Column(Float)
    conv_max_speed = Column(Float)
    conv_moving_time = Column(String)
    conv_elapsed_time = Column(String)

    # HR Zone enrichment (test field)
    hr_zone_1 = Column(Float, nullable=True)
    hr_zone_2 = Column(Float, nullable=True)
    hr_zone_3 = Column(Float, nullable=True)
    hr_zone_4 = Column(Float, nullable=True)
    hr_zone_5 = Column(Float, nullable=True)
